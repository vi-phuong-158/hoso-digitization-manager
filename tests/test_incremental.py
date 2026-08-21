"""scan_person_folder: đối chiếu inventory với state registry, KHÔNG mở PDF."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.incremental import (
    DECISION_ALREADY_PROCESSED,
    DECISION_DUPLICATE_SOURCE,
    DECISION_FAILED_PREVIOUSLY,
    DECISION_INTERRUPTED,
    DECISION_NEW,
    DECISION_REVIEW_PENDING,
    scan_person_folder,
)
from app.models import MODE_APPLY, MODE_DRY_RUN
from app.pdf_inventory import build_inventory
from app.state import StateRegistry
from state_testkit import add_source


@pytest.fixture()
def env(tmp_path: Path):
    input_root = tmp_path / "input"
    analysis_root = tmp_path / "analysis"
    reg = StateRegistry(tmp_path / "state" / "processing_state.db")
    yield input_root, analysis_root, reg
    reg.close()


def inv(input_root: Path, person="P"):
    return build_inventory(input_root / person)


def test_hash_chua_tung_thay_la_new(env):
    input_root, analysis_root, reg = env
    add_source(input_root, analysis_root, "P", "a.pdf")
    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    assert [d.decision for d in scan.decisions] == [DECISION_NEW]
    assert scan.to_process and scan.to_process[0].name == "a.pdf"


def test_processed_thi_skip_khong_process(env):
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    reg.begin_processing(
        source_hash=sha256_file(src), source_filename="a.pdf", source_relative_path="P/a.pdf",
        person_folder="P", page_count=1,
    )
    reg.commit_processed(sha256_file(src), logical_document_count=1, manifest_path="x")

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    d = scan.decisions[0]
    assert d.decision == DECISION_ALREADY_PROCESSED
    assert d.will_process is False
    assert scan.to_process == []


def test_cung_ten_khac_hash_la_new(env):
    """scan001.pdf hash ABC đã PROCESSED; sau đó scan001.pdf bị THAY bằng nội dung khác (hash XYZ)."""
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "scan001.pdf")
    from app.pdf_inventory import sha256_file

    old_hash = sha256_file(src)
    reg.begin_processing(
        source_hash=old_hash, source_filename="scan001.pdf", source_relative_path="P/scan001.pdf",
        person_folder="P", page_count=1,
    )
    reg.commit_processed(old_hash, logical_document_count=1, manifest_path="x")

    # Ghi đè scan001.pdf bằng nội dung khác (khổ trang khác -> hash khác).
    add_source(input_root, analysis_root, "P", "scan001.pdf", size=(420.0, 700.0))
    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    d = scan.decisions[0]
    assert d.decision == DECISION_NEW
    assert d.will_process is True


def test_khac_ten_cung_hash_la_duplicate(env):
    """copy-scan001.pdf giống hệt scan001.pdf (cùng hash) -> không xử lý AI lần 2."""
    input_root, analysis_root, reg = env
    same_size = (420.0, 611.0)
    add_source(input_root, analysis_root, "P", "scan001.pdf", size=same_size)
    add_source(input_root, analysis_root, "P", "copy-scan001.pdf", size=same_size)

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    by_name = {d.source.name: d for d in scan.decisions}
    # canonical = tên nhỏ nhất theo alphabet (deterministic) -> "copy-..." < "scan..."
    assert by_name["copy-scan001.pdf"].decision == DECISION_NEW
    assert by_name["scan001.pdf"].decision == DECISION_DUPLICATE_SOURCE
    assert by_name["scan001.pdf"].will_process is False
    assert by_name["scan001.pdf"].duplicate_of_name == "copy-scan001.pdf"
    # Chỉ có 1 nguồn được đưa cho Agent đọc, không phải 2.
    assert len(scan.to_process) == 1


def test_review_required_mac_dinh_skip_dry_run(env):
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.mark_review_required(h, logical_document_count=1, manifest_path=None)

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    d = scan.decisions[0]
    assert d.decision == DECISION_REVIEW_PENDING
    assert d.will_process is False


def test_review_required_voi_retry_review_thi_xu_ly(env):
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.mark_review_required(h, logical_document_count=1, manifest_path=None)

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN, retry_review=True)
    assert scan.decisions[0].will_process is True


def test_review_required_apply_mac_dinh_van_xu_ly(env):
    """Apply là hành động ghi thật -> phải xử lý REVIEW_PENDING dù không có --retry-review."""
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.mark_review_required(h, logical_document_count=1, manifest_path=None)

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_APPLY)
    assert scan.decisions[0].will_process is True


def test_failed_khong_tu_dong_retry(env):
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.mark_failed(h, error="loi")

    scan_dry = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    scan_apply = scan_person_folder(inv(input_root), reg, mode=MODE_APPLY)
    assert scan_dry.decisions[0].decision == DECISION_FAILED_PREVIOUSLY
    assert scan_dry.decisions[0].will_process is False
    assert scan_apply.decisions[0].will_process is False  # apply cũng KHÔNG tự retry failed


def test_failed_voi_retry_failed_thi_xu_ly(env):
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.mark_failed(h, error="loi")

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN, retry_failed=True)
    assert scan.decisions[0].will_process is True


def test_processing_con_sot_la_interrupted_khong_tu_retry(env):
    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    # KHÔNG gọi commit/mark_failed/mark_review -> mô phỏng crash giữa chừng.

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    assert scan.decisions[0].decision == DECISION_INTERRUPTED
    assert scan.decisions[0].will_process is False

    scan_retry = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN, retry_failed=True)
    assert scan_retry.decisions[0].will_process is True


def test_file_di_chuyen_cung_hash_khong_xu_ly_lai(env):
    """Cùng hash nhưng đường dẫn/tên khác -> vẫn nhận ra đã xử lý, không cần path khớp."""
    input_root, analysis_root, reg = env
    same_size = (420.0, 633.0)
    src = add_source(input_root, analysis_root, "P", "scan1.pdf", size=same_size)
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    reg.begin_processing(source_hash=h, source_filename="scan1.pdf", source_relative_path="P/scan1.pdf",
                          person_folder="P", page_count=1)
    reg.commit_processed(h, logical_document_count=1, manifest_path="x")

    src.unlink()
    add_source(input_root, analysis_root, "P", "tai-lieu-cu.pdf", size=same_size)  # cùng nội dung -> cùng hash, tên khác

    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    assert scan.decisions[0].source.name == "tai-lieu-cu.pdf"
    assert scan.decisions[0].decision == DECISION_ALREADY_PROCESSED
    assert scan.to_process == []


def test_output_mismatch_khi_state_processed_nhung_thieu_file(env, tmp_path):
    import json

    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    output_dir = tmp_path / "output" / "P"
    review_dir = tmp_path / "review" / "P"
    ledger_path = output_dir / "_manifest.json"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        json.dumps(
            {
                "documents": [
                    {"source_file": "a.pdf", "target_file": "04.X.pdf", "target_dir": "output"}
                ]
            }
        ),
        encoding="utf-8",
    )
    # KHÔNG tạo file 04.X.pdf thật -> mismatch.
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.commit_processed(h, logical_document_count=1, manifest_path=str(ledger_path))

    scan = scan_person_folder(
        inv(input_root), reg, mode=MODE_DRY_RUN, output_dir=output_dir, review_dir=review_dir
    )
    d = scan.decisions[0]
    assert d.decision == DECISION_ALREADY_PROCESSED
    assert d.output_mismatch is True
    assert "04.X.pdf" in d.output_mismatch_detail
    assert d.will_process is False  # không tự tạo lại


def test_output_khop_thi_khong_mismatch(env, tmp_path):
    import json

    input_root, analysis_root, reg = env
    src = add_source(input_root, analysis_root, "P", "a.pdf")
    from app.pdf_inventory import sha256_file

    h = sha256_file(src)
    output_dir = tmp_path / "output" / "P"
    review_dir = tmp_path / "review" / "P"
    output_dir.mkdir(parents=True)
    (output_dir / "04.X.pdf").write_bytes(b"%PDF-1.4 fake")
    ledger_path = output_dir / "_manifest.json"
    ledger_path.write_text(
        json.dumps({"documents": [{"source_file": "a.pdf", "target_file": "04.X.pdf", "target_dir": "output"}]}),
        encoding="utf-8",
    )
    reg.begin_processing(source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
                          person_folder="P", page_count=1)
    reg.commit_processed(h, logical_document_count=1, manifest_path=str(ledger_path))

    scan = scan_person_folder(
        inv(input_root), reg, mode=MODE_DRY_RUN, output_dir=output_dir, review_dir=review_dir
    )
    assert scan.decisions[0].output_mismatch is False


def test_summary_text_va_counts(env):
    input_root, analysis_root, reg = env
    add_source(input_root, analysis_root, "P", "a.pdf")
    scan = scan_person_folder(inv(input_root), reg, mode=MODE_DRY_RUN)
    assert scan.counts()[DECISION_NEW] == 1
    text = scan.summary_text()
    assert "Mới bổ sung: 1" in text
    assert "HỒ SƠ: P" in text
