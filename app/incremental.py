"""Phase A+ — Incremental scan: đối chiếu inventory hiện tại với state registry.

Quyết định file nào Agent cần đọc (NEW) và file nào SKIP. Module này CHỈ đọc
SHA-256 (đã có sẵn từ pdf_inventory) và tra registry — KHÔNG mở nội dung PDF,
KHÔNG gọi provider. An toàn để dùng cho lệnh `status` (read-only, không mutate
registry).

Khóa nhận diện là SHA-256, không phải filename:
  - cùng hash, khác tên/khác đường dẫn -> vẫn là cùng một nguồn, không đọc lại.
  - cùng tên, khác hash -> nguồn MỚI (NEW_SOURCE_VERSION), phải xử lý.
  - nhiều file cùng hash trong một lần scan -> chỉ 1 bản canonical (tên nhỏ
    nhất theo alphabet để deterministic), các bản còn lại là DUPLICATE_SOURCE
    và không bao giờ được xử lý.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .manifest import load_manifest
from .models import MODE_APPLY
from .pdf_inventory import PersonInventory, SourceFile
from .state import (
    STATUS_FAILED,
    STATUS_PROCESSED,
    STATUS_PROCESSING,
    STATUS_REVIEW_REQUIRED,
    SourceState,
    StateRegistry,
)

DECISION_NEW = "NEW"
DECISION_ALREADY_PROCESSED = "ALREADY_PROCESSED"
DECISION_REVIEW_PENDING = "REVIEW_PENDING"
DECISION_FAILED_PREVIOUSLY = "FAILED_PREVIOUSLY"
DECISION_INTERRUPTED = "INTERRUPTED"
DECISION_DUPLICATE_SOURCE = "DUPLICATE_SOURCE"

_STATUS_TO_DECISION = {
    STATUS_PROCESSING: DECISION_INTERRUPTED,
    STATUS_PROCESSED: DECISION_ALREADY_PROCESSED,
    STATUS_REVIEW_REQUIRED: DECISION_REVIEW_PENDING,
    STATUS_FAILED: DECISION_FAILED_PREVIOUSLY,
}

ALL_DECISIONS = (
    DECISION_NEW,
    DECISION_ALREADY_PROCESSED,
    DECISION_REVIEW_PENDING,
    DECISION_FAILED_PREVIOUSLY,
    DECISION_INTERRUPTED,
    DECISION_DUPLICATE_SOURCE,
)


@dataclass
class SourceDecision:
    source: SourceFile
    decision: str
    record: Optional[SourceState] = None
    duplicate_of_hash: Optional[str] = None
    duplicate_of_name: Optional[str] = None
    will_process: bool = False
    output_mismatch: bool = False
    output_mismatch_detail: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "source_file": self.source.name,
            "decision": self.decision,
            "will_process": self.will_process,
            "output_mismatch": self.output_mismatch,
            "output_mismatch_detail": self.output_mismatch_detail,
            "duplicate_of": self.duplicate_of_name,
        }


@dataclass
class IncrementalScan:
    person_folder: str
    decisions: list[SourceDecision] = field(default_factory=list)

    @property
    def to_process(self) -> list[SourceFile]:
        return [d.source for d in self.decisions if d.will_process]

    def counts(self) -> dict[str, int]:
        out = {d: 0 for d in ALL_DECISIONS}
        for d in self.decisions:
            out[d.decision] += 1
        return out

    def as_dict(self) -> dict:
        return {
            "person_folder": self.person_folder,
            "total_pdf": len(self.decisions),
            "counts": self.counts(),
            "sources": [d.as_dict() for d in self.decisions],
        }

    def summary_text(self) -> str:
        c = self.counts()
        lines = [
            f"HỒ SƠ: {self.person_folder}",
            "",
            f"PDF hiện có: {len(self.decisions)}",
            "",
            f"Đã xử lý trước: {c[DECISION_ALREADY_PROCESSED]} -> SKIP",
            f"Mới bổ sung: {c[DECISION_NEW]}",
        ]
        if c[DECISION_REVIEW_PENDING]:
            lines.append(f"Đang chờ review: {c[DECISION_REVIEW_PENDING]}")
        if c[DECISION_FAILED_PREVIOUSLY]:
            lines.append(f"Lỗi cũ: {c[DECISION_FAILED_PREVIOUSLY]}")
        if c[DECISION_INTERRUPTED]:
            lines.append(f"Bị gián đoạn lần trước (interrupted): {c[DECISION_INTERRUPTED]}")
        if c[DECISION_DUPLICATE_SOURCE]:
            lines.append(f"Trùng nội dung (duplicate): {c[DECISION_DUPLICATE_SOURCE]}")
        mismatches = [d for d in self.decisions if d.output_mismatch]
        if mismatches:
            lines.append("")
            lines.append("CẢNH BÁO STATE_OUTPUT_MISMATCH (state nói PROCESSED nhưng thiếu file):")
            for d in mismatches:
                lines.append(f"  - {d.source.name}: {d.output_mismatch_detail}")
        return "\n".join(lines)


def _check_output_mismatch(
    record: SourceState, source: SourceFile, output_dir: Path, review_dir: Path
) -> tuple[bool, Optional[str]]:
    if not record.manifest_path:
        return False, None
    manifest = load_manifest(Path(record.manifest_path))
    if manifest is None:
        return True, f"không đọc/parse được ledger đã ghi nhận: {record.manifest_path}"
    missing = []
    for entry in manifest.get("documents", []):
        if entry.get("source_file") != source.name:
            continue
        base = output_dir if entry.get("target_dir") == "output" else review_dir
        target = base / str(entry.get("target_file"))
        if not target.is_file():
            missing.append(entry.get("target_file"))
    if missing:
        return True, f"thiếu {len(missing)} file đầu ra đã ghi nhận trước đó: {missing}"
    return False, None


def scan_person_folder(
    inventory: PersonInventory,
    registry: StateRegistry,
    *,
    mode: str,
    retry_review: bool = False,
    retry_failed: bool = False,
    output_dir: Optional[Path] = None,
    review_dir: Optional[Path] = None,
) -> IncrementalScan:
    by_hash: dict[str, list[SourceFile]] = {}
    for s in inventory.sources:
        by_hash.setdefault(s.sha256, []).append(s)

    decisions: list[SourceDecision] = []
    for h, files in by_hash.items():
        # Thứ tự deterministic: không phụ thuộc thứ tự filesystem/scan.
        files_sorted = sorted(files, key=lambda f: f.name.casefold())
        canonical = files_sorted[0]
        record = registry.get(h)

        for f in files_sorted:
            if f is not canonical:
                decisions.append(
                    SourceDecision(
                        source=f,
                        decision=DECISION_DUPLICATE_SOURCE,
                        record=record,
                        duplicate_of_hash=h,
                        duplicate_of_name=canonical.name,
                        will_process=False,
                    )
                )
                continue

            if record is None:
                decisions.append(SourceDecision(source=f, decision=DECISION_NEW, will_process=True))
                continue

            decision = _STATUS_TO_DECISION[record.status]
            will_process = False
            if decision == DECISION_REVIEW_PENDING:
                # Apply là hành động "làm thật": phải xử lý để thực sự ghi file
                # review/ ra đĩa. Dry-run thường thì SKIP, trừ khi có --retry-review.
                will_process = retry_review or (mode == MODE_APPLY)
            elif decision in (DECISION_FAILED_PREVIOUSLY, DECISION_INTERRUPTED):
                # Lỗi kỹ thuật/gián đoạn luôn cần người vận hành yêu cầu rõ,
                # kể cả khi đang apply — không tự động retry vô hạn.
                will_process = retry_failed
            # DECISION_ALREADY_PROCESSED: will_process luôn False, không có cờ nào bật lại.

            mismatch, detail = False, None
            if (
                decision == DECISION_ALREADY_PROCESSED
                and output_dir is not None
                and review_dir is not None
            ):
                mismatch, detail = _check_output_mismatch(record, f, output_dir, review_dir)

            decisions.append(
                SourceDecision(
                    source=f,
                    decision=decision,
                    record=record,
                    will_process=will_process,
                    output_mismatch=mismatch,
                    output_mismatch_detail=detail,
                )
            )

    # Giữ đúng thứ tự ổn định của inventory (đã sort theo tên trong pdf_inventory).
    order = {id(s): i for i, s in enumerate(inventory.sources)}
    decisions.sort(key=lambda d: order[id(d.source)])
    return IncrementalScan(person_folder=inventory.person_folder, decisions=decisions)
