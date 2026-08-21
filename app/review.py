"""Phase E — Human review resolution.

Người vận hành chốt một logical document đang REVIEW_PENDING mà KHÔNG cần
Agent đọc lại toàn bộ PDF nguồn. Sau khi resolve, lượt `apply` kế tiếp sẽ tính
lại global naming (app/global_naming.py) và ghi file thật.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .catalog import Catalog
from .models import PipelineError, UNKNOWN
from .state import LogicalDocumentRow, StateRegistry


@dataclass(frozen=True)
class ReviewItem:
    logical_document_id: str
    source_filename: str
    source_pages: list[int]
    type_id: str
    confidence: float
    document_date: Optional[str]
    title_short: Optional[str]
    classification_reasons: list[str]


def list_pending_reviews(registry: StateRegistry, person_folder: str) -> list[ReviewItem]:
    out = []
    for row in registry.logical_documents_for_person(person_folder):
        if row.resolution_status != "REVIEW_PENDING":
            continue
        src = registry.get(row.source_hash)
        out.append(
            ReviewItem(
                logical_document_id=row.logical_document_id,
                source_filename=src.source_filename if src else row.source_hash[:12],
                source_pages=list(row.source_pages),
                type_id=row.type_id,
                confidence=row.confidence,
                document_date=row.document_date,
                title_short=row.title_short,
                classification_reasons=list(row.classification_reasons),
            )
        )
    return out


def resolve_review(
    registry: StateRegistry,
    catalog: Catalog,
    logical_document_id: str,
    *,
    type_id: str,
    document_date: Optional[str],
    resolved_by: str = "operator",
) -> LogicalDocumentRow:
    """Validate rồi ghi quyết định của người vận hành. KHÔNG tự động ghi file."""
    if not catalog.is_valid_classification(type_id) or type_id == UNKNOWN:
        raise PipelineError(
            f"resolve-review: type_id '{type_id}' không hợp lệ (phải trong danh mục, khác UNKNOWN)."
        )
    if document_date is not None:
        from datetime import date

        try:
            date.fromisoformat(document_date)
        except ValueError as exc:
            raise PipelineError(f"resolve-review: document_date '{document_date}' sai định dạng yyyy-mm-dd.") from exc

    registry.resolve_review(
        logical_document_id, resolved_type_id=type_id, resolved_document_date=document_date,
        resolved_by=resolved_by,
    )
    row = registry.get_logical_document(logical_document_id)
    assert row is not None
    return row
