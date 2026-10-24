"""Memory telemetry and cleanup for the 512 MB Render free tier."""
import ctypes
import gc
import logging
from functools import wraps

logger = logging.getLogger(__name__)


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
    """Collect garbage, return freed heap pages to the OS, log RSS before/after."""
    before = rss_mb()
    gc.collect()
    try:
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except (OSError, AttributeError):
        pass  # non-glibc platform (e.g. macOS dev box): skip trim
    logger.info("MEM %s: rss %.0f MB -> %.0f MB", tag, before, rss_mb())


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
