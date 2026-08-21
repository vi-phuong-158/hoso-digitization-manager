"""State registry — theo dõi PDF nào đã PROCESSED để không đọc lại (Antigravity Agent).

Lưu trên SQLite local (`state/processing_state.db`). Đây KHÔNG phải database
server; chỉ là một file local, không thêm dịch vụ ngoài. Không lưu toàn văn
hồ sơ hay OCR — chỉ lưu metadata điều phối tối thiểu.

Khóa nhận diện DUY NHẤT là SHA-256 của toàn bộ file PDF nguồn, không phải
filename. Không được sửa/đánh dấu vào chính PDF nguồn.

Hai khái niệm tách biệt (đây là điểm khác biệt cốt lõi so với bản đầu tiên):
  - AI đã đọc/phân tích xong nguồn      -> ANALYZED_PENDING_APPLY / REVIEW_REQUIRED
  - Nghiệp vụ đã hoàn tất (mọi logical
    document đã được giải quyết + ghi
    file thật + QC PASS)                -> PROCESSED

Một nguồn có tài liệu REVIEW chưa được người vận hành chốt thì KHÔNG BAO GIỜ
tự chuyển thành PROCESSED, dù đã apply và đã copy ra `review/`.
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
STATUS_ANALYZED_PENDING_APPLY = "ANALYZED_PENDING_APPLY"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_PROCESSED = "PROCESSED"
STATUS_FAILED = "FAILED"

# Các giá trị hợp lệ duy nhất cho cột `status` trong bảng sources.
PERSISTED_STATUSES = (
    STATUS_PROCESSING,
    STATUS_ANALYZED_PENDING_APPLY,
    STATUS_REVIEW_REQUIRED,
    STATUS_PROCESSED,
    STATUS_FAILED,
)

RESOLUTION_AUTO_RESOLVED = "AUTO_RESOLVED"
RESOLUTION_REVIEW_PENDING = "REVIEW_PENDING"
RESOLUTION_REVIEW_RESOLVED = "REVIEW_RESOLVED"

_MAX_ERROR_LEN = 2000  # chặn last_error phình to thành nơi chép nội dung tài liệu
_MAX_TITLE_LEN = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def logical_document_id(source_hash: str, source_pages: list[int]) -> str:
    """ID ổn định, không đổi qua các lần renumber (Phase K).

    Chỉ phụ thuộc (source_hash, source_pages) — hai thứ KHÔNG đổi theo thời
    gian cho cùng một logical document, dù filename/sequence có bị tính lại.
    """
    import hashlib

    raw = source_hash + "|" + ",".join(str(p) for p in source_pages)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


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
    taxonomy_version: Optional[str]
    analysis_schema_version: Optional[str]
    last_seen_path: str
    updated_at: str

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class LogicalDocumentRow:
    logical_document_id: str
    source_hash: str
    source_pages: list[int]
    type_id: str
    confidence: float
    document_date: Optional[str]
    date_confidence: float
    title_short: Optional[str]
    segmentation_flags: list[str]
    classification_status: str  # AUTO | REVIEW (trục phân loại, Phase D)
    classification_reasons: list[str]
    resolution_status: str  # AUTO_RESOLVED | REVIEW_PENDING | REVIEW_RESOLVED
    resolved_type_id: Optional[str]
    resolved_document_date: Optional[str]
    resolved_by: Optional[str]
    resolved_at: Optional[str]
    current_target_filename: Optional[str]
    target_dir: Optional[str]
    sequence_index: Optional[int]
    created_at: str
    updated_at: str

    @property
    def effective_type_id(self) -> str:
        return self.resolved_type_id or self.type_id

    @property
    def effective_document_date(self) -> Optional[str]:
        return self.resolved_document_date or self.document_date

    @property
    def is_settled(self) -> bool:
        """Đã có filename chính thức được không (không còn REVIEW_PENDING)."""
        return self.resolution_status != RESOLUTION_REVIEW_PENDING

    def as_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["source_pages"] = list(self.source_pages)
        d["segmentation_flags"] = list(self.segmentation_flags)
        d["classification_reasons"] = list(self.classification_reasons)
        return d


def _row_to_logical_document(row: sqlite3.Row) -> LogicalDocumentRow:
    d = dict(row)
    d["source_pages"] = json.loads(d["source_pages"])
    d["segmentation_flags"] = json.loads(d["segmentation_flags"])
    d["classification_reasons"] = json.loads(d["classification_reasons"])
    return LogicalDocumentRow(**d)


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
                        ('PROCESSING','ANALYZED_PENDING_APPLY','REVIEW_REQUIRED','PROCESSED','FAILED')),
                    first_seen_at TEXT NOT NULL,
                    processing_started_at TEXT,
                    processed_at TEXT,
                    logical_document_count INTEGER,
                    manifest_path TEXT,
                    last_error TEXT,
                    pipeline_version TEXT NOT NULL,
                    taxonomy_version TEXT,
                    analysis_schema_version TEXT,
                    last_seen_path TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sources_person ON sources(person_folder)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logical_documents (
                    logical_document_id TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL REFERENCES sources(source_hash),
                    source_pages TEXT NOT NULL,
                    type_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    document_date TEXT,
                    date_confidence REAL NOT NULL,
                    title_short TEXT,
                    segmentation_flags TEXT NOT NULL,
                    classification_status TEXT NOT NULL CHECK(classification_status IN ('AUTO','REVIEW')),
                    classification_reasons TEXT NOT NULL,
                    resolution_status TEXT NOT NULL CHECK(resolution_status IN
                        ('AUTO_RESOLVED','REVIEW_PENDING','REVIEW_RESOLVED')),
                    resolved_type_id TEXT,
                    resolved_document_date TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    current_target_filename TEXT,
                    target_dir TEXT,
                    sequence_index INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_logdocs_source ON logical_documents(source_hash)"
            )

    # ================= sources: truy vấn (read-only) =================
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
            "schema": "processing_state.v2",
            "exported_at": _now(),
            "sources": [s.as_dict() for s in self.all()],
            "logical_documents": [d.as_dict() for d in self._all_logical_documents()],
        }

    def _all_logical_documents(self) -> list[LogicalDocumentRow]:
        rows = self._conn.execute(
            "SELECT * FROM logical_documents ORDER BY logical_document_id"
        ).fetchall()
        return [_row_to_logical_document(r) for r in rows]

    # ================= sources: mutate =================
    def begin_processing(
        self,
        *,
        source_hash: str,
        source_filename: str,
        source_relative_path: str,
        person_folder: str,
        page_count: int,
    ) -> None:
        """NEW -> PROCESSING, hoặc retry (FAILED/REVIEW_REQUIRED/STALE/INTERRUPTED) -> PROCESSING.

        Phải được gọi và COMMIT xong TRƯỚC KHI đưa PDF cho Agent đọc, để nếu
        tiến trình bị crash giữa chừng, lần chạy sau phát hiện được PROCESSING
        còn sót lại (INTERRUPTED) thay vì mất dấu. Xoá sạch logical_documents
        cũ (nếu có) vì phân tích sắp được làm lại từ đầu.
        """
        ts = _now()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sources (
                    source_hash, source_filename, source_relative_path, person_folder,
                    page_count, status, first_seen_at, processing_started_at,
                    processed_at, logical_document_count, manifest_path, last_error,
                    pipeline_version, taxonomy_version, analysis_schema_version,
                    last_seen_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'PROCESSING', ?, ?, NULL, NULL, NULL, NULL, ?, NULL, NULL, ?, ?)
                ON CONFLICT(source_hash) DO UPDATE SET
                    status = 'PROCESSING',
                    processing_started_at = excluded.processing_started_at,
                    last_error = NULL,
                    pipeline_version = excluded.pipeline_version,
                    taxonomy_version = NULL,
                    analysis_schema_version = NULL,
                    source_filename = excluded.source_filename,
                    source_relative_path = excluded.source_relative_path,
                    person_folder = excluded.person_folder,
                    last_seen_path = excluded.last_seen_path,
                    updated_at = excluded.updated_at
                """,
                (
                    source_hash, source_filename, source_relative_path, person_folder,
                    page_count, ts, ts, PIPELINE_VERSION, source_relative_path, ts,
                ),
            )
            self._conn.execute(
                "DELETE FROM logical_documents WHERE source_hash = ?", (source_hash,)
            )

    def save_analysis(
        self,
        source_hash: str,
        *,
        documents: list[dict],
        taxonomy_version: str,
        analysis_schema_version: str,
    ) -> None:
        """PROCESSING -> ANALYZED_PENDING_APPLY (không review) hoặc REVIEW_REQUIRED
        (còn ít nhất một logical document REVIEW_PENDING). Ghi bảng
        `logical_documents` = kết quả phân loại + segmentation đã đóng băng.

        Mỗi dict trong `documents` cần các khoá: source_pages, type_id, confidence,
        document_date, date_confidence, title_short, segmentation_flags,
        classification_status ("AUTO"/"REVIEW"), classification_reasons.
        """
        has_review = any(d["classification_status"] == "REVIEW" for d in documents)
        status = STATUS_REVIEW_REQUIRED if has_review else STATUS_ANALYZED_PENDING_APPLY
        ts = _now()
        with self._conn:
            cur = self._conn.execute(
                """
                UPDATE sources SET
                    status = ?, taxonomy_version = ?, analysis_schema_version = ?,
                    last_error = NULL, updated_at = ?
                WHERE source_hash = ? AND status = 'PROCESSING'
                """,
                (status, taxonomy_version, analysis_schema_version, ts, source_hash),
            )
            if cur.rowcount != 1:
                raise PipelineError(
                    f"Lưu analysis thất bại cho hash {source_hash[:12]}…: "
                    "record không ở trạng thái PROCESSING."
                )
            self._conn.execute(
                "DELETE FROM logical_documents WHERE source_hash = ?", (source_hash,)
            )
            for d in documents:
                is_review = d["classification_status"] == "REVIEW"
                lid = logical_document_id(source_hash, d["source_pages"])
                title = (d.get("title_short") or None)
                if title and len(title) > _MAX_TITLE_LEN:
                    title = title[:_MAX_TITLE_LEN]
                self._conn.execute(
                    """
                    INSERT INTO logical_documents (
                        logical_document_id, source_hash, source_pages, type_id, confidence,
                        document_date, date_confidence, title_short, segmentation_flags,
                        classification_status, classification_reasons, resolution_status,
                        resolved_type_id, resolved_document_date, resolved_by, resolved_at,
                        current_target_filename, target_dir, sequence_index,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
                    """,
                    (
                        lid, source_hash, json.dumps(d["source_pages"]), d["type_id"],
                        float(d["confidence"]), d.get("document_date"),
                        float(d.get("date_confidence") or 0.0), title,
                        json.dumps(d.get("segmentation_flags") or []),
                        d["classification_status"], json.dumps(d.get("classification_reasons") or []),
                        RESOLUTION_REVIEW_PENDING if is_review else RESOLUTION_AUTO_RESOLVED,
                        ts, ts,
                    ),
                )

    def cached_analysis(
        self, source_hash: str, *, taxonomy_version: str, analysis_schema_version: str
    ) -> Optional[list[LogicalDocumentRow]]:
        """Trả về logical_documents đã lưu NẾU fingerprint còn khớp và nguồn đang
        ở ANALYZED_PENDING_APPLY/REVIEW_REQUIRED. None nếu không có cache hợp lệ
        (STALE_ANALYSIS hoặc chưa từng phân tích)."""
        rec = self.get(source_hash)
        if rec is None or rec.status not in (STATUS_ANALYZED_PENDING_APPLY, STATUS_REVIEW_REQUIRED):
            return None
        if rec.taxonomy_version != taxonomy_version or rec.analysis_schema_version != analysis_schema_version:
            return None
        return self.logical_documents_for(source_hash)

    def get_logical_document(self, logical_document_id_: str) -> Optional[LogicalDocumentRow]:
        row = self._conn.execute(
            "SELECT * FROM logical_documents WHERE logical_document_id = ?", (logical_document_id_,)
        ).fetchone()
        return _row_to_logical_document(row) if row else None

    def logical_documents_for(self, source_hash: str) -> list[LogicalDocumentRow]:
        rows = self._conn.execute(
            "SELECT * FROM logical_documents WHERE source_hash = ? ORDER BY logical_document_id",
            (source_hash,),
        ).fetchall()
        return [_row_to_logical_document(r) for r in rows]

    def logical_documents_for_person(
        self, person_folder: str, *, type_id: Optional[str] = None
    ) -> list[LogicalDocumentRow]:
        """Toàn bộ logical_documents của MỌI nguồn đã biết của một người — nền
        tảng cho global cross-run naming (Phase F/G)."""
        q = (
            "SELECT ld.* FROM logical_documents ld "
            "JOIN sources s ON s.source_hash = ld.source_hash "
            "WHERE s.person_folder = ?"
        )
        params: list = [person_folder]
        if type_id is not None:
            q += " AND (COALESCE(ld.resolved_type_id, ld.type_id) = ?)"
            params.append(type_id)
        q += " ORDER BY ld.logical_document_id"
        rows = self._conn.execute(q, params).fetchall()
        return [_row_to_logical_document(r) for r in rows]

    def set_target(
        self, logical_document_id_: str, *, target_filename: str, target_dir: str, sequence_index: Optional[int]
    ) -> None:
        ts = _now()
        with self._conn:
            self._conn.execute(
                """
                UPDATE logical_documents SET
                    current_target_filename = ?, target_dir = ?, sequence_index = ?, updated_at = ?
                WHERE logical_document_id = ?
                """,
                (target_filename, target_dir, sequence_index, ts, logical_document_id_),
            )

    def resolve_review(
        self,
        logical_document_id_: str,
        *,
        resolved_type_id: str,
        resolved_document_date: Optional[str],
        resolved_by: str,
    ) -> None:
        """Người vận hành chốt một logical document đang REVIEW_PENDING.

        Chỉ đổi resolution_status; KHÔNG tự động ghi file — apply lần sau sẽ
        tính lại global naming và ghi file thật (Phase E)."""
        ts = _now()
        with self._conn:
            cur = self._conn.execute(
                """
                UPDATE logical_documents SET
                    resolution_status = 'REVIEW_RESOLVED', resolved_type_id = ?,
                    resolved_document_date = ?, resolved_by = ?, resolved_at = ?, updated_at = ?
                WHERE logical_document_id = ? AND resolution_status = 'REVIEW_PENDING'
                """,
                (resolved_type_id, resolved_document_date, resolved_by, ts, ts, logical_document_id_),
            )
            if cur.rowcount != 1:
                raise PipelineError(
                    f"resolve_review thất bại cho {logical_document_id_}: "
                    "không tồn tại hoặc không ở REVIEW_PENDING."
                )

    def pending_reviews_for_source(self, source_hash: str) -> list[LogicalDocumentRow]:
        return [
            d for d in self.logical_documents_for(source_hash)
            if d.resolution_status == RESOLUTION_REVIEW_PENDING
        ]

    def commit_processed(
        self, source_hash: str, *, logical_document_count: int, manifest_path: str
    ) -> None:
        """-> PROCESSED. Chỉ gọi sau khi: apply hoàn tất + QC PASS + KHÔNG còn
        logical document nào REVIEW_PENDING của nguồn này."""
        pending = self.pending_reviews_for_source(source_hash)
        if pending:
            raise PipelineError(
                f"Không thể đánh PROCESSED cho hash {source_hash[:12]}…: "
                f"còn {len(pending)} logical document REVIEW_PENDING."
            )
        ts = _now()
        with self._conn:
            cur = self._conn.execute(
                """
                UPDATE sources SET
                    status = 'PROCESSED', processed_at = ?, logical_document_count = ?,
                    manifest_path = ?, last_error = NULL, updated_at = ?
                WHERE source_hash = ? AND status IN ('ANALYZED_PENDING_APPLY', 'REVIEW_REQUIRED')
                """,
                (ts, logical_document_count, manifest_path, ts, source_hash),
            )
            if cur.rowcount != 1:
                raise PipelineError(
                    f"State transition -> PROCESSED thất bại cho hash {source_hash[:12]}…: "
                    "record không ở ANALYZED_PENDING_APPLY/REVIEW_REQUIRED."
                )

    def mark_failed(self, source_hash: str, *, error: str) -> None:
        """-> FAILED. Không tự retry; cần hành động rõ ràng của người vận hành."""
        ts = _now()
        with self._conn:
            cur = self._conn.execute(
                """
                UPDATE sources SET status = 'FAILED', last_error = ?, updated_at = ?
                WHERE source_hash = ? AND status IN
                    ('PROCESSING', 'ANALYZED_PENDING_APPLY', 'REVIEW_REQUIRED')
                """,
                ((error or "")[:_MAX_ERROR_LEN], ts, source_hash),
            )
            if cur.rowcount != 1:
                raise PipelineError(
                    f"State transition -> FAILED thất bại cho hash {source_hash[:12]}…: "
                    "record không ở trạng thái hợp lệ để chuyển FAILED."
                )

    # ================= migration (Phase 27 cũ) =================
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
        hash/pages khớp, mọi target_file thực sự có trên đĩa. Không có
        logical_documents chi tiết (import chỉ có bằng chứng ở mức file, không
        có lại được segmentation/classification gốc) — nguồn import được coi
        đã hoàn tất nghiệp vụ (không còn review treo) vì bằng chứng là một
        ledger apply THÀNH CÔNG trước đó.
        """
        ts = _now()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sources (
                    source_hash, source_filename, source_relative_path, person_folder,
                    page_count, status, first_seen_at, processing_started_at,
                    processed_at, logical_document_count, manifest_path, last_error,
                    pipeline_version, taxonomy_version, analysis_schema_version,
                    last_seen_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'PROCESSED', ?, NULL, ?, ?, ?, NULL, ?, NULL, NULL, ?, ?)
                ON CONFLICT(source_hash) DO NOTHING
                """,
                (
                    source_hash, source_filename, source_relative_path, person_folder,
                    page_count, ts, ts, logical_document_count, manifest_path,
                    PIPELINE_VERSION, source_relative_path, ts,
                ),
            )
