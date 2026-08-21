"""State registry — theo dõi PDF nào đã PROCESSED để không đọc lại (Antigravity Agent).

Lưu trên SQLite local (`state/processing_state.db`). Đây KHÔNG phải database
server; chỉ là một file local, không thêm dịch vụ ngoài. Không lưu toàn văn
hồ sơ hay OCR — chỉ lưu metadata điều phối tối thiểu.

Khóa nhận diện DUY NHẤT là SHA-256 của toàn bộ file PDF nguồn, không phải
filename. Không được sửa/đánh dấu vào chính PDF nguồn.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import __version__ as PIPELINE_VERSION
from .models import PipelineError

DB_FILENAME = "processing_state.db"

STATUS_PROCESSING = "PROCESSING"
STATUS_PROCESSED = "PROCESSED"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_FAILED = "FAILED"

# Các giá trị hợp lệ duy nhất cho cột `status` trong bảng sources.
PERSISTED_STATUSES = (STATUS_PROCESSING, STATUS_PROCESSED, STATUS_REVIEW_REQUIRED, STATUS_FAILED)

_MAX_ERROR_LEN = 2000  # chặn last_error phình to thành nơi chép nội dung tài liệu


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SourceState:
    source_hash: str
    source_filename: str
    source_relative_path: str
    person_folder: str
    page_count: int
    status: str
    first_seen_at: str
    processing_started_at: Optional[str]
    processed_at: Optional[str]
    logical_document_count: Optional[int]
    manifest_path: Optional[str]
    last_error: Optional[str]
    pipeline_version: str
    last_seen_path: str
    updated_at: str

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


class StateRegistry:
    """Lớp truy cập SQLite. Mỗi phương thức mutate là MỘT transaction atomic."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=30)
        self._conn.row_factory = sqlite3.Row
        # WAL + synchronous=FULL: an toàn khi crash giữa chừng, vẫn đủ nhanh cho
        # một tool local một người dùng. Không cần cấu hình gì thêm phía người dùng.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "StateRegistry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    source_hash TEXT PRIMARY KEY,
                    source_filename TEXT NOT NULL,
                    source_relative_path TEXT NOT NULL,
                    person_folder TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                        ('PROCESSING','PROCESSED','REVIEW_REQUIRED','FAILED')),
                    first_seen_at TEXT NOT NULL,
                    processing_started_at TEXT,
                    processed_at TEXT,
                    logical_document_count INTEGER,
                    manifest_path TEXT,
                    last_error TEXT,
                    pipeline_version TEXT NOT NULL,
                    last_seen_path TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sources_person ON sources(person_folder)"
            )

    # ---------------- truy vấn (read-only) ----------------
    def get(self, source_hash: str) -> Optional[SourceState]:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE source_hash = ?", (source_hash,)
        ).fetchone()
        return SourceState(**dict(row)) if row else None

    def all(self, person_folder: Optional[str] = None) -> list[SourceState]:
        if person_folder is None:
            rows = self._conn.execute("SELECT * FROM sources ORDER BY source_hash").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sources WHERE person_folder = ? ORDER BY source_hash",
                (person_folder,),
            ).fetchall()
        return [SourceState(**dict(r)) for r in rows]

    def export_json(self) -> dict:
        return {
            "schema": "processing_state.v1",
            "exported_at": _now(),
            "sources": [s.as_dict() for s in self.all()],
        }

    # ---------------- mutate (mỗi hàm = 1 transaction) ----------------
    def begin_processing(
        self,
        *,
        source_hash: str,
        source_filename: str,
        source_relative_path: str,
        person_folder: str,
        page_count: int,
    ) -> None:
        """NEW -> PROCESSING, hoặc retry (FAILED/REVIEW_REQUIRED/INTERRUPTED) -> PROCESSING.

        Phải được gọi và COMMIT xong TRƯỚC KHI đưa PDF cho Agent đọc, để nếu
        tiến trình bị crash giữa chừng, lần chạy sau phát hiện được PROCESSING
        còn sót lại (INTERRUPTED) thay vì mất dấu.
        """
        ts = _now()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sources (
                    source_hash, source_filename, source_relative_path, person_folder,
                    page_count, status, first_seen_at, processing_started_at,
                    processed_at, logical_document_count, manifest_path, last_error,
                    pipeline_version, last_seen_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'PROCESSING', ?, ?, NULL, NULL, NULL, NULL, ?, ?, ?)
                ON CONFLICT(source_hash) DO UPDATE SET
                    status = 'PROCESSING',
                    processing_started_at = excluded.processing_started_at,
                    last_error = NULL,
                    pipeline_version = excluded.pipeline_version,
                    source_filename = excluded.source_filename,
                    source_relative_path = excluded.source_relative_path,
                    person_folder = excluded.person_folder,
                    last_seen_path = excluded.last_seen_path,
                    updated_at = excluded.updated_at
                """,
                (
                    source_hash,
                    source_filename,
                    source_relative_path,
                    person_folder,
                    page_count,
                    ts,
                    ts,
                    PIPELINE_VERSION,
                    source_relative_path,
                    ts,
                ),
            )

    def commit_processed(
        self, source_hash: str, *, logical_document_count: int, manifest_path: str
    ) -> None:
        """PROCESSING -> PROCESSED. Chỉ gọi sau khi apply hoàn tất + QC PASS."""
        self._transition_from_processing(
            source_hash,
            status=STATUS_PROCESSED,
            logical_document_count=logical_document_count,
            manifest_path=manifest_path,
            last_error=None,
            set_processed_at=True,
        )

    def mark_review_required(
        self, source_hash: str, *, logical_document_count: int, manifest_path: Optional[str]
    ) -> None:
        """PROCESSING -> REVIEW_REQUIRED. Dry-run xác định có tài liệu cần người kiểm tra."""
        self._transition_from_processing(
            source_hash,
            status=STATUS_REVIEW_REQUIRED,
            logical_document_count=logical_document_count,
            manifest_path=manifest_path,
            last_error=None,
            set_processed_at=False,
        )

    def mark_failed(self, source_hash: str, *, error: str) -> None:
        """PROCESSING -> FAILED. Không tự retry; cần hành động rõ ràng của người vận hành."""
        self._transition_from_processing(
            source_hash,
            status=STATUS_FAILED,
            logical_document_count=None,
            manifest_path=None,
            last_error=(error or "")[:_MAX_ERROR_LEN],
            set_processed_at=False,
        )

    def release(self, source_hash: str) -> None:
        """Xoá record nếu đang PROCESSING (dry-run sạch, không có gì cần REVIEW).

        Trở về trạng thái NEW (không có record) thay vì bịa ra một status thứ 6
        ngoài 5 status bắt buộc.
        """
        with self._conn:
            self._conn.execute(
                "DELETE FROM sources WHERE source_hash = ? AND status = 'PROCESSING'",
                (source_hash,),
            )

    def _transition_from_processing(
        self,
        source_hash: str,
        *,
        status: str,
        logical_document_count: Optional[int],
        manifest_path: Optional[str],
        last_error: Optional[str],
        set_processed_at: bool,
    ) -> None:
        ts = _now()
        with self._conn:
            cur = self._conn.execute(
                f"""
                UPDATE sources SET
                    status = ?,
                    processed_at = {'?' if set_processed_at else 'processed_at'},
                    logical_document_count = ?,
                    manifest_path = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE source_hash = ? AND status = 'PROCESSING'
                """,
                (
                    *((status, ts) if set_processed_at else (status,)),
                    logical_document_count,
                    manifest_path,
                    last_error,
                    ts,
                    source_hash,
                ),
            )
            if cur.rowcount != 1:
                raise PipelineError(
                    f"State transition -> {status} thất bại cho hash {source_hash[:12]}…: "
                    "record không ở trạng thái PROCESSING (đã bị thay đổi bởi tiến trình khác?)."
                )

    # ---------------- migration (Phase 27) ----------------
    def import_processed(
        self,
        *,
        source_hash: str,
        source_filename: str,
        source_relative_path: str,
        person_folder: str,
        page_count: int,
        logical_document_count: int,
        manifest_path: str,
    ) -> None:
        """Nạp một record PROCESSED từ bằng chứng manifest/output đã xác minh.

        CHỈ dùng bởi `app.state_import` sau khi đã kiểm tra: manifest tồn tại,
        hash/pages khớp, mọi target_file thực sự có trên đĩa. Không đi qua
        PROCESSING vì đây là ghi nhận việc đã xảy ra ở lần chạy trước khi có
        state registry, không phải một lần chạy pipeline mới.
        """
        ts = _now()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sources (
                    source_hash, source_filename, source_relative_path, person_folder,
                    page_count, status, first_seen_at, processing_started_at,
                    processed_at, logical_document_count, manifest_path, last_error,
                    pipeline_version, last_seen_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'PROCESSED', ?, NULL, ?, ?, ?, NULL, ?, ?, ?)
                ON CONFLICT(source_hash) DO NOTHING
                """,
                (
                    source_hash,
                    source_filename,
                    source_relative_path,
                    person_folder,
                    page_count,
                    ts,
                    ts,
                    logical_document_count,
                    manifest_path,
                    PIPELINE_VERSION,
                    source_relative_path,
                    ts,
                ),
            )
