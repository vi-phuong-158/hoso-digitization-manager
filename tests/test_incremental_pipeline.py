"""process_person_folder(state_registry=...) — hành vi incremental đầu-cuối.

Không đụng input/Vi Ngọc Phương/. Dùng PDF tổng hợp từ state_testkit.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.incremental import DECISION_ALREADY_PROCESSED, DECISION_NEW
from app.manifest import load_manifest
from app.models import MODE_APPLY, MODE_DRY_RUN
from app.pdf_inventory import sha256_file
from app.pipeline import Workspace, process_person_folder
from app.providers.agent_provider import AgentAnalysisProvider
from app.state import STATUS_FAILED, STATUS_PROCESSED, STATUS_REVIEW_REQUIRED, StateRegistry
from app.state_import import OUTCOME_ALREADY_IN_REGISTRY, OUTCOME_IMPORTED, import_person_folder
from app.vision_adapter import DocumentVisionProvider
from state_testkit import add_source


class CountingProvider(DocumentVisionProvider):
    """Bọc AgentAnalysisProvider, đếm những PDF thực sự được yêu cầu đọc.

    Dùng để CHỨNG MINH nguồn PROCESSED không bị Agent đọc lại - đây là yêu cầu
    cứng của nhiệm vụ, không chỉ là hệ quả tình cờ của việc filter documents.
    """

    name = "counting"

    def __init__(self, config=None):
        self._inner = AgentAnalysisProvider(config)
        self.analyzed_files: list[str] = []

    def analyze_pages(self, pdf_path, page_numbers):
        self.analyzed_files.append(Path(pdf_path).name)
        return self._inner.analyze_pages(pdf_path, page_numbers)

    def proposed_documents(self, pdf_path):
        return self._inner.proposed_documents(pdf_path)

    def classify_document(self, pdf_path, page_numbers, candidates, **kw):
        return self._inner.classify_document(pdf_path, page_numbers, candidates, **kw)

    def describe(self):
        return self._inner.describe()


@pytest.fixture()
def env(tmp_path: Path):
    ws = Workspace(tmp_path)
    input_root = tmp_path / "input"
    analysis_root = tmp_path / "analysis"
    registry = StateRegistry(ws.state_db_path)
    yield tmp_path, ws, input_root, analysis_root, registry
    registry.close()


def run(ws, folder, registry, provider, *, mode=MODE_DRY_RUN, **kw):
    return process_person_folder(
        folder, mode=mode, provider=provider, workspace=ws, state_registry=registry, **kw
    )


def test_dry_run_khong_danh_processed(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    provider = CountingProvider({"analysis_root": analysis_root})

    result = run(ws, input_root / "P", registry, provider, mode=MODE_DRY_RUN)
    assert result.status == "DRY_RUN_PASS"
    assert provider.analyzed_files == ["a.pdf"]

    h = sha256_file(input_root / "P" / "a.pdf")
    r = registry.get(h)
    # Tài liệu AUTO sạch -> release về NEW, KHÔNG BAO GIỜ là PROCESSED sau dry-run.
    assert r is None or r.status != STATUS_PROCESSED


def test_apply_qc_pass_moi_danh_processed(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    provider = CountingProvider({"analysis_root": analysis_root})

    result = run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)
    assert result.status == "APPLY_PASS"
    h = sha256_file(input_root / "P" / "a.pdf")
    r = registry.get(h)
    assert r.status == STATUS_PROCESSED
    assert r.logical_document_count == 1
    assert (ws.output / "P").exists()


def test_nguon_da_processed_khong_bi_agent_doc_lai(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    provider = CountingProvider({"analysis_root": analysis_root})
    run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)

    provider2 = CountingProvider({"analysis_root": analysis_root})
    result2 = run(ws, input_root / "P", registry, provider2, mode=MODE_DRY_RUN)
    assert provider2.analyzed_files == []  # KHÔNG được gọi analyze_pages cho nguồn PROCESSED
    assert result2.documents == []
    assert result2.incremental.counts()[DECISION_ALREADY_PROCESSED] == 1


def test_them_nguon_moi_chi_nguon_moi_duoc_agent_doc(env):
    """Đúng kịch bản trong nhiệm vụ: scan001..003 đã xử lý, scan004..005 mới.

    Dùng type_id khác nhau cho mỗi nguồn để phép thử này chỉ kiểm tra đúng một
    điều: Agent có bị gọi lại cho nguồn cũ hay không. Naming/đánh số liên-lượt
    cho NHIỀU tài liệu CÙNG loại trải qua nhiều lần apply là giới hạn đã biết,
    ghi ở LIMITATIONS.md, không phải phạm vi của test này (xem
    test_nhieu_tai_lieu_cung_loai_qua_nhieu_lan_apply_bi_chan_an_toan).
    """
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "scan001.pdf", type_id="01", document_date="2024-01-01")
    add_source(input_root, analysis_root, "P", "scan002.pdf", type_id="02", document_date="2024-01-02")
    add_source(input_root, analysis_root, "P", "scan003.pdf", type_id="03", document_date="2024-01-03")
    provider = CountingProvider({"analysis_root": analysis_root})
    run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)

    add_source(input_root, analysis_root, "P", "scan004.pdf", type_id="19", document_date="2024-02-01")
    add_source(input_root, analysis_root, "P", "scan005.pdf", type_id="20", document_date="2024-02-02")
    provider2 = CountingProvider({"analysis_root": analysis_root})
    result = run(ws, input_root / "P", registry, provider2, mode=MODE_APPLY)

    assert sorted(provider2.analyzed_files) == ["scan004.pdf", "scan005.pdf"]
    assert result.status == "APPLY_PASS"
    c = result.incremental.counts()
    assert c[DECISION_NEW] == 2
    assert c[DECISION_ALREADY_PROCESSED] == 3
    # 5 file output riêng biệt, không file nào bị ghi lại/trùng.
    assert len(list((ws.output / "P").glob("*.pdf"))) == 5


def test_nhieu_tai_lieu_cung_loai_qua_nhieu_lan_apply_bi_chan_an_toan(env):
    """Giới hạn đã biết (LIMITATIONS.md): naming chỉ đánh số trong PHẠM VI một
    lượt chạy. Thêm tài liệu CÙNG loại ở lượt sau có thể trùng tên bare-file
    với lượt trước -> phải bị CHẶN AN TOÀN (BLOCKED_RUNTIME, không ghi đè âm
    thầm), không phải renumber tự động."""
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2024-01-01")
    run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_APPLY)

    add_source(input_root, analysis_root, "P", "b.pdf", type_id="04", document_date="2024-02-01")
    result = run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_APPLY)

    assert result.status == "BLOCKED_RUNTIME"
    h = sha256_file(input_root / "P" / "b.pdf")
    assert registry.get(h).status == STATUS_FAILED
    # File gốc của lượt trước không bị đụng tới.
    assert len(list((ws.output / "P").glob("*.pdf"))) == 1


def test_apply_that_bai_khong_danh_processed_va_khong_tu_retry(env):
    from app.catalog import load_catalog

    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2024-01-01")
    provider = CountingProvider({"analysis_root": analysis_root})
    run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)

    # b.pdf khác loại với a.pdf (tách biệt khỏi giới hạn naming liên-lượt đã ghi
    # nhận riêng) - giả lập đúng MỘT điều: file đích của b bị ai đó ghi đè
    # NGOÀI pipeline trước khi apply chạy tới.
    add_source(input_root, analysis_root, "P", "b.pdf", type_id="05", document_date="2024-01-02")
    catalog = load_catalog()
    out_dir = ws.output / "P"
    out_dir.mkdir(parents=True, exist_ok=True)
    victim = out_dir / f"{catalog.filename_base('05')}.pdf"
    victim.write_bytes(b"%PDF-1.4 bi thay doi ngoai luong")

    provider2 = CountingProvider({"analysis_root": analysis_root})
    result = run(ws, input_root / "P", registry, provider2, mode=MODE_APPLY)
    assert result.status == "BLOCKED_RUNTIME"

    h = sha256_file(input_root / "P" / "b.pdf")
    r = registry.get(h)
    assert r.status == STATUS_FAILED
    assert r.status != STATUS_PROCESSED

    # Không tự động retry: gọi lại apply lần nữa (không sửa gì) vẫn FAILED, không đọc lại vô hạn.
    provider3 = CountingProvider({"analysis_root": analysis_root})
    result3 = run(ws, input_root / "P", registry, provider3, mode=MODE_APPLY)
    assert provider3.analyzed_files == []  # 'b.pdf' đang FAILED -> không tự retry


def test_crash_giua_chung_khong_thanh_processed(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    src = add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    h = sha256_file(src)
    # Mô phỏng crash: đã begin_processing nhưng tiến trình chết trước khi commit.
    registry.begin_processing(
        source_hash=h, source_filename="a.pdf", source_relative_path="P/a.pdf",
        person_folder="P", page_count=1,
    )

    provider = CountingProvider({"analysis_root": analysis_root})
    result = run(ws, input_root / "P", registry, provider, mode=MODE_DRY_RUN)
    # INTERRUPTED không tự retry mặc định -> Agent không đọc lại.
    assert provider.analyzed_files == []
    assert result.incremental.counts()["INTERRUPTED"] == 1
    r = registry.get(h)
    assert r.status != STATUS_PROCESSED


def test_apply_lan_hai_idempotent_khong_tao_ban_trung(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    provider = CountingProvider({"analysis_root": analysis_root})
    run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)
    files1 = {p.name: sha256_file(p) for p in (ws.output / "P").glob("*.pdf")}

    provider2 = CountingProvider({"analysis_root": analysis_root})
    result2 = run(ws, input_root / "P", registry, provider2, mode=MODE_APPLY)
    files2 = {p.name: sha256_file(p) for p in (ws.output / "P").glob("*.pdf")}

    assert result2.status == "APPLY_PASS"
    assert provider2.analyzed_files == []
    assert files1 == files2  # không có file mới/trùng nào xuất hiện


def test_source_mutation_bang_0_qua_nhieu_lan_chay(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    src = add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    before = sha256_file(src)
    provider = CountingProvider({"analysis_root": analysis_root})
    run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)
    run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_DRY_RUN)
    assert sha256_file(src) == before


def test_manifest_ledger_gop_qua_cac_lan_chay(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", type_id="04", document_date="2024-01-01")
    run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_APPLY)

    add_source(input_root, analysis_root, "P", "b.pdf", type_id="05", document_date="2024-01-02")
    run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_APPLY)

    ledger = load_manifest(ws.output / "P" / "_manifest.json")
    sources_in_ledger = {d["source_file"] for d in ledger["documents"]}
    assert sources_in_ledger == {"a.pdf", "b.pdf"}  # KHÔNG mất entry của lượt trước
    assert ledger["summary"]["logical_documents"] == 2


def test_trung_hash_khong_bao_gio_duoc_xu_ly(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    same_size = (420.0, 623.0)
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01", size=same_size)
    add_source(input_root, analysis_root, "P", "copy-a.pdf", document_date="2024-01-01", size=same_size)

    provider = CountingProvider({"analysis_root": analysis_root})
    result = run(ws, input_root / "P", registry, provider, mode=MODE_APPLY)

    # a.pdf < copy-a.pdf theo alphabet -> canonical là a.pdf
    assert sorted(provider.analyzed_files) == ["a.pdf"]
    assert len(list((ws.output / "P").glob("*.pdf"))) == 1  # không tạo output trùng cho bản duplicate


def test_review_required_source_duoc_xu_ly_khi_apply_va_thanh_processed(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(
        input_root, analysis_root, "P", "a.pdf",
        needs_review=True, review_reason="không chắc loại tài liệu",
    )
    provider = CountingProvider({"analysis_root": analysis_root})
    dry = run(ws, input_root / "P", registry, provider, mode=MODE_DRY_RUN)
    assert dry.status == "REVIEW_REQUIRED"
    h = sha256_file(input_root / "P" / "a.pdf")
    assert registry.get(h).status == STATUS_REVIEW_REQUIRED

    provider2 = CountingProvider({"analysis_root": analysis_root})
    apply_result = run(ws, input_root / "P", registry, provider2, mode=MODE_APPLY)
    assert provider2.analyzed_files == ["a.pdf"]  # apply PHẢI đọc để ghi file review/ thật
    assert registry.get(h).status == STATUS_PROCESSED  # apply xong -> PROCESSED dù có REVIEW


def test_khong_co_nguon_moi_thi_khong_goi_provider(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_APPLY)

    provider2 = CountingProvider({"analysis_root": analysis_root})
    result = run(ws, input_root / "P", registry, provider2, mode=MODE_APPLY)
    assert provider2.analyzed_files == []
    assert result.documents == []
    assert result.status == "APPLY_PASS"


# ---------------- migration (import-state) ----------------
def test_import_state_danh_processed_khi_bang_chung_du(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    # Apply KHÔNG dùng state registry (mô phỏng hồ sơ HAI được xử lý trước khi có state).
    process_person_folder(
        input_root / "P", mode=MODE_APPLY,
        provider=AgentAnalysisProvider({"analysis_root": analysis_root}), workspace=ws,
    )
    fresh_registry = StateRegistry(ws.state_db_path)
    assert fresh_registry.get(sha256_file(input_root / "P" / "a.pdf")) is None

    report = import_person_folder(input_root / "P", fresh_registry, workspace=ws)
    assert [o.outcome for o in report.outcomes] == [OUTCOME_IMPORTED]

    r = fresh_registry.get(sha256_file(input_root / "P" / "a.pdf"))
    assert r.status == STATUS_PROCESSED
    fresh_registry.close()


def test_import_state_khong_du_bang_chung_thi_khong_danh_processed(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf")
    # Chưa từng apply -> không có ledger.
    report = import_person_folder(input_root / "P", registry, workspace=ws)
    assert report.outcomes[0].outcome == "STATE_IMPORT_REVIEW_REQUIRED"
    assert registry.get(sha256_file(input_root / "P" / "a.pdf")) is None


def test_import_state_thieu_file_dau_ra_thi_khong_danh_processed(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    process_person_folder(
        input_root / "P", mode=MODE_APPLY,
        provider=AgentAnalysisProvider({"analysis_root": analysis_root}), workspace=ws,
    )
    # Xoá mất file output thật, nhưng ledger vẫn còn nhắc tới nó.
    for f in (ws.output / "P").glob("*.pdf"):
        f.unlink()

    fresh_registry = StateRegistry(ws.state_db_path)
    report = import_person_folder(input_root / "P", fresh_registry, workspace=ws)
    assert report.outcomes[0].outcome == "STATE_IMPORT_REVIEW_REQUIRED"
    assert fresh_registry.get(sha256_file(input_root / "P" / "a.pdf")) is None
    fresh_registry.close()


def test_import_state_khong_ghi_de_record_da_co_trong_registry(env):
    tmp_path, ws, input_root, analysis_root, registry = env
    add_source(input_root, analysis_root, "P", "a.pdf", document_date="2024-01-01")
    run(ws, input_root / "P", registry, CountingProvider({"analysis_root": analysis_root}), mode=MODE_APPLY)

    report = import_person_folder(input_root / "P", registry, workspace=ws)
    assert report.outcomes[0].outcome == OUTCOME_ALREADY_IN_REGISTRY
