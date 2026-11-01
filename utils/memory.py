"""Memory telemetry and cleanup for the 512 MB Render free tier."""
import ctypes
import gc
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def parse_memory_stat(text: str) -> dict:
    """Parse a cgroup memory.stat file ('key value' per line) into {key: bytes}."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            out[parts[0]] = int(parts[1])
    return out


def cgroup_mem_mb() -> dict:
    """Container-level memory in MB (what Render's OOM killer sees); {} if unavailable.

    The worker's RSS can be far below this (page cache, tmpfs/shared memory, other
    processes), so RSS alone cannot explain an OOM kill.
    """
    current = _read('/sys/fs/cgroup/memory.current')              # cgroup v2
    stat = _read('/sys/fs/cgroup/memory.stat')
    if current is None:                                           # cgroup v1
        current = _read('/sys/fs/cgroup/memory/memory.usage_in_bytes')
        stat = _read('/sys/fs/cgroup/memory/memory.stat')
    if current is None:
        return {}
    fields = parse_memory_stat(stat or '')
    mb = 1048576.0
    out = {'total': int(current.strip()) / mb}
    for name, keys in (('anon', ('anon', 'rss')), ('file', ('file', 'cache')),
                       ('shmem', ('shmem',)), ('slab', ('slab',))):
        for key in keys:
            if key in fields:
                out[name] = fields[key] / mb
                break
    return out


def rss_mb() -> float:
    """Resident memory of this process in MB (Linux /proc); -1.0 if unavailable."""
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024.0
    except (OSError, ValueError):
        pass
    return -1.0


def release_memory(tag: str) -> None:
    """Collect garbage, return freed heap pages to the OS, log RSS and container memory."""
    before = rss_mb()
    gc.collect()
    try:
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except (OSError, AttributeError):
        pass  # non-glibc platform (e.g. macOS dev box): skip trim
    cg = cgroup_mem_mb()
    extra = ''
    if cg:
        extra = ' | container ' + ' '.join(f'{k}={v:.0f}' for k, v in cg.items())
    logger.info("MEM %s: rss %.0f MB -> %.0f MB%s", tag, before, rss_mb(), extra)


def memory_guard(tag: str):
    """Decorator: run release_memory(tag) after a scheduler job, even on error."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            finally:
                release_memory(tag)
        return wrapper
    return decorator