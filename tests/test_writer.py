"""Bảo toàn hồ sơ: không đụng source, tách bằng page object, apply idempotent."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.models import ClassifiedDocument, DocumentClassification, LogicalDocument
from app.pdf_inventory import build_inventory, sha256_file
from app.writer import apply_documents, content_key, split_pages, verify_outputs


@pytest.fixture()
def workdir(tmp_path: Path, hai_folder: Path) -> Path:
    """Bản sao hồ sơ trong tmp để không bao giờ chạm vào input/ thật."""
    dst = tmp_path / "input" / hai_folder.name
    shutil.copytree(hai_folder, dst)
    return dst


def mk(source_file, pages, target_file, target_dir="output"):
    d = LogicalDocument(source_file=source_file, source_pages=list(pages), lead_page=pages[0])
    c = DocumentClassification(type_id="87", confidence=0.99)
    cd = ClassifiedDocument(document=d, classification=c)
    cd.target_file = target_file
    cd.target_dir = target_dir
    cd.final_status = "AUTO"
    return cd


def test_split_pages_khong_sua_file_nguon(workdir: Path, tmp_path: Path):
    src = workdir / "Quyet dinh dieu dong HAI.pdf"
    before_hash = sha256_file(src)
    before_mtime = src.stat().st_mtime_ns
    split_pages(src, [6, 7], tmp_path / "out" / "ks.pdf")
    assert sha256_file(src) == before_hash
    assert src.stat().st_mtime_ns == before_mtime


def test_split_pages_giu_dung_so_trang_va_thu_tu(workdir: Path, tmp_path: Path):
    src = workdir / "Quyet dinh dieu dong HAI.pdf"
    target = tmp_path / "out" / "ks.pdf"
    split_pages(src, [6, 7], target)
    out = PdfReader(str(target))
    assert len(out.pages) == 2
    source = PdfReader(str(src))
    for i, p in enumerate([6, 7]):
        assert out.pages[i].extract_text() == source.pages[p - 1].extract_text()


def test_split_pages_giu_nguyen_kho_trang_khong_rasterize(workdir: Path, tmp_path: Path):
    src = workdir / "Bang cap cua HAI.pdf"
    target = tmp_path / "out" / "bang.pdf"
    split_pages(src, [3, 4], target)
    out = PdfReader(str(target))
    source = PdfReader(str(src))
    for i, p in enumerate([3, 4]):
        assert float(out.pages[i].mediabox.width) == pytest.approx(
            float(source.pages[p - 1].mediabox.width)
        )
        # Trang vẫn còn XObject ảnh gốc -> không bị dựng lại thành ảnh mới.
        assert out.pages[i].images is not None


def test_split_pages_trang_ngoai_pham_vi_thi_bao_loi(workdir: Path, tmp_path: Path):
    from app.models import PipelineError

    with pytest.raises(PipelineError, match="nằm ngoài"):
        split_pages(workdir / "Phieu bo sung hs dang vien 2020 HAI.pdf", [1, 2], tmp_path / "x.pdf")


def test_apply_roi_apply_lai_khong_tao_ban_trung(workdir: Path, tmp_path: Path):
    inv = build_inventory(workdir)
    out, rev = tmp_path / "output", tmp_path / "review"
    docs = [
        mk("Quyet dinh dieu dong HAI.pdf", [1], "87.A.1.pdf"),
        mk("Quyet dinh dieu dong HAI.pdf", [6, 7], "75.B.pdf"),
    ]

    r1 = apply_documents(docs, inv, out, rev)
    assert r1.ok and len(r1.written) == 2
    files1 = sorted(p.name for p in out.iterdir())
    hashes1 = {p.name: sha256_file(p) for p in out.iterdir()}

    ledger = {"targets": {d.target_file: {"content_key": content_key(
        inv.by_name(d.document.source_file).sha256, d.document.source_pages)} for d in docs}}

    r2 = apply_documents(docs, inv, out, rev, previous_ledger=ledger)
    assert r2.ok
    assert r2.written == []
    assert len(r2.skipped_identical) == 2
    assert sorted(p.name for p in out.iterdir()) == files1
    assert {p.name: sha256_file(p) for p in out.iterdir()} == hashes1


def test_file_dich_la_de_khong_bi_ghi_de_am_tham(workdir: Path, tmp_path: Path):
    inv = build_inventory(workdir)
    out, rev = tmp_path / "output", tmp_path / "review"
    out.mkdir(parents=True)
    stranger = out / "87.A.1.pdf"
    stranger.write_bytes(b"%PDF-1.4 khong phai cua pipeline")
    docs = [mk("Quyet dinh dieu dong HAI.pdf", [1], "87.A.1.pdf")]

    r = apply_documents(docs, inv, out, rev)
    assert not r.ok
    assert r.conflicts
    assert stranger.read_bytes().startswith(b"%PDF-1.4 khong phai")


def test_xung_dot_thi_khong_ghi_bat_ky_file_nao(workdir: Path, tmp_path: Path):
    inv = build_inventory(workdir)
    out, rev = tmp_path / "output", tmp_path / "review"
    out.mkdir(parents=True)
    (out / "87.A.1.pdf").write_bytes(b"%PDF-1.4 la")
    docs = [
        mk("Quyet dinh dieu dong HAI.pdf", [1], "87.A.1.pdf"),
        mk("Quyet dinh dieu dong HAI.pdf", [2], "87.A.2.pdf"),
    ]
    r = apply_documents(docs, inv, out, rev)
    assert not r.ok
    assert not (out / "87.A.2.pdf").exists()  # fail-safe: không ghi gì cả


def test_apply_khong_sua_file_nguon(workdir: Path, tmp_path: Path):
    inv = build_inventory(workdir)
    before = {s.name: s.sha256 for s in inv.sources}
    docs = [mk("Bang cap cua HAI.pdf", [1, 2], "86.X.pdf")]
    apply_documents(docs, inv, tmp_path / "output", tmp_path / "review")
    after = {p.name: sha256_file(p) for p in workdir.iterdir() if p.suffix == ".pdf"}
    assert after == before


def test_verify_outputs_phat_hien_sai_so_trang(workdir: Path, tmp_path: Path):
    inv = build_inventory(workdir)
    out, rev = tmp_path / "output", tmp_path / "review"
    docs = [mk("Bang cap cua HAI.pdf", [1, 2], "86.X.pdf")]
    apply_documents(docs, inv, out, rev)
    assert verify_outputs(docs, out, rev) == []
    docs[0].document.source_pages = [1, 2, 3]
    assert verify_outputs(docs, out, rev)


def test_content_key_on_dinh_va_phan_biet_duoc():
    assert content_key("abc", [1, 2]) == content_key("abc", [1, 2])
    assert content_key("abc", [1, 2]) != content_key("abc", [2, 1])
    assert content_key("abc", [1]) != content_key("abd", [1])
