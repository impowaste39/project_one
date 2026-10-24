import logging
import pytest
from utils import memory


def test_rss_is_positive_on_linux():
    assert memory.rss_mb() > 0


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
