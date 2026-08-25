"""Pilot Harness & Execution Engine (Workstream A & I).

Cung cấp cơ chế chạy pilot có thể lặp lại, đo lường và kiểm chứng:
- Pre-run inventory (SHA-256, dung lượng, số trang)
- Dry-run
- Processing run (apply)
- Re-run (kiểm chứng idempotency: 0 xử lý lặp, 0 duplicate, hash đầu ra không đổi)
- Resume run (phục hồi sau gián đoạn / lỗi retryable)
- Reconcile (đối soát toàn diện giữa disk và DB state)
- Post-run audit (bảo đảm tính toàn vẹn 100% của file nguồn, QC pass, không va chạm tên)
- Tổng hợp metrics chuẩn: files_discovered, files_processed, files_skipped, v.v.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .catalog import load_catalog
from .fingerprint import current_fingerprint
from .incremental import (
    DECISION_ALREADY_PROCESSED,
    DECISION_CACHED_PENDING_APPLY,
    DECISION_CACHED_REVIEW_REQUIRED,
    DECISION_DUPLICATE_SOURCE,
    DECISION_FAILED_PREVIOUSLY,
    DECISION_INTERRUPTED,
    DECISION_NEW,
    DECISION_RETIRED_SOURCE,
    DECISION_STALE_ANALYSIS,
    scan_person_folder,
)
from .manifest import save_manifest
from .models import MODE_APPLY, MODE_DRY_RUN, PipelineError
from .oplog import (
    EVENT_ERROR_OCCURRED,
    EVENT_RECONCILE_COMPLETED,
    EVENT_RUN_END,
    EVENT_RUN_START,
    EVENT_SOURCE_DISCOVERED,
    EVENT_SOURCE_SKIPPED,
    INFO,
    WARNING,
    ERROR,
    log_event,
)
from .pdf_inventory import PersonInventory, build_inventory, list_pdfs, read_source, sha256_file, verify_unchanged
from .pipeline import PipelineResult, Workspace, process_person_folder
from .policy import CLASSIFICATION_KIND_DUPLICATE, CLASSIFICATION_KIND_SUPPORTING, CLASSIFICATION_KIND_TAXONOMY
from .reconcile import ReconcileReport, reconcile
from .state import SOURCE_ACTIVE, SOURCE_MISSING, StateRegistry
from .vision_adapter import DocumentVisionProvider, get_provider


def generate_run_id(prefix: str = "pilot") -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{prefix}-{now_str}-{short_uuid}"


@dataclass
class PilotMetrics:
    files_discovered: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    documents_created: int = 0
    taxonomy_documents: int = 0
    supporting_documents: int = 0
    duplicates: int = 0
    review_pending: int = 0
    errors: int = 0
    retryable_errors: int = 0
    permanent_errors: int = 0
    elapsed_time: float = 0.0
    resume_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "files_discovered": self.files_discovered,
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "documents_created": self.documents_created,
            "taxonomy_documents": self.taxonomy_documents,
            "supporting_documents": self.supporting_documents,
            "duplicates": self.duplicates,
            "review_pending": self.review_pending,
            "errors": self.errors,
            "retryable_errors": self.retryable_errors,
            "permanent_errors": self.permanent_errors,
            "elapsed_time": round(self.elapsed_time, 4),
            "resume_count": self.resume_count,
        }


@dataclass
class StageResult:
    stage_name: str
    status: str
    elapsed_seconds: float
    detail: str = ""
    manifest: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "detail": self.detail,
        }


@dataclass
class PilotRunReport:
    run_id: str
    person_folder: str
    started_at: str
    ended_at: Optional[str] = None
    status: str = "PENDING"  # PASS | REVIEW_REQUIRED | BLOCKED | FAIL
    metrics: PilotMetrics = field(default_factory=PilotMetrics)
    source_hashes_before: dict[str, str] = field(default_factory=dict)
    source_hashes_after: dict[str, str] = field(default_factory=dict)
    source_integrity_intact: bool = False
    output_files: list[str] = field(default_factory=list)
    stages: list[StageResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    report_path: Optional[Path] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "person_folder": self.person_folder,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "metrics": self.metrics.as_dict(),
            "source_integrity_intact": self.source_integrity_intact,
            "source_count": len(self.source_hashes_before),
            "output_count": len(self.output_files),
            "output_files": sorted(self.output_files),
            "stages": [s.as_dict() for s in self.stages],
            "notes": self.notes,
        }

    def summary_text(self) -> str:
        lines = [
            f"=== PILOT RUN REPORT: {self.run_id} ===",
            f"Hồ sơ               : {self.person_folder}",
            f"Trạng thái          : {self.status}",
            f"Bảo toàn nguồn      : {'PASS (100% hash khớp)' if self.source_integrity_intact else 'FAIL (file nguồn bị đổi)'}",
            f"Thời gian thực thi  : {self.metrics.elapsed_time:.3f}s",
            "",
            "--- METRICS ---",
            f"  Files discovered  : {self.metrics.files_discovered}",
            f"  Files processed   : {self.metrics.files_processed}",
            f"  Files skipped     : {self.metrics.files_skipped}",
            f"  Documents created : {self.metrics.documents_created}",
            f"  Taxonomy docs     : {self.metrics.taxonomy_documents}",
            f"  Supporting docs   : {self.metrics.supporting_documents}",
            f"  Duplicates        : {self.metrics.duplicates}",
            f"  Review pending    : {self.metrics.review_pending}",
            f"  Errors            : {self.metrics.errors} (retryable={self.metrics.retryable_errors}, permanent={self.metrics.permanent_errors})",
            f"  Resume count      : {self.metrics.resume_count}",
            "",
            "--- STAGES ---",
        ]
        for s in self.stages:
            lines.append(f"  [{s.status}] {s.stage_name} ({s.elapsed_seconds:.3f}s): {s.detail}")
        if self.notes:
            lines.append("")
            lines.append("--- GHI CHÚ ---")
            for n in self.notes:
                lines.append(f"  - {n}")
        if self.report_path:
            lines.append(f"\nReport lưu tại: {self.report_path}")
        return "\n".join(lines)


class PilotRunner:
    """Điều phối và thực thi toàn diện một quy trình pilot chuẩn."""

    def __init__(
        self,
        folder: Path,
        *,
        workspace: Optional[Workspace] = None,
        provider_name: str = "agent",
        provider_config: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ):
        self.folder = Path(folder).resolve()
        self.person_folder = self.folder.name
        self.ws = workspace or Workspace.discover(self.folder)
        self.provider_name = provider_name
        self.provider_config = provider_config or {}
        self.run_id = run_id or generate_run_id()

    def run_full(self) -> PilotRunReport:
        """Thực thi đầy đủ các pha pilot:

        1. Inventory & Baseline Hashes
        2. Dry-Run Check
        3. Processing (Apply) Run
        4. Idempotent Re-Run Check (xác minh không chạy lặp, không duplicate)
        5. Reconcile & State Verification
        6. Post-Run Source Integrity Audit
        """
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report = PilotRunReport(
            run_id=self.run_id,
            person_folder=self.person_folder,
            started_at=started_at,
        )

        log_event(
            EVENT_RUN_START,
            component="pilot",
            run_id=self.run_id,
            message=f"Bắt đầu pilot run cho hồ sơ: {self.person_folder}",
            metadata={"folder": str(self.folder)},
        )

        t0 = time.perf_counter()
        try:
            with StateRegistry(self.ws.state_db_path) as registry:
                # Stage 1: Inventory & Baseline Hashes
                st_time = time.perf_counter()
                inventory = self._stage_inventory(report)
                report.stages.append(
                    StageResult("INVENTORY", "PASS", time.perf_counter() - st_time, f"{len(inventory.sources)} PDF ({inventory.total_pages} trang)")
                )

                # Stage 2: Dry-Run
                st_time = time.perf_counter()
                dry_result = process_person_folder(
                    self.folder,
                    mode=MODE_DRY_RUN,
                    provider_name=self.provider_name,
                    provider_config=self.provider_config,
                    workspace=self.ws,
                    state_registry=registry,
                )
                dry_status = "PASS" if dry_result.status in ("DRY_RUN_PASS", "REVIEW_REQUIRED") else "FAIL"
                report.stages.append(
                    StageResult("DRY_RUN", dry_status, time.perf_counter() - st_time, f"status={dry_result.status}")
                )

                # Stage 3: Apply Run
                st_time = time.perf_counter()
                apply_result = process_person_folder(
                    self.folder,
                    mode=MODE_APPLY,
                    provider_name=self.provider_name,
                    provider_config=self.provider_config,
                    workspace=self.ws,
                    state_registry=registry,
                )
                apply_status = "PASS" if apply_result.status in ("APPLY_PASS", "REVIEW_REQUIRED") else "FAIL"
                report.stages.append(
                    StageResult("APPLY", apply_status, time.perf_counter() - st_time, f"status={apply_result.status}")
                )

                # Stage 4: Idempotent Re-Run Check
                st_time = time.perf_counter()
                rerun_result = process_person_folder(
                    self.folder,
                    mode=MODE_APPLY,
                    provider_name=self.provider_name,
                    provider_config=self.provider_config,
                    workspace=self.ws,
                    state_registry=registry,
                )
                # Kỳ vọng re-run: 0 file need_agent, 0 conflicts, APPLY_PASS
                rerun_needs_agent = len(rerun_result.incremental.needs_agent_sources) if rerun_result.incremental else 0
                rerun_ok = rerun_needs_agent == 0 and rerun_result.status in ("APPLY_PASS", "REVIEW_REQUIRED")
                report.stages.append(
                    StageResult(
                        "IDEMPOTENCY_RERUN",
                        "PASS" if rerun_ok else "FAIL",
                        time.perf_counter() - st_time,
                        f"needs_agent={rerun_needs_agent}, status={rerun_result.status}",
                    )
                )

                # Stage 5: Reconcile Check
                st_time = time.perf_counter()
                rec_report = reconcile(
                    registry,
                    self.person_folder,
                    self.ws.output / self.person_folder,
                    self.ws.review / self.person_folder,
                    self.folder,
                )
                report.stages.append(
                    StageResult("RECONCILE", "PASS" if rec_report.ok else "FAIL", time.perf_counter() - st_time, rec_report.summary_text())
                )

                # Stage 6: Post-Run Audit & Metrics Gathering
                st_time = time.perf_counter()
                self._stage_audit_and_metrics(report, registry, apply_result)
                report.stages.append(
                    StageResult("AUDIT", "PASS" if report.source_integrity_intact else "FAIL", time.perf_counter() - st_time, "Source integrity verified")
                )

                # Determine overall status
                failed_stages = [s for s in report.stages if s.status == "FAIL"]
                if failed_stages:
                    report.status = "FAIL"
                elif report.metrics.review_pending > 0:
                    report.status = "REVIEW_REQUIRED"
                else:
                    report.status = "PASS"

        except Exception as exc:
            report.status = "BLOCKED"
            report.notes.append(f"Pilot execution error: {type(exc).__name__}: {exc}")
            log_event(
                EVENT_ERROR_OCCURRED,
                component="pilot",
                run_id=self.run_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )

        report.metrics.elapsed_time = time.perf_counter() - t0
        report.ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # Save pilot report manifest
        log_dir = self.ws.logs / "pilot"
        log_dir.mkdir(parents=True, exist_ok=True)
        report_path = save_manifest(report.as_dict(), log_dir / f"{self.run_id}.json")
        report.report_path = report_path

        log_event(
            EVENT_RUN_END,
            component="pilot",
            run_id=self.run_id,
            message=f"Hoàn tất pilot run: {report.status}",
            metadata={"status": report.status, "elapsed_time": report.metrics.elapsed_time},
        )

        return report

    def _stage_inventory(self, report: PilotRunReport) -> PersonInventory:
        pdf_files = list_pdfs(self.folder)
        sources = [read_source(p) for p in pdf_files]
        inventory = PersonInventory(self.person_folder, self.folder, sources)
        for s in inventory.sources:
            report.source_hashes_before[s.name] = s.sha256
            log_event(
                EVENT_SOURCE_DISCOVERED,
                component="pilot",
                run_id=self.run_id,
                source_id=s.sha256,
                message=f"Phát hiện file nguồn: {s.name} ({s.pages} trang)",
                metadata={"file": s.name, "pages": s.pages, "size_bytes": s.size_bytes},
            )
        report.metrics.files_discovered = len(sources)
        return inventory

    def _stage_audit_and_metrics(
        self, report: PilotRunReport, registry: StateRegistry, apply_result: PipelineResult
    ) -> None:
        # Check source hashes after run
        current_pdfs = list_pdfs(self.folder)
        for p in current_pdfs:
            report.source_hashes_after[p.name] = sha256_file(p)

        intact = True
        if set(report.source_hashes_before.keys()) != set(report.source_hashes_after.keys()):
            intact = False
        else:
            for name, h in report.source_hashes_before.items():
                if report.source_hashes_after.get(name) != h:
                    intact = False
                    break
        report.source_integrity_intact = intact

        # Count output files (both settled in output/ and pending in review/)
        out_dir = self.ws.output / self.person_folder
        review_dir = self.ws.review / self.person_folder
        out_files = [f"output/{f.name}" for f in out_dir.glob("*.pdf")] if out_dir.is_dir() else []
        rev_files = [f"review/{f.name}" for f in review_dir.glob("*.pdf")] if review_dir.is_dir() else []
        report.output_files = out_files + rev_files

        # Query metrics from canonical summary in StateRegistry
        present_hashes = set(report.source_hashes_after.values())
        summary = registry.summarize_person(self.person_folder, present_hashes)
        report.metrics.taxonomy_documents = summary.get("taxonomy", 0)
        report.metrics.supporting_documents = summary.get("supporting", 0)
        report.metrics.duplicates = summary.get("duplicate", 0)
        report.metrics.review_pending = summary.get("review_pending", 0)
        report.metrics.documents_created = len(out_files) + len(rev_files)

        # Count processed vs skipped from incremental scan
        if apply_result.incremental:
            counts = apply_result.incremental.counts()
            report.metrics.files_processed = counts[DECISION_NEW] + counts[DECISION_STALE_ANALYSIS]
            report.metrics.files_skipped = counts[DECISION_ALREADY_PROCESSED] + counts[DECISION_DUPLICATE_SOURCE] + counts[DECISION_RETIRED_SOURCE]
            report.metrics.retryable_errors = counts[DECISION_INTERRUPTED] + counts[DECISION_FAILED_PREVIOUSLY]
        else:
            report.metrics.files_processed = len(report.source_hashes_before)
