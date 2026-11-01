import logging
import sys

import pytest
from utils import memory


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="reads /proc/self/status (Linux/Render only)")
def test_rss_is_positive_on_linux():
    assert memory.rss_mb() > 0


def test_rss_returns_minus_one_when_proc_unavailable(monkeypatch):
    # what macOS/Windows dev machines hit: must degrade gracefully, not raise
    def boom(*args, **kwargs):
        raise OSError("no /proc")
    monkeypatch.setattr(memory, "open", boom, raising=False)
    assert memory.rss_mb() == -1.0


def test_release_memory_logs(caplog):
    with caplog.at_level(logging.INFO, logger="utils.memory"):
        memory.release_memory("unit")
    assert any("MEM unit" in r.message for r in caplog.records)


def test_guard_preserves_name_and_returns_value():
    @memory.memory_guard("t")
    def job():
        return 42
    assert job() == 42
    assert job.__name__ == "job"


def test_guard_runs_cleanup_even_when_job_raises(caplog):
    @memory.memory_guard("boom")
    def job():
        raise RuntimeError("x")
    with caplog.at_level(logging.INFO, logger="utils.memory"):
        with pytest.raises(RuntimeError):
            job()
    assert any("MEM boom" in r.message for r in caplog.records)


V2_STAT = "anon 314572800\nfile 125829120\nshmem 10485760\nslab 5242880\nkernel_stack 1\n"


def test_parse_memory_stat():
    d = memory.parse_memory_stat(V2_STAT)
    assert d['anon'] == 314572800 and d['file'] == 125829120


def test_cgroup_v2_values(monkeypatch):
    files = {'/sys/fs/cgroup/memory.current': '536870912\n', '/sys/fs/cgroup/memory.stat': V2_STAT}
    monkeypatch.setattr(memory, '_read', lambda p: files.get(p))
    cg = memory.cgroup_mem_mb()
    assert cg['total'] == 512.0 and cg['anon'] == 300.0 and cg['file'] == 120.0 and cg['shmem'] == 10.0


def test_cgroup_v1_fallback(monkeypatch):
    files = {'/sys/fs/cgroup/memory/memory.usage_in_bytes': '209715200\n',
             '/sys/fs/cgroup/memory/memory.stat': 'rss 104857600\ncache 52428800\nshmem 1048576\n'}
    monkeypatch.setattr(memory, '_read', lambda p: files.get(p))
    cg = memory.cgroup_mem_mb()
    assert cg['total'] == 200.0 and cg['anon'] == 100.0 and cg['file'] == 50.0


def test_cgroup_unavailable_returns_empty_and_log_still_works(monkeypatch, caplog):
    monkeypatch.setattr(memory, '_read', lambda p: None)
    assert memory.cgroup_mem_mb() == {}
    with caplog.at_level(logging.INFO, logger='utils.memory'):
        memory.release_memory('nocg')
    assert any('MEM nocg' in r.message and 'container' not in r.message for r in caplog.records)