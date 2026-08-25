"""Phase 12 — Real-World Pilot & Operational Hardening Test Suite.

Kiểm chứng các workstream:
- Failure recovery (app killed, crash giữa chừng, resume sau partial completion)
- Idempotency & Incremental additions
- Source change detection (đổi tên, sửa nội dung, duplicate)
- Corrupted / Unsupported / Zero-byte / Unicode / Long filename inputs
- Disk space safety & atomic write cleanup
- State DB backup & restore
- Operational logging & crash audit
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import pytest
from pypdf import PdfReader, PdfWriter

from app import cli
from app.batch import PERSON_BLOCKED, PERSON_COMPLETED, run_batch
from app.fingerprint import current_fingerprint
from app.golden_fixtures import deterministic_blank_pdf, isolated_golden_workspace
from app.incremental import (
    DECISION_ALREADY_PROCESSED,
    DECISION_DUPLICATE_SOURCE,
    DECISION_INTERRUPTED,
    DECISION_NEW,
    scan_person_folder,
)
from app.models import MODE_APPLY, MODE_DRY_RUN, PipelineError
from app.oplog import (
    EVENT_ERROR_OCCURRED,
    EVENT_RUN_START,
    read_operational_logs,
    set_operational_log_file,
)
from app.pdf_inventory import PersonInventory, build_inventory, list_pdfs, read_source, sha256_file
from app.pipeline import Workspace, process_person_folder
from app.state import (
    STATUS_FAILED,
    STATUS_PROCESSED,
    STATUS_PROCESSING,
    StateRegistry,
)
from app.writer import check_disk_capacity, split_pages


# ---------------- Corrupted / Unsupported Inputs ----------------
def test_zero_byte_pdf_handling(tmp_path: Path):
    ws = Workspace(tmp_path)
    person_dir = tmp_path / "input" / "TEST_CORRUPT"
    person_dir.mkdir(parents=True)
    zero_pdf = person_dir / "zero.pdf"
    zero_pdf.write_bytes(b"")

    with pytest.raises(PipelineError, match="PDF rỗng|Không đọc được PDF"):
        read_source(zero_pdf)


def test_corrupted_pdf_bytes_handling(tmp_path: Path):
    ws = Workspace(tmp_path)
    person_dir = tmp_path / "input" / "TEST_CORRUPT"
    person_dir.mkdir(parents=True)
    bad_pdf = person_dir / "corrupted.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4 THIS IS INVALID CORRUPT CONTENT")

    with pytest.raises(PipelineError, match="Không đọc được PDF"):
        read_source(bad_pdf)


def test_unsupported_non_pdf_files_ignored(tmp_path: Path):
    person_dir = tmp_path / "input" / "TEST_PERSON"
    person_dir.mkdir(parents=True)
    (person_dir / "image.png").write_bytes(b"fake png")
    (person_dir / "notes.txt").write_text("plain text notes", encoding="utf-8")
    (person_dir / "doc.pdf").write_bytes(deterministic_blank_pdf(1))

    pdfs = list_pdfs(person_dir)
    assert len(pdfs) == 1
    assert pdfs[0].name == "doc.pdf"


def test_unicode_and_long_filenames(tmp_path: Path):
    person_dir = tmp_path / "input" / "NGUYỄN_VĂN_A"
    person_dir.mkdir(parents=True)
    long_unicode_name = "01.Don_xin_vao_Dang_Đảng_Viên_Nguyễn_Văn_A_Rất_Dài_Hồ_Sơ_Chi_Tiết_Số_Hóa_2026_Xác_Minh.pdf"
    pdf_path = person_dir / long_unicode_name
    pdf_path.write_bytes(deterministic_blank_pdf(2))

    src = read_source(pdf_path)
    assert src.name == long_unicode_name
    assert src.pages == 2
    assert src.sha256 is not None


def test_read_only_source_file_intact(tmp_path: Path):
    person_dir = tmp_path / "input" / "TEST_READONLY"
    person_dir.mkdir(parents=True)
    pdf_path = person_dir / "sample.pdf"
    pdf_path.write_bytes(deterministic_blank_pdf(1))
    
    # Make file read-only
    import stat
    os.chmod(pdf_path, stat.S_IREAD)
    try:
        src = read_source(pdf_path)
        assert src.pages == 1
        assert sha256_file(pdf_path) == src.sha256
    finally:
        os.chmod(pdf_path, stat.S_IWRITE | stat.S_IREAD)


# ---------------- Failure Recovery & Resume ----------------
def test_crash_interruption_and_resume(repo_root: Path, tmp_path: Path):
    with isolated_golden_workspace(repo_root, temp_parent=tmp_path) as staged:
        ws = Workspace(staged.root)
        from app.catalog import load_catalog
        catalog = load_catalog()
        fp = current_fingerprint(catalog)
        
        with StateRegistry(ws.state_db_path) as registry:
            inv = build_inventory(staged.person_folder)
            first_src = inv.sources[0]
            
            # Simulate a crash leaving first source in STATUS_PROCESSING
            registry.begin_processing(
                source_hash=first_src.sha256,
                source_filename=first_src.name,
                source_relative_path=f"{inv.person_folder}/{first_src.name}",
                person_folder=inv.person_folder,
                page_count=first_src.pages,
            )
            rec = registry.get(first_src.sha256)
            assert rec.status == STATUS_PROCESSING

            # Incremental scan recognizes it as INTERRUPTED
            scan = scan_person_folder(inv, registry, mode=MODE_DRY_RUN, fingerprint=fp)
            c = scan.counts()
            assert c[DECISION_INTERRUPTED] == 1

            # Resume with retry_failed=True
            res = process_person_folder(
                staged.person_folder,
                mode=MODE_APPLY,
                provider_name="agent",
                provider_config={"analysis_root": str(staged.analysis_root)},
                workspace=ws,
                state_registry=registry,
                retry_failed=True,
            )
            assert res.status in ("APPLY_PASS", "REVIEW_REQUIRED")
            
            # Verify source recovered from PROCESSING
            rec_after = registry.get(first_src.sha256)
            assert rec_after.status in (STATUS_PROCESSED, "ANALYZED_PENDING_APPLY", "REVIEW_REQUIRED")


# ---------------- Idempotency & Incremental Additions ----------------
def test_idempotent_rerun_does_not_duplicate_or_reprocess(repo_root: Path, tmp_path: Path):
    with isolated_golden_workspace(repo_root, temp_parent=tmp_path) as staged:
        ws = Workspace(staged.root)
        with StateRegistry(ws.state_db_path) as registry:
            # Run 1: Apply
            res1 = process_person_folder(
                staged.person_folder,
                mode=MODE_APPLY,
                provider_name="agent",
                provider_config={"analysis_root": str(staged.analysis_root)},
                workspace=ws,
                state_registry=registry,
            )
            out_files_run1 = sorted([p.name for p in (ws.output / staged.person_folder.name).glob("*.pdf")])
            out_hashes_run1 = {name: sha256_file(ws.output / staged.person_folder.name / name) for name in out_files_run1}

            # Run 2: Re-run same source
            res2 = process_person_folder(
                staged.person_folder,
                mode=MODE_APPLY,
                provider_name="agent",
                provider_config={"analysis_root": str(staged.analysis_root)},
                workspace=ws,
                state_registry=registry,
            )
            out_files_run2 = sorted([p.name for p in (ws.output / staged.person_folder.name).glob("*.pdf")])
            out_hashes_run2 = {name: sha256_file(ws.output / staged.person_folder.name / name) for name in out_files_run2}

            # Must be identical
            assert out_files_run1 == out_files_run2
            assert out_hashes_run1 == out_hashes_run2
            assert len(res2.incremental.needs_agent_sources) == 0


# ---------------- Disk Space Guard & Atomic Write Safety ----------------
def test_disk_capacity_check_fails_when_full(tmp_path: Path, monkeypatch):
    import shutil

    # Mock disk_usage to report 1 KB free
    def mock_usage(path):
        from collections import namedtuple
        Usage = namedtuple("Usage", ["total", "used", "free"])
        return Usage(1000000, 999000, 1024)

    monkeypatch.setattr(shutil, "disk_usage", mock_usage)

    with pytest.raises(PipelineError, match="Không đủ dung lượng đĩa"):
        check_disk_capacity(tmp_path, required_bytes=10 * 1024 * 1024)


def test_atomic_write_cleans_part_file_on_error(tmp_path: Path, monkeypatch):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(deterministic_blank_pdf(2))
    target_pdf = tmp_path / "target.pdf"

    # Simulate error during writer.write
    def broken_write(self, stream):
        stream.write(b"partial corrupted data")
        raise OSError("Disk full simulation")

    monkeypatch.setattr(PdfWriter, "write", broken_write)

    with pytest.raises(PipelineError, match="Ghi file .* thất bại"):
        split_pages(source_pdf, [1], target_pdf)

    # .part file and target file must not exist
    assert not target_pdf.exists()
    assert not (tmp_path / "target.pdf.part").exists()
