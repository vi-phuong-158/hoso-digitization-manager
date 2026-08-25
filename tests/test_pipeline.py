"""Pipeline đầu-cuối: dry-run mặc định, coverage/overlap, apply idempotent."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.manifest import normalize_for_compare
from app.models import PipelineError
from app.pdf_inventory import sha256_file
from app.pipeline import MODE_APPLY, MODE_DRY_RUN, Workspace, process_person_folder


@pytest.fixture()
def sandbox(tmp_path: Path, hai_folder: Path):
    """Workspace tạm + bản sao hồ sơ, để test không đụng input/output thật."""
    folder = tmp_path / "input" / hai_folder.name
    shutil.copytree(hai_folder, folder)
    return folder, Workspace(tmp_path)


def run(sandbox, mode=MODE_DRY_RUN, **kw):
    folder, ws = sandbox
    return process_person_folder(folder, mode=mode, workspace=ws, provider_name="fixture", **kw)


def test_dry_run_la_mac_dinh_va_khong_ghi_output(sandbox):
    folder, ws = sandbox
    result = run(sandbox)
    assert result.mode == MODE_DRY_RUN
    assert not ws.output.exists()
    assert not ws.review.exists()
    assert result.manifest_path is not None and result.manifest_path.is_file()
    assert result.manifest["summary"]["logical_documents"] == 18


def test_page_coverage_100_va_khong_overlap(sandbox):
    result = run(sandbox)
    assert result.qc.passed, [c.as_dict() for c in result.qc.failures]
    total = sum(len(d.document.source_pages) for d in result.documents)
    flat = [
        (d.document.source_file, p) for d in result.documents for p in d.document.source_pages
    ]
    assert total == result.inventory.total_pages == 29
    assert len(flat) == len(set(flat))


def test_moi_logical_document_deu_co_trang_thai(sandbox):
    result = run(sandbox)
    assert all(d.final_status in ("AUTO", "REVIEW") for d in result.documents)
    auto = [d for d in result.documents if d.final_status == "AUTO"]
    review = [d for d in result.documents if d.final_status == "REVIEW"]
    assert len(auto) + len(review) == len(result.documents)


def test_dry_run_idempotent(sandbox):
    a = run(sandbox)
    b = run(sandbox)
    assert normalize_for_compare(a.manifest) == normalize_for_compare(b.manifest)


def test_apply_tao_dung_file_va_khong_sua_source(sandbox):
    folder, ws = sandbox
    before = {p.name: sha256_file(p) for p in folder.iterdir() if p.suffix == ".pdf"}
    result = run(sandbox, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS", [c.as_dict() for c in result.qc.failures]

    after = {p.name: sha256_file(p) for p in folder.iterdir() if p.suffix == ".pdf"}
    assert after == before

    out_dir = ws.output / folder.name
    rev_dir = ws.review / folder.name
    auto = [d for d in result.documents if d.final_status == "AUTO"]
    review = [d for d in result.documents if d.final_status == "REVIEW"]
    for d in auto:
        assert (out_dir / d.target_file).is_file()
    for d in review:
        assert (rev_dir / d.target_file).is_file()
    assert (out_dir / "_manifest.json").is_file()
    assert result.qc.as_dict()["all_pages_accounted_for"]


def test_apply_lai_lan_hai_khong_am_tham_tao_ban_trung(sandbox):
    folder, ws = sandbox
    run(sandbox, mode=MODE_APPLY)
    out_dir = ws.output / folder.name
    snapshot = {p.name: sha256_file(p) for p in out_dir.iterdir() if p.suffix == ".pdf"}

    second = run(sandbox, mode=MODE_APPLY)
    assert second.status == "APPLY_PASS"
    assert second.write_result is not None
    assert second.write_result.written == []
    assert len(second.write_result.skipped_identical) == len(
        [d for d in second.documents if d.target_file]
    )
    assert {p.name: sha256_file(p) for p in out_dir.iterdir() if p.suffix == ".pdf"} == snapshot


def test_apply_dung_lai_khi_file_dich_bi_thay_the_bang_ban_khac(sandbox):
    folder, ws = sandbox
    run(sandbox, mode=MODE_APPLY)
    out_dir = ws.output / folder.name
    victim = next(p for p in out_dir.iterdir() if p.suffix == ".pdf")
    victim.write_bytes(b"%PDF-1.4 ban khac")

    result = run(sandbox, mode=MODE_APPLY)
    assert result.status == "BLOCKED_RUNTIME"
    assert victim.read_bytes().startswith(b"%PDF-1.4 ban khac")


def test_tai_lieu_review_khong_bao_gio_ra_output(sandbox):
    result = run(sandbox)
    for d in result.documents:
        if d.final_status == "REVIEW":
            assert d.target_dir == "review"


def test_manifest_truy_nguoc_duoc_nguon(sandbox):
    result = run(sandbox)
    for entry in result.manifest["documents"]:
        assert entry["source_file"]
        assert entry["source_pages"]
        assert entry["target_file"]
        assert entry["status"] in ("AUTO", "REVIEW")
    sources = {s["file"]: s for s in result.manifest["sources"]}
    assert set(sources) == {
        "Bang cap cua HAI.pdf",
        "Phieu bo sung hs dang vien 2020 HAI.pdf",
        "Quyet dinh dieu dong HAI.pdf",
    }
    for s in sources.values():
        assert len(s["sha256"]) == 64


def test_manifest_khong_chua_toan_van_tai_lieu(sandbox):
    result = run(sandbox)
    for entry in result.manifest["documents"]:
        assert entry["title_short"] is None or len(entry["title_short"]) <= 200


def test_ho_so_khong_co_fixture_thi_bao_loi_ro_rang(tmp_path: Path, hai_folder: Path):
    folder = tmp_path / "input" / "NGUOI_MOI"
    folder.mkdir(parents=True)
    shutil.copy2(hai_folder / "Phieu bo sung hs dang vien 2020 HAI.pdf", folder)
    with pytest.raises(PipelineError, match="Không có fixture"):
        process_person_folder(folder, workspace=Workspace(tmp_path), provider_name="fixture")


def test_thu_muc_rong_bao_loi(tmp_path: Path):
    folder = tmp_path / "input" / "RONG"
    folder.mkdir(parents=True)
    with pytest.raises(PipelineError, match="không có file PDF"):
        process_person_folder(folder, workspace=Workspace(tmp_path), provider_name="fixture")
