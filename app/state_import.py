"""Migration: nạp lại state registry từ manifest/output đã có sẵn (Phase 27).

Dùng khi một hồ sơ đã được apply THÀNH CÔNG trước khi state registry tồn tại
(ví dụ bộ HAI). Lệnh này KHÔNG suy đoán — chỉ đánh PROCESSED khi bằng chứng đầy
đủ: ledger `output/<người>/_manifest.json` có entry cho đúng nguồn (khớp
SHA-256 + số trang) VÀ mọi target_file của nguồn đó thực sự tồn tại trên đĩa.

Thiếu bất kỳ bằng chứng nào -> STATE_IMPORT_REVIEW_REQUIRED, không đụng registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .manifest import load_manifest
from .pdf_inventory import PersonInventory, build_inventory
from .pipeline import Workspace
from .state import StateRegistry

OUTCOME_IMPORTED = "IMPORTED"
OUTCOME_ALREADY_IN_REGISTRY = "ALREADY_IN_REGISTRY"
OUTCOME_REVIEW_REQUIRED = "STATE_IMPORT_REVIEW_REQUIRED"


@dataclass
class ImportOutcome:
    source_file: str
    outcome: str
    detail: str = ""


@dataclass
class ImportReport:
    person_folder: str
    outcomes: list[ImportOutcome] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [f"IMPORT STATE: {self.person_folder}", ""]
        for o in self.outcomes:
            lines.append(f"  [{o.outcome}] {o.source_file}" + (f" - {o.detail}" if o.detail else ""))
        return "\n".join(lines)


def import_person_folder(
    folder: Path, registry: StateRegistry, *, workspace: Optional[Workspace] = None
) -> ImportReport:
    folder = Path(folder)
    ws = workspace or Workspace.discover(folder)
    inventory: PersonInventory = build_inventory(folder)

    output_dir = ws.output / inventory.person_folder
    review_dir = ws.review / inventory.person_folder
    ledger_path = output_dir / "_manifest.json"
    ledger = load_manifest(ledger_path)

    report = ImportReport(person_folder=inventory.person_folder)

    if ledger is None:
        for src in inventory.sources:
            report.outcomes.append(
                ImportOutcome(src.name, OUTCOME_REVIEW_REQUIRED, f"chưa có ledger {ledger_path}")
            )
        return report

    ledger_sources = {s.get("file"): s for s in ledger.get("sources", [])}
    ledger_docs_by_source: dict[str, list[dict]] = {}
    for d in ledger.get("documents", []):
        ledger_docs_by_source.setdefault(d.get("source_file"), []).append(d)

    for src in inventory.sources:
        existing = registry.get(src.sha256)
        if existing is not None:
            report.outcomes.append(
                ImportOutcome(src.name, OUTCOME_ALREADY_IN_REGISTRY, f"đã có trong registry ({existing.status})")
            )
            continue

        ledger_src = ledger_sources.get(src.name)
        docs = ledger_docs_by_source.get(src.name)
        if ledger_src is None or not docs:
            # Không có bằng chứng nào -> không phải lỗi, chỉ là chưa từng apply.
            report.outcomes.append(
                ImportOutcome(src.name, OUTCOME_REVIEW_REQUIRED, "không có entry trong ledger; có thể chưa từng apply")
            )
            continue

        if ledger_src.get("sha256") != src.sha256:
            report.outcomes.append(
                ImportOutcome(src.name, OUTCOME_REVIEW_REQUIRED, "SHA-256 trong ledger không khớp file hiện tại")
            )
            continue
        if ledger_src.get("pages") != src.pages:
            report.outcomes.append(
                ImportOutcome(src.name, OUTCOME_REVIEW_REQUIRED, "số trang trong ledger không khớp file hiện tại")
            )
            continue

        missing = []
        for entry in docs:
            base = output_dir if entry.get("target_dir") == "output" else review_dir
            target = base / str(entry.get("target_file"))
            if not target.is_file():
                missing.append(entry.get("target_file"))
        if missing:
            report.outcomes.append(
                ImportOutcome(src.name, OUTCOME_REVIEW_REQUIRED, f"thiếu file đầu ra: {missing}")
            )
            continue

        registry.import_processed(
            source_hash=src.sha256,
            source_filename=src.name,
            source_relative_path=f"{inventory.person_folder}/{src.name}",
            person_folder=inventory.person_folder,
            page_count=src.pages,
            logical_document_count=len(docs),
            manifest_path=str(ledger_path),
        )
        report.outcomes.append(
            ImportOutcome(src.name, OUTCOME_IMPORTED, f"{len(docs)} logical document, ledger {ledger_path.name}")
        )

    return report
