import json
from pathlib import Path

import pytest

from app.oplog import (
    EVENT_APP_START,
    EVENT_ERROR_OCCURRED,
    EVENT_RUN_START,
    INFO,
    ERROR,
    get_operational_log_file,
    log_event,
    read_operational_logs,
    set_operational_log_file,
)


def test_oplog_write_and_read(tmp_path: Path):
    log_file = tmp_path / "test_operational.log"
    set_operational_log_file(log_file)
    try:
        log_event(
            EVENT_APP_START,
            level=INFO,
            component="manager",
            run_id="run-123",
            message="Manager starting",
            metadata={"port": 8000},
        )
        log_event(
            EVENT_ERROR_OCCURRED,
            level=ERROR,
            component="pipeline",
            run_id="run-123",
            error_class="ValueError",
            message="Sample failure",
            metadata={"source": "test.pdf"},
        )
        log_event(
            EVENT_RUN_START,
            level=INFO,
            component="pilot",
            run_id="run-456",
            message="Pilot run starting",
        )

        all_logs = read_operational_logs(log_file)
        assert len(all_logs) == 3
        assert all_logs[0]["event"] == EVENT_APP_START
        assert all_logs[0]["metadata"]["port"] == 8000
        assert all_logs[1]["level"] == ERROR
        assert all_logs[1]["error_class"] == "ValueError"

        # Test filtering by run_id
        run_123_logs = read_operational_logs(log_file, run_id="run-123")
        assert len(run_123_logs) == 2

        # Test filtering by event
        error_logs = read_operational_logs(log_file, event=EVENT_ERROR_OCCURRED)
        assert len(error_logs) == 1
        assert error_logs[0]["message"] == "Sample failure"

        # Test limit
        limit_logs = read_operational_logs(log_file, limit=1)
        assert len(limit_logs) == 1
        assert limit_logs[0]["run_id"] == "run-456"
    finally:
        set_operational_log_file(None)


def test_oplog_rotation(tmp_path: Path, monkeypatch):
    import app.oplog as oplog_mod

    monkeypatch.setattr(oplog_mod, "MAX_LOG_BYTES", 200)
    log_file = tmp_path / "test_rotate.log"
    set_operational_log_file(log_file)
    try:
        for i in range(10):
            log_event(
                EVENT_RUN_START,
                level=INFO,
                run_id=f"run-{i}",
                message="Message to test rotation and growth bounds",
            )
        assert log_file.is_file()
        backup1 = log_file.with_name("test_rotate.log.1")
        assert backup1.is_file()
    finally:
        set_operational_log_file(None)


def test_oplog_never_crashes(monkeypatch):
    # If file opening raises OSError, log_event should silently handle it
    def broken_open(*args, **kwargs):
        raise OSError("Disk locked or permission denied")

    monkeypatch.setattr(Path, "open", broken_open)
    # Must not raise
    log_event(EVENT_APP_START, message="Should not crash")
