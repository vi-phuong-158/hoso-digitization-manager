"""Điều phối Phase A -> G cho một thư mục hồ sơ (một người).

Mặc định dry-run. Apply chỉ chạy khi QC đạt.

Có hai đường đi:
  - `state_registry=None` (mặc định của hàm): xử lý TOÀN BỘ nguồn trong thư
    mục mỗi lần gọi, y hệt hành vi gốc trước khi có incremental processing.
    Toàn bộ test cũ dùng đường đi này, không đổi hành vi.
  - `state_registry=<StateRegistry>`: đường đi incremental. Trước khi đọc bất
    kỳ PDF nào, đối chiếu SHA-256 với registry; chỉ những nguồn NEW (hoặc được
    yêu cầu retry rõ ràng) mới được đưa cho provider đọc. Nguồn ALREADY_PROCESSED
    / DUPLICATE_SOURCE hoàn toàn không được chạm tới.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .catalog import Catalog, find_catalog_path, load_catalog
from .classifier import DEFAULT_POLICY, ConfidencePolicy, classify_document
from .incremental import IncrementalScan, scan_person_folder
from .manifest import build_manifest, load_manifest, save_manifest
from .models import MODE_APPLY, MODE_DRY_RUN, ClassifiedDocument, PipelineError
from .naming import DEFAULT_NAMING_POLICY, NamingPolicy, assign_names
from .pdf_inventory import PersonInventory, SourceFile, build_inventory
from .qc import QCReport, run_qc
from .segmenter import (
    DEFAULT_SEGMENTATION_CONFIG,
    SegmentationConfig,
    segment_source,
)
from .state import DB_FILENAME, StateRegistry
from .vision_adapter import DocumentVisionProvider, get_provider, validate_page_observation
from .writer import LEDGER_FILENAME, WriteResult, apply_documents, plan_targets, verify_outputs

# Re-export để tương thích ngược: `from app.pipeline import MODE_APPLY, MODE_DRY_RUN`.
__all__ = [
    "MODE_APPLY",
    "MODE_DRY_RUN",
    "Workspace",
    "PipelineResult",
    "process_person_folder",
]


@dataclass
class Workspace:
    root: Path

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def review(self) -> Path:
        return self.root / "review"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def state_db_path(self) -> Path:
        return self.state_dir / DB_FILENAME

    @classmethod
    def discover(cls, start: Optional[Path] = None) -> "Workspace":
        return cls(find_catalog_path(start).parent)


@dataclass
class PipelineResult:
    person_folder: str
    mode: str
    inventory: PersonInventory
    documents: list[ClassifiedDocument]
    qc: QCReport
    manifest: dict
    manifest_path: Optional[Path] = None
    write_result: Optional[WriteResult] = None
    notes: list[str] = field(default_factory=list)
    incremental: Optional[IncrementalScan] = None

    @property
    def status(self) -> str:
        """Trạng thái kết thúc theo RUNBOOK_ANTIGRAVITY.md (đúng 5 giá trị)."""
        if not self.qc.passed:
            return "BLOCKED_QC"
        if self.mode == MODE_APPLY:
            if self.write_result is not None and not self.write_result.ok:
                return "BLOCKED_RUNTIME"
            return "APPLY_PASS"
        if any(d.final_status == "REVIEW" for d in self.documents):
            return "REVIEW_REQUIRED"
        return "DRY_RUN_PASS"


def process_person_folder(
    folder: Path,
    *,
    mode: str = MODE_DRY_RUN,
    provider: Optional[DocumentVisionProvider] = None,
    provider_name: str = "fixture",
    provider_config: Optional[dict] = None,
    workspace: Optional[Workspace] = None,
    catalog: Optional[Catalog] = None,
    segmentation_config: SegmentationConfig = DEFAULT_SEGMENTATION_CONFIG,
    confidence_policy: ConfidencePolicy = DEFAULT_POLICY,
    naming_policy: NamingPolicy = DEFAULT_NAMING_POLICY,
    force: bool = False,
    write_manifest: bool = True,
    state_registry: Optional[StateRegistry] = None,
    retry_review: bool = False,
    retry_failed: bool = False,
) -> PipelineResult:
    if mode not in (MODE_DRY_RUN, MODE_APPLY):
        raise PipelineError(f"mode không hợp lệ: {mode!r}")

    folder = Path(folder)
    ws = workspace or Workspace.discover(folder)
    catalog = catalog or load_catalog()
    provider = provider or get_provider(provider_name, provider_config)

    # Phase A - Inventory (chỉ đọc).
    inventory = build_inventory(folder)

    output_dir = ws.output / inventory.person_folder
    review_dir = ws.review / inventory.person_folder

    if state_registry is not None:
        return _process_incremental(
            inventory=inventory,
            mode=mode,
            provider=provider,
            catalog=catalog,
            ws=ws,
            output_dir=output_dir,
            review_dir=review_dir,
            segmentation_config=segmentation_config,
            confidence_policy=confidence_policy,
            naming_policy=naming_policy,
            force=force,
            write_manifest=write_manifest,
            state_registry=state_registry,
            retry_review=retry_review,
            retry_failed=retry_failed,
        )

    # ================= Đường đi CŨ (không state-aware) =================
    # Xử lý TOÀN BỘ nguồn mỗi lần gọi - hành vi giữ nguyên 100% so với trước
    # khi có incremental processing. Mọi test cũ dùng nhánh này.
    documents: list[ClassifiedDocument] = []
    notes: list[str] = []
    for src in inventory.sources:
        documents.extend(
            _process_source(provider, catalog, src, segmentation_config, confidence_policy, notes)
        )

    assign_names(catalog, documents, output_dir, review_dir, naming_policy)

    write_result: Optional[WriteResult] = None
    output_problems: Optional[list[str]] = None
    targets = plan_targets(documents, inventory, output_dir, review_dir)
    targets_by_name = {v["target_file"]: v for v in targets.values()}

    if mode == MODE_APPLY:
        pre_qc = run_qc(catalog, inventory, documents, output_dir, review_dir)
        if not pre_qc.passed:
            manifest = build_manifest(
                catalog, inventory, documents, pre_qc, mode=mode,
                provider=provider.describe(), targets=targets_by_name,
            )
            path = _persist(manifest, ws, inventory.person_folder, mode) if write_manifest else None
            return PipelineResult(
                person_folder=inventory.person_folder, mode=mode, inventory=inventory,
                documents=documents, qc=pre_qc, manifest=manifest, manifest_path=path,
                notes=["QC không đạt -> không apply."],
            )
        previous = load_manifest(output_dir / LEDGER_FILENAME)
        write_result = apply_documents(
            documents, inventory, output_dir, review_dir, previous_ledger=previous, force=force
        )
        if write_result.ok:
            output_problems = verify_outputs(documents, output_dir, review_dir)
        else:
            notes.append("Có xung đột file đầu ra -> không ghi gì cả (fail-safe).")

    qc = run_qc(catalog, inventory, documents, output_dir, review_dir, output_problems)

    if write_result is not None:
        for name, sha in write_result.output_sha256.items():
            if name in targets_by_name:
                targets_by_name[name]["output_sha256"] = sha

    manifest = build_manifest(
        catalog, inventory, documents, qc, mode=mode,
        provider=provider.describe(), targets=targets_by_name,
    )
    if write_result is not None:
        manifest["write_result"] = write_result.as_dict()

    manifest_path = None
    if write_manifest:
        manifest_path = _persist(manifest, ws, inventory.person_folder, mode)
        if mode == MODE_APPLY and write_result is not None and write_result.ok:
            save_manifest(manifest, output_dir / LEDGER_FILENAME)

    return PipelineResult(
        person_folder=inventory.person_folder, mode=mode, inventory=inventory,
        documents=documents, qc=qc, manifest=manifest, manifest_path=manifest_path,
        write_result=write_result, notes=notes,
    )


def _process_source(
    provider: DocumentVisionProvider,
    catalog: Catalog,
    src: SourceFile,
    segmentation_config: SegmentationConfig,
    confidence_policy: ConfidencePolicy,
    notes: list[str],
) -> list[ClassifiedDocument]:
    """Phase B->D cho MỘT file nguồn. Dùng chung bởi cả hai đường đi."""
    page_numbers = list(range(1, src.pages + 1))
    observations = provider.analyze_pages(src.path, page_numbers)
    for obs in observations:
        validate_page_observation(obs, catalog, where=f"{src.name}/trang {obs.page_number}")
    by_page = {o.page_number: o for o in observations}

    # Phase C - Segmentation (deterministic, do code local quyết định).
    logical_docs = segment_source(src, observations, segmentation_config)

    # Đối chiếu chéo với cách gom trang do Agent đề xuất (nếu có).
    # Lệch nhau = không chắc -> REVIEW; không bên nào được mặc định là đúng.
    proposed = provider.proposed_documents(src.path)
    if proposed is not None:
        mismatches = cross_check_segmentation(logical_docs, proposed)
        if mismatches:
            notes.append(
                f"{src.name}: segmenter local và đề xuất của Agent lệch nhau ở "
                f"{len(mismatches)} nhóm trang -> đưa REVIEW."
            )

    # Phase D - Classification (đọc toàn bộ logical document).
    out: list[ClassifiedDocument] = []
    for ldoc in logical_docs:
        doc_obs = [by_page[p] for p in ldoc.source_pages]
        out.append(
            classify_document(provider, catalog, src.path, ldoc, doc_obs, policy=confidence_policy)
        )
    return out


def _process_incremental(
    *,
    inventory: PersonInventory,
    mode: str,
    provider: DocumentVisionProvider,
    catalog: Catalog,
    ws: Workspace,
    output_dir: Path,
    review_dir: Path,
    segmentation_config: SegmentationConfig,
    confidence_policy: ConfidencePolicy,
    naming_policy: NamingPolicy,
    force: bool,
    write_manifest: bool,
    state_registry: StateRegistry,
    retry_review: bool,
    retry_failed: bool,
) -> PipelineResult:
    incremental = scan_person_folder(
        inventory, state_registry, mode=mode, retry_review=retry_review, retry_failed=retry_failed,
        output_dir=output_dir, review_dir=review_dir,
    )
    sources_to_process = incremental.to_process

    # PROCESSING phải được commit TRƯỚC khi đưa PDF cho provider đọc, để lần
    # chạy sau phát hiện được nếu tiến trình bị crash giữa chừng (INTERRUPTED).
    for d in incremental.decisions:
        if d.will_process:
            state_registry.begin_processing(
                source_hash=d.source.sha256,
                source_filename=d.source.name,
                source_relative_path=f"{inventory.person_folder}/{d.source.name}",
                person_folder=inventory.person_folder,
                page_count=d.source.pages,
            )

    notes: list[str] = []
    documents: list[ClassifiedDocument] = []
    failed: dict[str, str] = {}  # source_hash -> lỗi

    for src in sources_to_process:
        try:
            documents.extend(
                _process_source(provider, catalog, src, segmentation_config, confidence_policy, notes)
            )
        except Exception as exc:  # cô lập lỗi theo từng nguồn - 1 file hỏng không sập cả lượt
            failed[src.sha256] = str(exc)
            notes.append(f"{src.name}: LỖI xử lý -> {exc}")

    for h, err in failed.items():
        state_registry.mark_failed(h, error=err)

    ok_sources = [s for s in sources_to_process if s.sha256 not in failed]

    if not ok_sources:
        empty_qc = QCReport()
        manifest = build_manifest(
            catalog, inventory, [], empty_qc, mode=mode, provider=provider.describe(), targets={}
        )
        manifest["incremental"] = incremental.as_dict()
        if failed:
            manifest["failed_this_run"] = [
                {"source_file": s.name, "error": failed[s.sha256]}
                for s in sources_to_process if s.sha256 in failed
            ]
        manifest_path = _persist(manifest, ws, inventory.person_folder, mode) if write_manifest else None
        return PipelineResult(
            person_folder=inventory.person_folder, mode=mode, inventory=inventory,
            documents=[], qc=empty_qc, manifest=manifest, manifest_path=manifest_path,
            notes=notes or ["Không có nguồn mới cần xử lý."], incremental=incremental,
        )

    assign_names(catalog, documents, output_dir, review_dir, naming_policy)

    write_result: Optional[WriteResult] = None
    output_problems: Optional[list[str]] = None
    targets = plan_targets(documents, inventory, output_dir, review_dir)
    targets_by_name = {v["target_file"]: v for v in targets.values()}
    ledger_path = output_dir / LEDGER_FILENAME

    if mode == MODE_APPLY:
        pre_qc = run_qc(catalog, inventory, documents, output_dir, review_dir, sources=ok_sources)
        if not pre_qc.passed:
            for s in ok_sources:
                state_registry.mark_failed(
                    s.sha256,
                    error="QC (trước khi ghi) không đạt: "
                    + "; ".join(f"{c.name}: {c.detail}" for c in pre_qc.failures),
                )
            manifest = build_manifest(
                catalog, inventory, documents, pre_qc, mode=mode,
                provider=provider.describe(), targets=targets_by_name,
            )
            manifest["incremental"] = incremental.as_dict()
            path = _persist(manifest, ws, inventory.person_folder, mode) if write_manifest else None
            return PipelineResult(
                person_folder=inventory.person_folder, mode=mode, inventory=inventory,
                documents=documents, qc=pre_qc, manifest=manifest, manifest_path=path,
                notes=notes + ["QC không đạt -> không apply."], incremental=incremental,
            )

        previous = load_manifest(ledger_path)
        write_result = apply_documents(
            documents, inventory, output_dir, review_dir, previous_ledger=previous, force=force
        )
        if write_result.ok:
            output_problems = verify_outputs(documents, output_dir, review_dir)
        else:
            notes.append("Có xung đột file đầu ra -> không ghi gì cả (fail-safe).")
            for s in ok_sources:
                state_registry.mark_failed(
                    s.sha256,
                    error="Xung đột file đầu ra khi apply: " + "; ".join(write_result.conflicts),
                )

    qc = run_qc(catalog, inventory, documents, output_dir, review_dir, output_problems, sources=ok_sources)

    if write_result is not None:
        for name, sha in write_result.output_sha256.items():
            if name in targets_by_name:
                targets_by_name[name]["output_sha256"] = sha

    manifest = build_manifest(
        catalog, inventory, documents, qc, mode=mode,
        provider=provider.describe(), targets=targets_by_name,
    )
    if write_result is not None:
        manifest["write_result"] = write_result.as_dict()
    manifest["incremental"] = incremental.as_dict()
    if failed:
        manifest["failed_this_run"] = [{"source_file": name, "error": err} for name, err in (
            (s.name, failed[s.sha256]) for s in sources_to_process if s.sha256 in failed
        )]

    manifest_path = None
    if write_manifest:
        manifest_path = _persist(manifest, ws, inventory.person_folder, mode)
        if mode == MODE_APPLY and write_result is not None and write_result.ok:
            merged = _merge_ledger(load_manifest(ledger_path), manifest, {s.name for s in ok_sources})
            save_manifest(merged, ledger_path)

    _apply_state_transitions(
        mode=mode, qc=qc, write_result=write_result, documents=documents,
        ok_sources=ok_sources, state_registry=state_registry, ledger_path=ledger_path,
        manifest_path=manifest_path,
    )

    return PipelineResult(
        person_folder=inventory.person_folder, mode=mode, inventory=inventory, documents=documents,
        qc=qc, manifest=manifest, manifest_path=manifest_path, write_result=write_result,
        notes=notes, incremental=incremental,
    )


def _apply_state_transitions(
    *,
    mode: str,
    qc: QCReport,
    write_result: Optional[WriteResult],
    documents: list[ClassifiedDocument],
    ok_sources: list[SourceFile],
    state_registry: StateRegistry,
    ledger_path: Path,
    manifest_path: Optional[Path],
) -> None:
    by_name = {s.name: s for s in ok_sources}

    if mode == MODE_APPLY:
        if write_result is not None and write_result.ok and qc.passed:
            counts: dict[str, int] = {}
            for d in documents:
                counts[d.document.source_file] = counts.get(d.document.source_file, 0) + 1
            for name, count in counts.items():
                s = by_name.get(name)
                if s is not None:
                    state_registry.commit_processed(
                        s.sha256, logical_document_count=count, manifest_path=str(ledger_path)
                    )
        elif write_result is not None and not write_result.ok:
            pass  # đã mark_failed ngay khi phát hiện xung đột (fail-safe)
        elif not qc.passed:
            for s in ok_sources:
                state_registry.mark_failed(s.sha256, error="QC (sau khi ghi) không đạt.")
        return

    # DRY-RUN.
    if not qc.passed:
        for s in ok_sources:
            state_registry.mark_failed(
                s.sha256,
                error="QC (dry-run) không đạt: " + "; ".join(f"{c.name}: {c.detail}" for c in qc.failures),
            )
        return

    per_source: dict[str, list[ClassifiedDocument]] = {}
    for d in documents:
        per_source.setdefault(d.document.source_file, []).append(d)
    for name, docs in per_source.items():
        s = by_name.get(name)
        if s is None:
            continue
        if any(d.final_status == "REVIEW" for d in docs):
            state_registry.mark_review_required(
                s.sha256,
                logical_document_count=len(docs),
                manifest_path=str(manifest_path) if manifest_path else None,
            )
        else:
            # Dry-run sạch (không có gì cần review) -> trở về NEW; không bịa
            # thêm status thứ 6 ngoài 5 status bắt buộc.
            state_registry.release(s.sha256)


def _merge_ledger(previous: Optional[dict], new_manifest: dict, processed_source_names: set[str]) -> dict:
    """Gộp ledger cũ (trừ các nguồn vừa xử lý lại) với kết quả lượt này.

    Đảm bảo `output/<người>/_manifest.json` luôn là bản ghi TRUY VẾT ĐƯỢC đầy
    đủ (AGENTS.md mục 8), không bị lượt chạy incremental sau ghi đè mất phần
    của các nguồn đã xử lý ở lượt trước.
    """
    if previous is None:
        return new_manifest
    old_docs = [
        d for d in previous.get("documents", []) if d.get("source_file") not in processed_source_names
    ]
    merged_docs = old_docs + list(new_manifest.get("documents", []))
    merged_targets = {**previous.get("targets", {}), **new_manifest.get("targets", {})}
    merged = dict(new_manifest)
    merged["documents"] = merged_docs
    merged["targets"] = merged_targets
    sources = new_manifest.get("sources", [])
    merged["summary"] = {
        "source_files": len(sources),
        "source_pages": sum(s.get("pages", 0) for s in sources),
        "logical_documents": len(merged_docs),
        "auto": sum(1 for d in merged_docs if d.get("status") == "AUTO"),
        "review": sum(1 for d in merged_docs if d.get("status") == "REVIEW"),
    }
    return merged


FLAG_AGENT_SEGMENTATION_MISMATCH = "AGENT_SEGMENTATION_MISMATCH"


def cross_check_segmentation(logical_docs: list, proposed: list[list[int]]) -> list:
    """Gắn cờ những logical document mà Agent gom khác segmenter local.

    Trả về danh sách các document bị gắn cờ (sửa tại chỗ `segmentation_flags`).
    """
    proposed_set = {tuple(g) for g in proposed}
    flagged = []
    for d in logical_docs:
        if tuple(d.source_pages) not in proposed_set:
            d.segmentation_flags = sorted(
                set(d.segmentation_flags) | {FLAG_AGENT_SEGMENTATION_MISMATCH}
            )
            flagged.append(d)
    return flagged


def _persist(manifest: dict, ws: Workspace, person: str, mode: str) -> Path:
    name = "manifest.dryrun.json" if mode == MODE_DRY_RUN else "manifest.apply.json"
    return save_manifest(manifest, ws.logs / person / name)
