"""QC phải BẮT được vi phạm, không chỉ báo xanh."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.models import UNKNOWN, ClassifiedDocument, DocumentClassification, LogicalDocument
from app.pdf_inventory import build_inventory
from app.qc import run_qc

OUT = Path("output/X")
REV = Path("review/X")


@pytest.fixture()
def inv(tmp_path: Path, hai_folder: Path):
    dst = tmp_path / "input" / hai_folder.name
    shutil.copytree(hai_folder, dst)
    return build_inventory(dst)


def mk(source, pages, type_id="87", target=None, status="AUTO"):
    d = LogicalDocument(source_file=source, source_pages=list(pages), lead_page=pages[0])
    c = DocumentClassification(type_id=type_id, confidence=0.99)
    cd = ClassifiedDocument(document=d, classification=c)
    cd.final_status = status
    cd.target_dir = "output" if status == "AUTO" else "review"
    cd.target_file = target
    return cd


def full_cover(catalog, inv):
    """Bộ tài liệu phủ đúng 100% trang, mỗi trang một tài liệu, tên hợp lệ."""
    docs = []
    ids = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
    i = 0
    for src in inv.sources:
        for p in range(1, src.pages + 1):
            tid = ids[i % len(ids)]
            docs.append(
                mk(src.name, [p], tid, f"{catalog.filename_base(tid)}.{i + 1}.pdf")
            )
            i += 1
    return docs


def test_qc_xanh_khi_moi_thu_dung(catalog, inv):
    report = run_qc(catalog, inv, full_cover(catalog, inv), OUT, REV)
    assert report.passed, [c.as_dict() for c in report.failures]


def test_qc_bat_thieu_trang(catalog, inv):
    docs = full_cover(catalog, inv)
    docs.pop()
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "page_coverage" for c in report.failures)


def test_qc_bat_trang_dung_lap(catalog, inv):
    docs = full_cover(catalog, inv)
    docs.append(mk(docs[0].document.source_file, docs[0].document.source_pages, "22", "22.X.pdf"))
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "page_overlap" for c in report.failures)


def test_qc_bat_ten_file_khong_tu_catalog(catalog, inv):
    docs = full_cover(catalog, inv)
    docs[0].target_file = "Bang_tot_nghiep_cua_anh_Hai.pdf"
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "naming_from_catalog" for c in report.failures)


def test_qc_bat_auto_nhung_type_unknown(catalog, inv):
    docs = full_cover(catalog, inv)
    docs[0].classification.type_id = UNKNOWN
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "naming_from_catalog" for c in report.failures)


def test_qc_bat_file_review_khong_co_tien_to(catalog, inv):
    docs = full_cover(catalog, inv)
    docs[0].final_status = "REVIEW"
    docs[0].target_dir = "review"
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "naming_from_catalog" for c in report.failures)


def test_qc_bat_trung_ten_file_dich(catalog, inv):
    docs = full_cover(catalog, inv)
    docs[1].target_file = docs[0].target_file
    docs[1].target_dir = docs[0].target_dir
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "filename_collision" for c in report.failures)


def test_qc_bat_source_bi_sua(catalog, inv):
    docs = full_cover(catalog, inv)
    victim = inv.sources[0].path
    victim.write_bytes(victim.read_bytes() + b"\n% da bi sua\n")
    report = run_qc(catalog, inv, docs, OUT, REV)
    assert not report.passed
    assert any(c.name == "source_unchanged" for c in report.failures)


def test_qc_bat_file_dau_ra_hong(catalog, inv):
    docs = full_cover(catalog, inv)
    report = run_qc(catalog, inv, docs, OUT, REV, output_problems=["'x.pdf' có 1 trang, kỳ vọng 2"])
    assert not report.passed
    assert any(c.name == "outputs_readable" for c in report.failures)
