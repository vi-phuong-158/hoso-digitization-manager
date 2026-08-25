"""Chốt kết quả rehearsal trên bộ fixture tổng hợp (provider agent).

Đây là snapshot để phát hiện regression: nếu ai đó đổi ngưỡng, đổi luật đặt tên
hay đổi phân tích của Agent, các con số dưới đây sẽ lệch và test đỏ.
"""
from __future__ import annotations

import pytest

from app.pipeline import Workspace, process_person_folder


@pytest.fixture(scope="module")
def rehearsal(tmp_path_factory, hai_folder, hai_analysis_root):
    ws = Workspace(tmp_path_factory.mktemp("rehearsal"))
    return process_person_folder(
        hai_folder,
        provider_name="agent",
        provider_config={"analysis_root": str(hai_analysis_root)},
        workspace=ws,
        write_manifest=False,
    )


def test_dung_18_logical_document_tren_29_trang(rehearsal):
    assert rehearsal.inventory.total_pages == 29
    assert len(rehearsal.documents) == 18
    assert rehearsal.qc.passed


def test_phan_bo_auto_review(rehearsal):
    auto = [d for d in rehearsal.documents if d.final_status == "AUTO"]
    review = [d for d in rehearsal.documents if d.final_status == "REVIEW"]
    assert len(auto) == 9
    assert len(review) == 9


def test_ten_file_auto_dung_nhu_mong_doi(rehearsal):
    got = {
        d.target_file
        for d in rehearsal.documents
        if d.final_status == "AUTO"
    }
    assert got == {
        "04.Phieu_bo_sung_ho_so_dang_vien.pdf",
        "05.Quyet_dinh_ket_nap_dang_vien.pdf",
        "07.Quyet_dinh_cong_nhan_dang_vien_chinh_thuc.pdf",
        "19.Quyet_dinh_phat_the_dang_vien_cho_ca_nhan_dang_vien.pdf",
        "70.Bang_chung_chi_ly_luan_chinh_tri_so_cap_trung_cap_cao_cap_cu_nhan.pdf",
        "75.Khai_sinh_goc_Ket_luan_dinh_chinh_ngay_thang_nam_sinh_cua_co_quan_co_tham_quyen.pdf",
        "87.Cac_quyet_dinh_dieu_dong_bo_nhiem.1.pdf",
        "87.Cac_quyet_dinh_dieu_dong_bo_nhiem.2.pdf",
        "87.Cac_quyet_dinh_dieu_dong_bo_nhiem.3.pdf",
    }


def test_nhom_87_danh_so_tu_cu_den_moi(rehearsal):
    seq = {
        d.sequence_index: d.classification.document_date
        for d in rehearsal.documents
        if d.classification.type_id == "87" and d.final_status == "AUTO"
    }
    assert seq == {1: "2015-09-23", 2: "2015-11-03", 3: "2015-11-10"}


def test_nhom_86_bi_chan_dung_vi_trung_ngay_khong_phai_vi_thieu_ngay(rehearsal):
    """Sau khi Agent đọc thật, mọi văn bằng 86 đều có ngày; chỉ còn kẹt vì TRÙNG ngày."""
    g86 = [d for d in rehearsal.documents if d.classification.type_id == "86"]
    assert len(g86) == 9
    auto_pool = [d for d in g86 if d.classification_status == "AUTO"]
    assert len(auto_pool) == 8
    assert all(d.classification.document_date for d in auto_pool), "còn văn bằng thiếu ngày"

    reasons = set()
    for d in auto_pool:
        reasons |= set(d.final_reasons)
    assert "ORDERING_DUPLICATE_DATE" in reasons
    assert "ORDERING_MISSING_RELIABLE_DATE" not in reasons

    dates = [d.classification.document_date for d in auto_pool]
    assert dates.count("2015-01-26") == 2  # chứng chỉ tiếng Anh A1 và tin học A cùng ngày


def test_bang_thpt_van_giu_review_theo_golden(rehearsal):
    d = next(x for x in rehearsal.documents if x.document.source_pages == [17, 18])
    assert d.classification.type_id == "86"
    assert d.classification_status == "REVIEW"
    assert "LOW_CONFIDENCE" in d.classification_reasons
    assert "AGENT_FLAGGED_REVIEW" in d.classification_reasons


def test_khai_sinh_ghep_mat_truoc_mat_sau(rehearsal):
    d = next(x for x in rehearsal.documents if x.document.source_pages == [6, 7])
    assert d.classification.type_id == "75"
    assert d.document.page_roles == {6: "CONTENT", 7: "BACK_SIDE"}
    assert d.final_status == "AUTO"


def test_khong_co_lech_segmentation_giua_agent_va_code(rehearsal):
    for d in rehearsal.documents:
        assert "AGENT_SEGMENTATION_MISMATCH" not in d.document.segmentation_flags
