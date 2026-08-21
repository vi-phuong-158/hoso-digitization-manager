"""Hàng rào hợp đồng Agent -> code local.

Agent làm nhận thức, code local quyết định. JSON sai hợp đồng phải bị TỪ CHỐI,
không được đoán hộ, không được tự sửa.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent_contract import (
    AnalysisContractError,
    load_analysis,
    parse_analysis,
    to_classification,
)
from app.pipeline import Workspace, process_person_folder
from app.providers.agent_provider import AgentAnalysisProvider


def base_doc(**over):
    d = {
        "source_pages": [1, 2],
        "type_id": "86",
        "confidence": 0.97,
        "document_date": "2023-05-15",
        "date_confidence": 0.96,
        "title_short": "Bằng cử nhân",
        "needs_review": False,
        "review_reason": None,
    }
    d.update(over)
    return d


def base_page(n=1, **over):
    p = {
        "page_number": n,
        "page_role": "CONTENT",
        "title_guess": "X",
        "document_date": None,
        "date_confidence": 0.0,
        "type_candidates": [{"type_id": "86", "confidence": 0.9}],
        "starts_new_document": True,
        "continues_previous": False,
        "attach_hint": "NONE",
        "attach_hint_confidence": 0.0,
        "notes": None,
    }
    p.update(over)
    return p


def payload(**over):
    d = {
        "schema_version": "1.0",
        "person_folder": "X",
        "source_file": "a.pdf",
        "page_count": 2,
        "pages": [base_page(1), base_page(2, page_role="COVER", starts_new_document=False)],
        "documents": [base_doc()],
    }
    d.update(over)
    return d


def parse(catalog, **over):
    return parse_analysis(json.dumps(payload(**over), ensure_ascii=False), catalog)


# ---------------- hợp lệ ----------------
def test_json_dung_hop_dong_thi_qua(catalog):
    a = parse(catalog)
    assert a.page_count == 2
    assert a.proposed_groups() == [[1, 2]]
    assert a.document_for([1, 2]).type_id == "86"
    assert a.document_for([1]) is None


def test_chuyen_thanh_classification_giu_co_review_cua_agent(catalog):
    a = parse(catalog, documents=[base_doc(needs_review=True, review_reason="không chắc")])
    c = to_classification(a.documents[0])
    assert c.provider_needs_review is True
    assert c.provider_review_reason == "không chắc"


# ---------------- JSON hỏng / schema ----------------
def test_json_hong_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="JSON hỏng"):
        parse_analysis("{ khong phai json", catalog)


def test_schema_version_la_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="schema_version"):
        parse(catalog, schema_version="9.9")


def test_thieu_truong_bat_buoc_bi_tu_choi(catalog):
    body = payload()
    del body["documents"]
    with pytest.raises(AnalysisContractError, match="documents"):
        parse_analysis(json.dumps(body), catalog)


# ---------------- taxonomy ----------------
def test_type_ngoai_taxonomy_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="không có trong document_types.json"):
        parse(catalog, documents=[base_doc(type_id="105")])


def test_type_bia_dat_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="không có trong document_types.json"):
        parse(catalog, documents=[base_doc(type_id="BANG_CAP")])


def test_unknown_van_hop_le(catalog):
    a = parse(catalog, documents=[base_doc(type_id="UNKNOWN", confidence=0.4)])
    assert a.documents[0].type_id == "UNKNOWN"


# ---------------- trang ----------------
def test_page_ngoai_pham_vi_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="ngoài phạm vi"):
        parse(catalog, documents=[base_doc(source_pages=[1, 5])])


def test_page_bi_thieu_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="chưa thuộc logical document"):
        parse(catalog, documents=[base_doc(source_pages=[1])])


def test_page_overlap_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="overlap"):
        parse(
            catalog,
            documents=[base_doc(source_pages=[1, 2]), base_doc(source_pages=[2])],
        )


def test_page_lap_trong_cung_tai_lieu_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="lặp"):
        parse(catalog, documents=[base_doc(source_pages=[1, 1, 2])])


def test_logical_document_rong_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="không rỗng"):
        parse(catalog, documents=[base_doc(source_pages=[])])


def test_dao_thu_tu_trang_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="không được đảo"):
        parse(catalog, documents=[base_doc(source_pages=[2, 1])])


def test_pages_bo_sot_trang_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="bỏ sót trang"):
        parse(catalog, pages=[base_page(1)])


def test_pages_lap_trang_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="lặp"):
        parse(catalog, pages=[base_page(1), base_page(1), base_page(2)])


def test_page_role_la_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="page_role"):
        parse(catalog, pages=[base_page(1, page_role="BIA"), base_page(2)])


# ---------------- kiểu dữ liệu ----------------
def test_confidence_sai_kieu_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="phải là số"):
        parse(catalog, documents=[base_doc(confidence="cao")])


def test_confidence_ngoai_khoang_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="ngoài khoảng"):
        parse(catalog, documents=[base_doc(confidence=1.4)])


def test_ngay_sai_dinh_dang_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="yyyy-mm-dd"):
        parse(catalog, documents=[base_doc(document_date="15/05/2023")])


def test_ngay_khong_ton_tai_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="yyyy-mm-dd"):
        parse(catalog, documents=[base_doc(document_date="2023-02-30")])


def test_needs_review_sai_kieu_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="true/false"):
        parse(catalog, documents=[base_doc(needs_review="yes")])


# ---------------- Agent không được đặt tên file ----------------
@pytest.mark.parametrize(
    "key",
    ["target_file", "filename", "file_name", "output_name", "sequence", "status", "target_dir"],
)
def test_agent_gui_ten_file_bi_tu_choi(catalog, key):
    with pytest.raises(AnalysisContractError, match="naming engine local"):
        parse(catalog, documents=[base_doc(**{key: "86.bang.pdf"})])


# ---------------- chống ghi toàn văn hồ sơ ----------------
def test_title_short_qua_dai_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="quá dài"):
        parse(catalog, documents=[base_doc(title_short="x" * 400)])


def test_notes_qua_dai_bi_tu_choi(catalog):
    with pytest.raises(AnalysisContractError, match="quá dài"):
        parse(catalog, pages=[base_page(1, notes="y" * 500), base_page(2)])


# ---------------- khớp file thật ----------------
def test_page_count_khong_khop_pdf_that_bi_tu_choi(tmp_path: Path, catalog):
    body = payload(source_file="Bang cap cua HAI.pdf", page_count=2)
    p = tmp_path / "x.json"
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AnalysisContractError, match="page_count"):
        load_analysis(p, catalog, expect_source="Bang cap cua HAI.pdf", expect_pages=20)


def test_source_file_khong_khop_bi_tu_choi(tmp_path: Path, catalog):
    p = tmp_path / "x.json"
    p.write_text(json.dumps(payload()), encoding="utf-8")
    with pytest.raises(AnalysisContractError, match="source_file"):
        load_analysis(p, catalog, expect_source="khac.pdf")


def test_thieu_file_phan_tich_thi_bao_loi_ro_rang(tmp_path: Path, catalog):
    with pytest.raises(AnalysisContractError, match="Chưa có file phân tích"):
        load_analysis(tmp_path / "khong-co.json", catalog)


def test_ho_so_chua_co_analysis_thi_pipeline_dung_lai(tmp_path: Path, hai_folder: Path):
    import shutil

    folder = tmp_path / "input" / "NGUOI_MOI"
    folder.mkdir(parents=True)
    shutil.copy2(hai_folder / "Phieu bo sung hs dang vien 2020 HAI.pdf", folder)
    with pytest.raises(AnalysisContractError, match="Chưa có file phân tích"):
        process_person_folder(folder, provider_name="agent", workspace=Workspace(tmp_path))


# ---------------- đối chiếu chéo segmentation ----------------
def test_agent_gom_trang_khac_segmenter_thi_sang_review(tmp_path: Path, hai_folder: Path, catalog):
    """Agent tách bìa ra khỏi văn bằng -> lệch segmenter local -> REVIEW."""
    src = Path("analysis/Nguyễn Hữu Hải/Bang cap cua HAI.json")
    data = json.loads(src.read_text(encoding="utf-8"))
    # Tách nhóm [1,2] thành [1] và [2].
    data["documents"] = [
        {**data["documents"][0], "source_pages": [1]},
        {**data["documents"][0], "source_pages": [2]},
    ] + data["documents"][1:]

    root = tmp_path / "analysis" / hai_folder.name
    root.mkdir(parents=True)
    (root / "Bang cap cua HAI.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    for name in ("Quyet dinh dieu dong HAI", "Phieu bo sung hs dang vien 2020 HAI"):
        (root / f"{name}.json").write_text(
            Path(f"analysis/Nguyễn Hữu Hải/{name}.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    result = process_person_folder(
        hai_folder,
        provider_name="agent",
        provider_config={"analysis_root": str(tmp_path / "analysis")},
        workspace=Workspace(tmp_path),
        write_manifest=False,
    )
    doc = next(d for d in result.documents if d.document.source_pages == [1, 2])
    assert doc.final_status == "REVIEW"
    assert "AGENT_SEGMENTATION_MISMATCH" in doc.document.segmentation_flags
    assert result.qc.passed  # vẫn phủ 100% trang, không mất trang nào


def test_provider_khong_bao_gio_tra_ve_ten_file(catalog, hai_folder: Path):
    p = AgentAnalysisProvider({"catalog": catalog})
    res = p.classify_document(hai_folder / "Bang cap cua HAI.pdf", [3, 4], [])
    assert not hasattr(res, "target_file")
    assert res.type_id == "86"
    assert res.runner_up is not None and res.runner_up.type_id == "70"
