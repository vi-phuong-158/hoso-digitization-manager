"""Manifest truy ngược (AGENTS.md mục 8).

source file + source pages -> logical document -> type -> output filename.
Không chép toàn văn tài liệu vào manifest; chỉ tiêu đề ngắn do model trả về.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

from .catalog import Catalog
from .models import UNKNOWN, ClassifiedDocument
from .pdf_inventory import PersonInventory
from .qc import QCReport

MANIFEST_SCHEMA_VERSION = "1.0"


def document_entry(catalog: Catalog, doc: ClassifiedDocument) -> dict:
    c = doc.classification
    entry = {
        "source_file": doc.document.source_file,
        "source_pages": list(doc.document.source_pages),
        "page_roles": {str(k): v for k, v in doc.document.page_roles.items()},
        "type_id": c.type_id,
        "type_name_vi": catalog.name_vi(c.type_id) if c.type_id != UNKNOWN else None,
        "confidence": round(c.confidence, 4),
        "document_date": c.document_date,
        "date_confidence": round(c.date_confidence, 4),
        "title_short": c.title_short,
        "target_file": doc.target_file,
        "target_dir": doc.target_dir,
        "sequence": doc.sequence_index,
        "status": doc.final_status,
        "classification_status": doc.classification_status,
        "needs_review": doc.final_status == "REVIEW",
        "review_reason": (
            sorted(set(doc.classification_reasons) | set(doc.final_reasons)) or None
        )
        if doc.final_status == "REVIEW"
        else None,
        "segmentation_flags": doc.document.segmentation_flags or None,
        "segmentation_confidence": round(doc.document.segmentation_confidence, 4),
        "second_pass_used": doc.second_pass_used,
    }
    return entry


def build_manifest(
    catalog: Catalog,
    inventory: PersonInventory,
    documents: Sequence[ClassifiedDocument],
    qc: QCReport,
    *,
    mode: str,
    provider: dict,
    targets: Optional[dict] = None,
) -> dict:
    docs = [document_entry(catalog, d) for d in documents]
    auto = [d for d in docs if d["status"] == "AUTO"]
    review = [d for d in docs if d["status"] == "REVIEW"]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "catalog_schema_version": catalog.schema_version,
        "mode": mode,
        "provider": provider,
        "person_folder": inventory.person_folder,
        "sources": [s.as_dict() for s in inventory.sources],
        "documents": docs,
        "summary": {
            "source_files": len(inventory.sources),
            "source_pages": inventory.total_pages,
            "logical_documents": len(docs),
            "auto": len(auto),
            "review": len(review),
        },
        "qc": qc.as_dict(),
        "targets": targets or {},
    }


def normalize_for_compare(manifest: dict) -> dict:
    """Bỏ các trường phụ thuộc lần chạy để so sánh tính idempotent của dry-run."""
    clone = json.loads(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    clone.pop("mode", None)
    return clone


def save_manifest(manifest: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_manifest(path: Path) -> Optional[dict]:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
