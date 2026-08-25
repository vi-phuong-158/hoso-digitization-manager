"""Local Offline Operational Logging (Workstream B).

Ghi log có cấu trúc (JSONL) phục vụ quan sát hệ thống, truy vết và khắc phục sự cố.
Hoàn toàn offline-first: không gửi telemetry hay dữ liệu hồ sơ ra bên ngoài.
Không ghi toàn bộ nội dung nhạy cảm của tài liệu vào log.
Không để lỗi ghi log làm sập tiến trình chính.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import __version__ as APP_VERSION

DEFAULT_LOG_DIR = Path("logs")
LOG_FILENAME = "operational.log"
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 3

# Severities
DEBUG = "DEBUG"
INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"

# Defined event types
EVENT_APP_START = "APP_START"
EVENT_APP_EXIT = "APP_EXIT"
EVENT_RUN_START = "RUN_START"
EVENT_RUN_END = "RUN_END"
EVENT_SOURCE_DISCOVERED = "SOURCE_DISCOVERED"
EVENT_SOURCE_SKIPPED = "SOURCE_SKIPPED"
EVENT_SOURCE_ANALYZED = "SOURCE_ANALYZED"
EVENT_DOCUMENT_CLASSIFIED = "DOCUMENT_CLASSIFIED"
EVENT_DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
EVENT_REVIEW_REQUIRED = "REVIEW_REQUIRED"
EVENT_WRITE_COMPLETED = "WRITE_COMPLETED"
EVENT_RENAME_COMPLETED = "RENAME_COMPLETED"
EVENT_RETRY_ATTEMPTED = "RETRY_ATTEMPTED"
EVENT_RECOVERY_ATTEMPTED = "RECOVERY_ATTEMPTED"
EVENT_ERROR_OCCURRED = "ERROR_OCCURRED"
EVENT_CRASH_DETECTED = "CRASH_DETECTED"
EVENT_BACKUP_COMPLETED = "BACKUP_COMPLETED"
EVENT_RESTORE_COMPLETED = "RESTORE_COMPLETED"
EVENT_RECONCILE_COMPLETED = "RECONCILE_COMPLETED"

_lock = threading.Lock()
_custom_log_file: Optional[Path] = None


def set_operational_log_file(path: Optional[Path]) -> None:
    """Cấu hình file log cục bộ (chủ yếu dùng cho test hoặc workspace riêng)."""
    global _custom_log_file
    with _lock:
        _custom_log_file = Path(path) if path is not None else None


def get_operational_log_file() -> Path:
    if _custom_log_file is not None:
        return _custom_log_file
    return DEFAULT_LOG_DIR / LOG_FILENAME


def _rotate_if_needed(log_path: Path) -> None:
    try:
        if not log_path.is_file() or log_path.stat().st_size < MAX_LOG_BYTES:
            return
        for idx in range(BACKUP_COUNT - 1, 0, -1):
            src = log_path.with_name(f"{log_path.name}.{idx}")
            dst = log_path.with_name(f"{log_path.name}.{idx + 1}")
            if src.is_file():
                src.replace(dst)
        target = log_path.with_name(f"{log_path.name}.1")
        log_path.replace(target)
    except Exception:
        pass


def log_event(
    event: str,
    *,
    level: str = INFO,
    component: str = "pipeline",
    run_id: Optional[str] = None,
    source_id: Optional[str] = None,
    document_id: Optional[str] = None,
    error_class: Optional[str] = None,
    message: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Ghi một bản ghi operational log dạng JSONL.

    Bảo đảm không bao giờ ném exception ra ngoài làm gián đoạn nghiệp vụ chính.
    """
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "level": level,
            "component": component,
            "event": event,
            "version": APP_VERSION,
            "run_id": run_id,
            "source_id": source_id,
            "document_id": document_id,
            "error_class": error_class,
            "message": message,
            "metadata": metadata or {},
        }
        log_path = get_operational_log_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            _rotate_if_needed(log_path)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Logging failure must never fail the application.
        pass


def read_operational_logs(
    log_path: Optional[Path] = None,
    *,
    run_id: Optional[str] = None,
    event: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Đọc và lọc các bản ghi operational log phục vụ kiểm tra và audit."""
    target_path = log_path or get_operational_log_file()
    if not target_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with target_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if run_id and data.get("run_id") != run_id:
                        continue
                    if event and data.get("event") != event:
                        continue
                    records.append(data)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    if limit is not None and len(records) > limit:
        return records[-limit:]
    return records
