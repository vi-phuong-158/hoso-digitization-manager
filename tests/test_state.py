"""StateRegistry: các phép chuyển trạng thái nguyên tử trên SQLite local."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.models import PipelineError
from app.state import (
    STATUS_FAILED,
    STATUS_PROCESSED,
    STATUS_PROCESSING,
    STATUS_REVIEW_REQUIRED,
    StateRegistry,
)


@pytest.fixture()
def registry(tmp_path: Path):
    with StateRegistry(tmp_path / "state" / "processing_state.db") as reg:
        yield reg


def begin(reg, h="h1", name="a.pdf", person="P", pages=3):
    reg.begin_processing(
        source_hash=h, source_filename=name, source_relative_path=f"{person}/{name}",
        person_folder=person, page_count=pages,
    )


def test_hash_chua_tung_thay_thi_khong_co_record(registry):
    assert registry.get("khong-ton-tai") is None


def test_begin_processing_tao_record_processing(registry):
    begin(registry)
    r = registry.get("h1")
    assert r.status == STATUS_PROCESSING
    assert r.first_seen_at
    assert r.processing_started_at
    assert r.processed_at is None


def test_state_db_la_file_that_tren_dia(tmp_path: Path, registry):
    assert (tmp_path / "state" / "processing_state.db").is_file()


def test_commit_processed_chi_hop_le_tu_processing(registry):
    begin(registry)
    registry.commit_processed("h1", logical_document_count=5, manifest_path="output/P/_manifest.json")
    r = registry.get("h1")
    assert r.status == STATUS_PROCESSED
    assert r.processed_at is not None
    assert r.logical_document_count == 5


def test_commit_processed_tren_record_khong_o_processing_thi_bao_loi(registry):
    with pytest.raises(PipelineError, match="PROCESSING"):
        registry.commit_processed("khong-ton-tai", logical_document_count=1, manifest_path="x")


def test_apply_qc_fail_khong_duoc_danh_processed(registry):
    begin(registry)
    registry.mark_failed("h1", error="QC không đạt")
    r = registry.get("h1")
    assert r.status == STATUS_FAILED
    assert r.status != STATUS_PROCESSED


def test_dry_run_khong_duoc_danh_processed_review_required_thi_duoc(registry):
    begin(registry)
    registry.mark_review_required("h1", logical_document_count=2, manifest_path=None)
    r = registry.get("h1")
    assert r.status == STATUS_REVIEW_REQUIRED
    assert r.status != STATUS_PROCESSED
    assert r.processed_at is None  # REVIEW_REQUIRED không phải "đã xong"


def test_release_dry_run_sach_tro_ve_new(registry):
    begin(registry)
    registry.release("h1")
    assert registry.get("h1") is None  # NEW = không có record


def test_release_khong_dung_lam_gi_neu_khong_o_processing(registry):
    begin(registry)
    registry.commit_processed("h1", logical_document_count=1, manifest_path="x")
    registry.release("h1")  # không được xoá mất record PROCESSED
    r = registry.get("h1")
    assert r is not None and r.status == STATUS_PROCESSED


def test_failed_khong_tu_retry_phai_qua_begin_processing_lai(registry):
    begin(registry)
    registry.mark_failed("h1", error="loi ky thuat")
    r = registry.get("h1")
    assert r.status == STATUS_FAILED
    # Retry là hành động rõ ràng: gọi lại begin_processing (giả lập CLI --retry-failed).
    begin(registry)
    r = registry.get("h1")
    assert r.status == STATUS_PROCESSING
    assert r.last_error is None  # lỗi cũ được xoá khi bắt đầu lại


def test_processing_con_sot_la_dau_hieu_interrupted(registry):
    """Không set-completion nào được gọi (mô phỏng crash) -> record dừng ở PROCESSING mãi."""
    begin(registry)
    r = registry.get("h1")
    assert r.status == STATUS_PROCESSING  # lần "chạy sau" đọc lại sẽ suy ra đây là INTERRUPTED


def test_last_error_bi_gioi_han_do_dai_khong_thanh_noi_chep_toan_van(registry):
    begin(registry)
    registry.mark_failed("h1", error="x" * 5000)
    r = registry.get("h1")
    assert len(r.last_error) <= 2000


def test_export_json_khong_chua_noi_dung_tai_lieu(registry):
    begin(registry)
    registry.commit_processed("h1", logical_document_count=1, manifest_path="x")
    data = registry.export_json()
    assert data["sources"][0]["source_hash"] == "h1"
    # Chỉ có metadata điều phối, không có trường nào chứa văn bản/OCR.
    assert set(data["sources"][0]) == {
        "source_hash", "source_filename", "source_relative_path", "person_folder",
        "page_count", "status", "first_seen_at", "processing_started_at", "processed_at",
        "logical_document_count", "manifest_path", "last_error", "pipeline_version",
        "last_seen_path", "updated_at",
    }


def test_all_loc_theo_person_folder(registry):
    begin(registry, h="h1", name="a.pdf", person="P1")
    begin(registry, h="h2", name="b.pdf", person="P2")
    assert {s.source_hash for s in registry.all(person_folder="P1")} == {"h1"}
    assert {s.source_hash for s in registry.all()} == {"h1", "h2"}


def test_import_processed_khong_di_qua_processing(registry):
    registry.import_processed(
        source_hash="h9", source_filename="old.pdf", source_relative_path="P/old.pdf",
        person_folder="P", page_count=2, logical_document_count=2,
        manifest_path="output/P/_manifest.json",
    )
    r = registry.get("h9")
    assert r.status == STATUS_PROCESSED
    assert r.processing_started_at is None


def test_import_processed_khong_ghi_de_record_da_co(registry):
    begin(registry, h="h1")
    registry.commit_processed("h1", logical_document_count=1, manifest_path="a")
    registry.import_processed(
        source_hash="h1", source_filename="a.pdf", source_relative_path="P/a.pdf",
        person_folder="P", page_count=3, logical_document_count=99, manifest_path="KHAC",
    )
    r = registry.get("h1")
    assert r.logical_document_count == 1  # không bị import ghi đè
