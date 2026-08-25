"""DEV POLICY CLOSURE — 4 policy phát sinh sau blind runtime test trên corpus tổng hợp.

Không đụng thư mục dữ liệu thật/*.pdf. Dùng PDF/JSON tổng hợp từ
state_testkit, y hệt các test incremental khác. Bốn nhóm đúng theo yêu cầu
nhiệm vụ (mục 20): type 87 (subtype), supporting document, duplicate,
partial date precision - cộng nhóm regression bảo vệ baseline/blind/golden.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.catalog import load_catalog
from app.global_naming import (
    NameableDoc,
    R_ORDER_AMBIGUOUS,
    compute_global_assignment,
    orderability_reasons,
)
from app.golden import run_all_golden
from app.models import MODE_APPLY, MODE_DRY_RUN, PipelineError
from app.naming import auto_filename
from app.pdf_inventory import sha256_file
from app.pipeline import Workspace, process_person_folder
from app.policy import (
    CLASSIFICATION_KIND_DUPLICATE,
    CLASSIFICATION_KIND_SUPPORTING,
    CLASSIFICATION_KIND_TAXONOMY,
    DATE_PRECISION_DAY,
    DATE_PRECISION_MONTH,
    DATE_PRECISION_UNKNOWN,
    DATE_PRECISION_YEAR,
    SUBTYPE_APPOINTMENT,
    SUBTYPE_ASSIGNMENT,
    SUBTYPE_OTHER_PERSONNEL_DECISION,
    SUBTYPE_PROMOTION_SALARY,
    SUBTYPE_RETIREMENT,
    SUBTYPE_TRANSFER,
    derive_personnel_subtype,
    parse_partial_date,
    supporting_filename,
)
from app.policy_rehearsal import deterministic_resolutions, extract_month_year_from_notes, rehearse
from app.review import resolve_review
from app.state import StateRegistry
from state_testkit import add_source

# ---------------------------------------------------------------------------
# harness dùng chung (giống test_incremental_pipeline.py)
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path: Path):
    ws = Workspace(tmp_path)
    input_root = tmp_path / "input"
    analysis_root = tmp_path / "analysis"
    registry = StateRegistry(ws.state_db_path)
    yield tmp_path, ws, input_root, analysis_root, registry
    registry.close()


def run(ws, folder, registry, *, mode=MODE_DRY_RUN, analysis_root=None, **kw):
    analysis_root = analysis_root or (ws.root / "analysis")
    return process_person_folder(
        folder, mode=mode, provider_name="agent",
        provider_config={"analysis_root": str(analysis_root)},
        workspace=ws, state_registry=registry, **kw,
    )


def logical_id_for(registry, person, source_pdf_path, pages):
    from app.pdf_inventory import sha256_file
    from app.state import logical_document_id

    return logical_document_id(sha256_file(source_pdf_path), list(pages))


# ===========================================================================
# Nhóm 1 — Policy 1: quyết định nhân sự -> type 87 + subtype
# ===========================================================================
def test_derive_subtype_tu_khoa_dieu_dong_bo_tri_bo_nhiem_nghi_huu():
    assert derive_personnel_subtype("Quyết định về việc điều động cán bộ") == SUBTYPE_TRANSFER
    assert derive_personnel_subtype("Quyết định về việc bố trí cán bộ") == SUBTYPE_ASSIGNMENT
    assert derive_personnel_subtype("Quyết định bổ nhiệm chức vụ Đội trưởng") == SUBTYPE_APPOINTMENT
    assert (
        derive_personnel_subtype("Quyết định thăng cấp bậc hàm, nâng bậc lương năm 2023")
        == SUBTYPE_PROMOTION_SALARY
    )
    assert derive_personnel_subtype("Quyết định nghỉ hưu") == SUBTYPE_RETIREMENT
    assert derive_personnel_subtype("Một tài liệu nhân sự khác") == SUBTYPE_OTHER_PERSONNEL_DECISION


def test_resolve_review_type87_subtype_luu_vao_state(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "qd.pdf", type_id="87", confidence=0.75,
        document_date="2017-05-29", needs_review=True,
        review_reason="Quyết định thăng cấp bậc hàm nâng bậc lương",
        title="Quyết định thăng cấp bậc hàm, nâng bậc lương năm 2017",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    row = resolve_review(
        registry, catalog, lid, type_id="87", subtype=SUBTYPE_PROMOTION_SALARY,
    )
    assert row.effective_classification_kind == CLASSIFICATION_KIND_TAXONOMY
    assert row.effective_type_id == "87"
    assert row.effective_subtype == SUBTYPE_PROMOTION_SALARY
    # roundtrip qua registry
    reloaded = registry.get_logical_document(lid)
    assert reloaded.effective_subtype == SUBTYPE_PROMOTION_SALARY


def test_subtype_khong_doi_ten_file_chinh_thuc_cua_type_87(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "qd.pdf", type_id="87", confidence=0.75,
        document_date="2017-05-29", needs_review=True, review_reason="thang ham",
        title="Quyết định thăng cấp bậc hàm",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid, type_id="87", subtype=SUBTYPE_PROMOTION_SALARY)
    result = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"
    row = registry.get_logical_document(lid)
    assert row.current_target_filename == auto_filename(catalog, "87")
    assert "promotion_salary" not in row.current_target_filename


def test_resolve_review_subtype_khong_hop_le_bi_tu_choi(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "qd.pdf", type_id="87", confidence=0.75,
        needs_review=True, review_reason="thang ham",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid, type_id="87", subtype="khong_ton_tai")


def test_resolve_review_subtype_non87_bi_tu_choi(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "non87.pdf", type_id="04", needs_review=True,
        review_reason="LOW_CONFIDENCE",
    )
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError, match="type-id 87"):
        resolve_review(registry, catalog, lid, type_id="04", subtype=SUBTYPE_PROMOTION_SALARY)


# ===========================================================================
# Nhóm 2 — Policy 2: ngoài taxonomy -> SUPPORTING_DOCUMENT
# ===========================================================================
def test_unknown_khong_tu_dong_thanh_supporting(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(
        input_root, analysis_root, "P", "bc.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="Không có mã khớp trong danh mục",
        title="Báo cáo kết nạp đảng viên",
    )
    result = run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    row = result.manifest["documents"][0]
    assert row["classification_kind"] == CLASSIFICATION_KIND_TAXONOMY
    assert row["needs_review"] is True


def test_human_resolve_supporting_document(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "bc.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="ngoai danh muc", title="Báo cáo kết nạp đảng viên",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    row = resolve_review(registry, catalog, lid, supporting=True)
    assert row.effective_classification_kind == CLASSIFICATION_KIND_SUPPORTING


def test_supporting_filename_deterministic_khong_dung_stt_gia(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "bc.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="ngoai danh muc", title="Báo cáo kết nạp đảng viên",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid, supporting=True)
    result = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"
    row = registry.get_logical_document(lid)
    assert row.current_target_filename == "SUPPORTING.Bao_Cao_Ket_Nap_Dang_Vien.pdf"
    assert (ws.output / "P" / row.current_target_filename).is_file()
    catalog_bases = {t.filename_base for t in catalog.all_types()}
    assert row.current_target_filename.replace(".pdf", "") not in catalog_bases


def test_supporting_trung_tieu_de_duoc_danh_so_global(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf1 = add_source(
        input_root, analysis_root, "P", "bc1.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="ngoai danh muc", title="Báo cáo kết nạp đảng viên",
    )
    pdf2 = add_source(
        input_root, analysis_root, "P", "bc2.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="ngoai danh muc", title="Báo cáo kết nạp đảng viên",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid1 = logical_id_for(registry, "P", pdf1, [1])
    lid2 = logical_id_for(registry, "P", pdf2, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid1, supporting=True)
    resolve_review(registry, catalog, lid2, supporting=True)
    result = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"
    names = {
        registry.get_logical_document(lid1).current_target_filename,
        registry.get_logical_document(lid2).current_target_filename,
    }
    assert names == {
        "SUPPORTING.Bao_Cao_Ket_Nap_Dang_Vien.1.pdf",
        "SUPPORTING.Bao_Cao_Ket_Nap_Dang_Vien.2.pdf",
    }


def test_resolve_review_khong_duoc_chon_ca_type_id_va_supporting(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "bc.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="ngoai danh muc",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid, type_id="04", supporting=True)


# ===========================================================================
# Nhóm 3 — Policy 3: duplicate page/document
# ===========================================================================
def test_duplicate_confirmed_khong_tao_output_thu_hai(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    input_root_p = input_root / "P"
    input_root_p.mkdir(parents=True, exist_ok=True)
    from state_testkit import make_pdf, make_analysis
    import json as _json

    pdf_path = make_pdf(input_root_p / "bc.pdf", n_pages=2)
    stem = "bc"
    payload = {
        "schema_version": "1.0", "produced_by": "test-synthetic", "person_folder": "P",
        "source_file": "bc.pdf", "page_count": 2,
        "pages": [
            {"page_number": 1, "page_role": "CONTENT", "title_guess": "Báo cáo kết nạp đảng viên",
             "document_date": "2014-06-07", "date_confidence": 0.9,
             "type_candidates": [{"type_id": "UNKNOWN", "confidence": 0.75}],
             "starts_new_document": True, "continues_previous": False,
             "attach_hint": "NONE", "attach_hint_confidence": 0.0, "notes": None},
            {"page_number": 2, "page_role": "CONTENT", "title_guess": "Báo cáo kết nạp đảng viên (bản trùng)",
             "document_date": "2014-06-07", "date_confidence": 0.9,
             "type_candidates": [{"type_id": "UNKNOWN", "confidence": 0.75}],
             "starts_new_document": True, "continues_previous": False,
             "attach_hint": "NONE", "attach_hint_confidence": 0.0, "notes": "scan lặp trang 1"},
        ],
        "documents": [
            {"source_pages": [1], "type_id": "UNKNOWN", "confidence": 0.75, "document_date": "2014-06-07",
             "date_confidence": 0.9, "title_short": "Báo cáo kết nạp đảng viên",
             "needs_review": True, "review_reason": "ngoai danh muc"},
            {"source_pages": [2], "type_id": "UNKNOWN", "confidence": 0.75, "document_date": "2014-06-07",
             "date_confidence": 0.9, "title_short": "Báo cáo kết nạp đảng viên (bản trùng)",
             "needs_review": True, "review_reason": "nghi trung lap voi trang 1"},
        ],
    }
    out = analysis_root / "P" / f"{stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    run(ws, input_root_p, registry, mode=MODE_DRY_RUN)
    lid1 = logical_id_for(registry, "P", pdf_path, [1])
    lid2 = logical_id_for(registry, "P", pdf_path, [2])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid1, supporting=True)
    resolve_review(registry, catalog, lid2, duplicate_of=lid1)

    result = run(ws, input_root_p, registry, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"

    row1 = registry.get_logical_document(lid1)
    row2 = registry.get_logical_document(lid2)
    assert row1.current_target_filename is not None
    assert row2.current_target_filename is None
    assert row2.effective_classification_kind == CLASSIFICATION_KIND_DUPLICATE

    output_files = list((ws.output / "P").glob("*.pdf"))
    assert len(output_files) == 1

    src_hash = row1.source_hash
    assert registry.get(src_hash).status == "PROCESSED"


def test_duplicate_relation_luu_trong_manifest(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf1 = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2020-01-01",
    )
    pdf2 = add_source(
        input_root, analysis_root, "P", "b.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid_original = logical_id_for(registry, "P", pdf1, [1])
    lid_dup = logical_id_for(registry, "P", pdf2, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid_dup, duplicate_of=lid_original)
    result = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"
    by_id = {d["logical_document_id"]: d for d in result.manifest["documents"]}
    assert by_id[lid_dup]["classification_kind"] == CLASSIFICATION_KIND_DUPLICATE
    assert by_id[lid_dup]["duplicate_of"] == lid_original
    assert by_id[lid_dup]["current_target_filename"] is None


def test_duplicate_khong_lam_thay_doi_hash_nguon(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf1 = add_source(input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2020-01-01")
    pdf2 = add_source(
        input_root, analysis_root, "P", "b.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap",
    )
    before1, before2 = sha256_file(pdf1), sha256_file(pdf2)
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid_original = logical_id_for(registry, "P", pdf1, [1])
    lid_dup = logical_id_for(registry, "P", pdf2, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid_dup, duplicate_of=lid_original)
    run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert sha256_file(pdf1) == before1
    assert sha256_file(pdf2) == before2


def test_duplicate_khong_the_tro_toi_chinh_no(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid, duplicate_of=lid)


def test_duplicate_of_khong_ton_tai_bi_tu_choi(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid, duplicate_of="khong_ton_tai" * 4)


def test_duplicate_khong_the_tro_toi_mot_duplicate_khac(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf1 = add_source(input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2020-01-01")
    pdf2 = add_source(
        input_root, analysis_root, "P", "b.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap 1",
    )
    pdf3 = add_source(
        input_root, analysis_root, "P", "c.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap 2",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid1 = logical_id_for(registry, "P", pdf1, [1])
    lid2 = logical_id_for(registry, "P", pdf2, [1])
    lid3 = logical_id_for(registry, "P", pdf3, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid2, duplicate_of=lid1)
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid3, duplicate_of=lid2)


def test_duplicate_confirmation_idempotent_khong_the_resolve_lai(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf1 = add_source(input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2020-01-01")
    pdf2 = add_source(
        input_root, analysis_root, "P", "b.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid1 = logical_id_for(registry, "P", pdf1, [1])
    lid2 = logical_id_for(registry, "P", pdf2, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid2, duplicate_of=lid1)
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid2, duplicate_of=lid1)
    # apply 2 lần liên tiếp không tạo thêm output / không lỗi
    r1 = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    r2 = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert r1.status == "APPLY_PASS"
    assert r2.status == "APPLY_PASS"
    assert len(list((ws.output / "P").glob("*.pdf"))) == 1


def test_nghi_ngo_trung_lap_chua_chac_van_giu_review(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "b.pdf", type_id="UNKNOWN", confidence=0.75,
        needs_review=True, review_reason="nghi trung lap nhung chua xac nhan",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    result = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    lid = logical_id_for(registry, "P", pdf, [1])
    row = registry.get_logical_document(lid)
    assert row.resolution_status == "REVIEW_PENDING"
    assert row.effective_classification_kind == CLASSIFICATION_KIND_TAXONOMY
    assert registry.get(row.source_hash).status == "REVIEW_REQUIRED"


# ===========================================================================
# Nhóm 4 — Policy 4: partial date precision
# ===========================================================================
def test_parse_partial_date_day():
    assert parse_partial_date("2023-05-19") == ("2023-05-19", DATE_PRECISION_DAY)


def test_parse_partial_date_month():
    assert parse_partial_date("2023-11") == ("2023-11", DATE_PRECISION_MONTH)


def test_parse_partial_date_year():
    assert parse_partial_date("2023") == ("2023", DATE_PRECISION_YEAR)


def test_parse_partial_date_none_la_unknown():
    assert parse_partial_date(None) == (None, DATE_PRECISION_UNKNOWN)
    assert parse_partial_date("") == (None, DATE_PRECISION_UNKNOWN)


def test_parse_partial_date_sai_dinh_dang_bi_tu_choi():
    with pytest.raises(PipelineError):
        parse_partial_date("2023/11/05")
    with pytest.raises(PipelineError):
        parse_partial_date("2023-13")


def test_sap_xep_an_toan_qua_nhieu_do_chinh_xac():
    docs = [
        NameableDoc("a", "ha", (1,), "2022-11-17", 0.95, "T1", date_precision=DATE_PRECISION_DAY),
        NameableDoc("b", "hb", (1,), "2023-11", 0.95, "T2", date_precision=DATE_PRECISION_MONTH),
        NameableDoc("c", "hc", (1,), "2024-11-04", 0.95, "T3", date_precision=DATE_PRECISION_DAY),
    ]
    assert orderability_reasons(docs) == []
    catalog = load_catalog()
    assignment, reasons = compute_global_assignment(catalog, "04", docs)
    assert reasons == []
    order = {a.logical_document_id: a.sequence_index for a in assignment}
    assert order["a"] < order["b"] < order["c"]


def test_thang_va_ngay_cung_thang_la_ambiguous():
    docs = [
        NameableDoc("a", "ha", (1,), "2023-11", 0.95, "T1", date_precision=DATE_PRECISION_MONTH),
        NameableDoc("b", "hb", (1,), "2023-11-05", 0.95, "T2", date_precision=DATE_PRECISION_DAY),
    ]
    reasons = orderability_reasons(docs)
    assert R_ORDER_AMBIGUOUS in reasons


def test_nam_va_thang_cung_nam_la_ambiguous():
    docs = [
        NameableDoc("a", "ha", (1,), "2023", 0.95, "T1", date_precision=DATE_PRECISION_YEAR),
        NameableDoc("b", "hb", (1,), "2023-05", 0.95, "T2", date_precision=DATE_PRECISION_MONTH),
    ]
    reasons = orderability_reasons(docs)
    assert R_ORDER_AMBIGUOUS in reasons


def test_ambiguous_khong_tu_gia_dinh_thu_tu():
    docs = [
        NameableDoc("a", "ha", (1,), "2023-11", 0.95, "T1", date_precision=DATE_PRECISION_MONTH),
        NameableDoc("b", "hb", (1,), "2023-11-05", 0.95, "T2", date_precision=DATE_PRECISION_DAY),
    ]
    catalog = load_catalog()
    assignment, reasons = compute_global_assignment(catalog, "04", docs)
    assert assignment == []
    assert reasons


def test_resolve_review_date_precision_khong_khop_bi_tu_choi(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="04", confidence=0.99,
        needs_review=True, review_reason="thieu ngay",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid, document_date="2023-11", date_precision="DAY")


def test_partial_date_roundtrip_qua_state_va_manifest(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="04", confidence=0.99,
        needs_review=True, review_reason="chi ghi thang, thieu ngay",
        title="Phiếu bổ sung hồ sơ đảng viên năm 2023",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    resolve_review(registry, catalog, lid, document_date="2023-11")
    result = run(ws, input_root / "P", registry, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"
    row = registry.get_logical_document(lid)
    assert row.effective_document_date == "2023-11"
    assert row.effective_date_precision == DATE_PRECISION_MONTH
    by_id = {d["logical_document_id"]: d for d in result.manifest["documents"]}
    assert by_id[lid]["document_date"] == "2023-11"
    assert by_id[lid]["date_precision"] == DATE_PRECISION_MONTH


def test_khong_fake_ngay_khi_chi_co_thang(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="04", confidence=0.99,
        needs_review=True, review_reason="chi ghi thang",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    row = resolve_review(registry, catalog, lid, document_date="2023-11")
    assert row.effective_document_date == "2023-11"
    assert "2023-11-01" != row.effective_document_date


# ===========================================================================
# Nhóm 5 — Regression: baseline/blind/golden không suy suyển
# ===========================================================================
def test_golden_van_pass_provider_agent(golden_root: Path):
    reports = run_all_golden(golden_root, provider_name="agent")
    assert reports
    assert all(r.passed for r in reports), [str(r) for r in reports if not r.passed]


_BLIND_ANALYSIS_SHA256 = {
    "vi-phuong.json": "313d978b4db2f7f144d54935ee14f55baa5533f405adf514e7a26111c6d6fc35",
    "vi-phuong-2.json": "dd00862215245660da3ab4bd0d0ba2c7a469c98a00e778bb5c6cb93be84e7b47",
}


def test_blind_analysis_json_hash_khong_doi(repo_root: Path):
    folder = repo_root / "analysis" / "Synthetic Other Person"
    if not folder.is_dir():
        pytest.skip("Không có analysis tổng hợp bổ sung trong workspace này.")
    for name, expected in _BLIND_ANALYSIS_SHA256.items():
        assert sha256_file(folder / name) == expected, f"{name} đã bị đổi so với bản freeze!"


_VI_PHUONG_PDF_SHA256 = {
    "vi-phuong.pdf": "caf017dfe848c8e4f4edc81462eee6afb2ba329545ea7be3f317bc2bef10b673",
    "vi-phuong-2.pdf": "c0c785fdbcd817fa9a0c6543efe7556875b89b939e538cd16e295dc4f7303b48",
}


def test_vi_phuong_pdf_hash_khong_doi(repo_root: Path):
    folder = repo_root / "input" / "Synthetic Other Person"
    if not folder.is_dir():
        pytest.skip("Không có dữ liệu thật bổ sung trong workspace này.")
    for name, expected in _VI_PHUONG_PDF_SHA256.items():
        assert sha256_file(folder / name) == expected, f"{name} đã bị mutate!"


def test_policy_module_khong_import_thu_vien_mang(repo_root: Path):
    from test_runtime_no_network import NETWORK_MODULES, imported_roots

    bad = imported_roots(repo_root / "app" / "policy.py") & NETWORK_MODULES
    assert not bad


def test_extract_month_year_from_notes():
    assert extract_month_year_from_notes("Ngày để trống (chỉ ghi tháng 11 năm 2023)") == "2023-11"
    assert extract_month_year_from_notes("Không có gì đặc biệt") is None
    assert extract_month_year_from_notes(None) is None


def test_rehearsal_chi_resolve_type87_va_partial_date_khong_dung_supporting_duplicate():
    manifest = {
        "summary": {"auto_resolved": 5},
        "documents": [
            {
                "logical_document_id": "d1", "source_file": "a.pdf", "source_pages": [17],
                "type_id": "87", "title_short": "Quyết định thăng cấp bậc hàm",
                "document_date": "2017-05-29", "needs_review": True,
                "review_reason": ["LOW_CONFIDENCE", "AGENT_FLAGGED_REVIEW"],
            },
            {
                "logical_document_id": "d2", "source_file": "b.pdf", "source_pages": [2],
                "type_id": "04", "title_short": "Phiếu bổ sung 2023",
                "document_date": None, "needs_review": True,
                "review_reason": ["AGENT_FLAGGED_REVIEW"],
            },
            {
                "logical_document_id": "d3", "source_file": "b.pdf", "source_pages": [8],
                "type_id": "UNKNOWN", "title_short": "Báo cáo kết nạp đảng viên",
                "document_date": "2014-06-07", "needs_review": True,
                "review_reason": ["AGENT_FLAGGED_REVIEW", "TYPE_UNKNOWN"],
            },
        ],
    }
    raw = [
        {"source_file": "a.pdf", "pages": [{"page_number": 17, "notes": None}]},
        {
            "source_file": "b.pdf",
            "pages": [
                {"page_number": 2, "notes": "Ngày để trống (chỉ ghi tháng 11 năm 2023)"},
                {"page_number": 8, "notes": None},
            ],
        },
    ]
    report = rehearse(manifest, raw)
    assert report.auto_before == 5
    assert report.review_before == 3
    assert report.auto_after == 7
    assert report.review_after == 1
    reasons_by_id = {r.logical_document_id: r for r in report.resolutions}
    assert reasons_by_id["d1"].resolved_type_id == "87"
    assert reasons_by_id["d1"].resolved_subtype == SUBTYPE_PROMOTION_SALARY
    assert reasons_by_id["d2"].resolved_document_date == "2023-11"
    assert reasons_by_id["d2"].resolved_date_precision == DATE_PRECISION_MONTH
    assert "d3" not in reasons_by_id  # UNKNOWN/supporting KHÔNG tự resolve
    assert [d["logical_document_id"] for d in report.remaining_review] == ["d3"]


def test_rehearsal_khong_mutate_gi_ca():
    """Rehearsal là hàm thuần - gọi 2 lần cùng input phải ra cùng kết quả,
    không có side effect nào (không state DB, không file)."""
    manifest = {
        "summary": {"auto_resolved": 0},
        "documents": [
            {
                "logical_document_id": "d1", "source_file": "a.pdf", "source_pages": [1],
                "type_id": "87", "title_short": "Quyết định điều động",
                "document_date": "2018-01-01", "needs_review": True,
                "review_reason": ["LOW_CONFIDENCE"],
            },
        ],
    }
    r1 = deterministic_resolutions(manifest["documents"])
    r2 = deterministic_resolutions(manifest["documents"])
    assert r1 == r2


def test_review_module_van_tu_choi_type_id_khong_hop_le(env):
    """Regression: nhánh TAXONOMY cũ (không kèm policy mới) vẫn hoạt động y hệt."""
    tmp_path, ws, input_root, analysis_root, registry = env
    pdf = add_source(
        input_root, analysis_root, "P", "a.pdf", type_id="UNKNOWN", confidence=0.5,
        needs_review=True, review_reason="khong ro loai",
    )
    run(ws, input_root / "P", registry, mode=MODE_DRY_RUN)
    lid = logical_id_for(registry, "P", pdf, [1])
    catalog = load_catalog()
    with pytest.raises(PipelineError):
        resolve_review(registry, catalog, lid, type_id="UNKNOWN")
