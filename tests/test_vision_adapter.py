"""Ranh giới provider: hàng rào validate + adapter Gemini (phần thuần, không mạng)."""
from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from app.models import DocumentClassification, PageObservation, TypeCandidate, UNKNOWN
from app.providers.gemini_provider import (
    GeminiVisionProvider,
    build_classification_prompt,
    build_page_analysis_prompt,
    extract_json,
    extract_pages_bytes,
    parse_classification,
    parse_page_analysis,
)
from app.vision_adapter import (
    ProviderError,
    available_providers,
    get_provider,
    validate_classification,
    validate_page_observation,
)


# ---------------- registry ----------------
def test_runtime_chi_co_provider_khong_goi_mang():
    """Runtime là Antigravity-native: registry chỉ được có provider offline."""
    assert set(available_providers()) == {"agent", "fixture"}


def test_gemini_khong_nam_trong_runtime_registry():
    from app.providers import gemini_provider

    assert gemini_provider.NOT_USED_IN_ANTIGRAVITY_RUNTIME is True
    with pytest.raises(ProviderError, match="chưa đăng ký"):
        get_provider("gemini")


def test_provider_la_thi_bao_loi():
    with pytest.raises(ProviderError, match="chưa đăng ký"):
        get_provider("khong-ton-tai")


# ---------------- hàng rào validate ----------------
def test_chan_type_id_ngoai_catalog(catalog):
    obs = PageObservation(page_number=1, type_candidates=[TypeCandidate("999", 0.9)])
    with pytest.raises(ProviderError, match="không có trong catalog"):
        validate_page_observation(obs, catalog, "test")


def test_chan_page_role_la(catalog):
    obs = PageObservation(page_number=1, page_role="BIA")  # type: ignore[arg-type]
    with pytest.raises(ProviderError, match="page_role"):
        validate_page_observation(obs, catalog, "test")


def test_chan_ngay_sai_dinh_dang(catalog):
    obs = PageObservation(page_number=1, document_date="15/05/2023")
    with pytest.raises(ProviderError, match="yyyy-mm-dd"):
        validate_page_observation(obs, catalog, "test")


def test_chan_confidence_ngoai_khoang(catalog):
    obs = PageObservation(page_number=1, date_confidence=1.5)
    with pytest.raises(ProviderError, match="ngoài"):
        validate_page_observation(obs, catalog, "test")


def test_chan_model_nhet_toan_van_vao_title(catalog):
    res = DocumentClassification(type_id="05", confidence=0.99, title_short="x" * 500)
    with pytest.raises(ProviderError, match="quá dài"):
        validate_classification(res, catalog, "test")


def test_unknown_luon_hop_le(catalog):
    res = DocumentClassification(type_id=UNKNOWN, confidence=0.4)
    assert validate_classification(res, catalog, "test").type_id == UNKNOWN


# ---------------- prompt builder ----------------
def test_prompt_doc_trang_co_du_danh_muc_va_cam_dat_ten(catalog):
    p = build_page_analysis_prompt(catalog, [1, 2])
    assert "KHÔNG được đặt tên file" in p
    assert "86: " in p and "104: " in p
    assert "[1, 2]" in p


def test_prompt_phan_loai_second_pass_khong_ap_dat_ket_luan_vong_1(catalog):
    p = build_classification_prompt(
        catalog, [1, 2], [TypeCandidate("86", 0.9), TypeCandidate("70", 0.5)], second_pass=True
    )
    assert "Kết luận lượt trước CHỈ là tham khảo" in p
    assert "86(0.90)" in p
    assert "Không đặt tên file" in p


# ---------------- response parser ----------------
def test_parse_page_analysis_hop_le(catalog):
    text = """```json
    {"pages": [{"page_number": 1, "page_role": "content", "title_guess": "Quyết định kết nạp đảng viên",
                "document_date": "2018-08-19", "date_confidence": 0.95,
                "type_candidates": [{"type_id": "05", "confidence": 0.98}],
                "starts_new_document": true, "attach_hint": "none"}]}
    ```"""
    out = parse_page_analysis(text, [1], catalog)
    assert out[0].page_role == "CONTENT"
    assert out[0].attach_hint == "NONE"
    assert out[0].type_candidates[0].type_id == "05"


def test_parse_page_analysis_bo_sot_trang_thi_bao_loi(catalog):
    text = '{"pages": [{"page_number": 1, "type_candidates": []}]}'
    with pytest.raises(ProviderError, match="bỏ sót trang"):
        parse_page_analysis(text, [1, 2], catalog)


def test_parse_page_analysis_type_id_bia_dat_bi_chan(catalog):
    text = '{"pages": [{"page_number": 1, "type_candidates": [{"type_id": "BANG_CAP", "confidence": 0.9}]}]}'
    with pytest.raises(ProviderError, match="không có trong catalog"):
        parse_page_analysis(text, [1], catalog)


def test_parse_classification(catalog):
    text = 'Đây là kết quả: {"type_id": "86", "confidence": 0.97, "document_date": "2023-05-15", "date_confidence": 0.96, "title_short": "Bằng cử nhân", "runner_up": {"type_id": "70", "confidence": 0.1}}'
    res = parse_classification(text, catalog)
    assert res.type_id == "86"
    assert res.runner_up.type_id == "70"
    assert res.document_date == "2023-05-15"


def test_parse_json_hong_thi_bao_loi_ro():
    with pytest.raises(ProviderError, match="JSON không hợp lệ"):
        extract_json("{khong phai json")


# ---------------- cắt trang gửi model ----------------
def test_extract_pages_bytes_giu_page_object(hai_folder: Path, tmp_path: Path):
    src = hai_folder / "Bang cap cua HAI.pdf"
    data = extract_pages_bytes(src, [3, 4])
    out = tmp_path / "x.pdf"
    out.write_bytes(data)
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2
    source = PdfReader(str(src))
    assert reader.pages[0].extract_text() == source.pages[2].extract_text()


# ---------------- an toàn mạng ----------------
def test_gemini_mac_dinh_chan_mang(catalog, hai_folder: Path):
    p = GeminiVisionProvider({"catalog": catalog})
    with pytest.raises(ProviderError, match="chặn mạng"):
        p.analyze_pages(hai_folder / "Bang cap cua HAI.pdf", [1])


def test_gemini_dung_transport_cam_vao_duoc(catalog, hai_folder: Path):
    """Adapter hoạt động end-to-end với transport giả -> business logic không cần biết Gemini."""
    calls: list[str] = []

    def fake_transport(prompt: str, pdf_bytes: bytes, model: str) -> str:
        calls.append(model)
        assert pdf_bytes.startswith(b"%PDF")
        return (
            '{"pages": [{"page_number": 1, "page_role": "CONTENT",'
            ' "title_guess": "Giấy chứng nhận", "document_date": null, "date_confidence": 0,'
            ' "type_candidates": [{"type_id": "86", "confidence": 0.96}],'
            ' "starts_new_document": true, "attach_hint": "NONE"}]}'
        )

    p = GeminiVisionProvider({"catalog": catalog, "transport": fake_transport, "model": "m-test"})
    out = p.analyze_pages(hai_folder / "Bang cap cua HAI.pdf", [1])
    assert out[0].type_candidates[0].type_id == "86"
    assert calls == ["m-test"]
    assert p.describe()["provider"] == "gemini"
