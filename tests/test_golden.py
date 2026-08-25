"""Acceptance gate bắt buộc - test_cases/HAI_GOLDEN.json.

KHÔNG được sửa golden label để test xanh (AGENTS.md mục 2.2 và mục 12).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.golden import list_golden_files, run_all_golden, run_golden_file


def test_co_it_nhat_mot_file_golden(golden_root: Path):
    assert list_golden_files(golden_root), "Thiếu bộ golden trong test_cases/"


@pytest.mark.parametrize("golden_path", list_golden_files(Path(__file__).resolve().parents[1]))
@pytest.mark.parametrize("provider", ["fixture", "agent"])
def test_golden_acceptance(golden_path: Path, provider: str, golden_root: Path):
    """Golden phải xanh với CẢ fixture (test) lẫn agent (runtime Antigravity thật)."""
    report = run_golden_file(golden_path, root=golden_root, provider_name=provider)
    assert report.passed, f"provider={provider}\n" + "\n".join(str(f) for f in report.failures)


def test_agent_va_fixture_cho_cung_ket_qua_segmentation(golden_root: Path):
    a = run_golden_file(list_golden_files(golden_root)[0], root=golden_root, provider_name="agent")
    f = run_golden_file(list_golden_files(golden_root)[0], root=golden_root, provider_name="fixture")
    assert a.result is not None and f.result is not None
    pages_a = sorted((d.document.source_file, tuple(d.document.source_pages)) for d in a.result.documents)
    pages_f = sorted((d.document.source_file, tuple(d.document.source_pages)) for d in f.result.documents)
    assert pages_a == pages_f


def test_golden_bao_phu_du_moi_case(golden_root: Path):
    reports = run_all_golden(golden_root)
    total_expected = 0
    for path in list_golden_files(golden_root):
        golden = json.loads(path.read_text(encoding="utf-8"))
        total_expected += sum(len(c.get("expected_documents") or []) for c in golden["cases"])
    assert sum(r.checked_documents for r in reports) == total_expected


def test_golden_khong_bo_sot_trang_nao(golden_root: Path):
    reports = run_all_golden(golden_root)
    for r in reports:
        assert r.result is not None
        covered = sum(len(d.document.source_pages) for d in r.result.documents)
        assert covered == r.result.inventory.total_pages
        assert r.result.qc.passed, [c.as_dict() for c in r.result.qc.failures]


def test_golden_khong_ghi_gi_ra_output_hay_review(golden_root: Path):
    before_out = _snapshot(golden_root / "output")
    before_rev = _snapshot(golden_root / "review")
    run_all_golden(golden_root)
    assert _snapshot(golden_root / "output") == before_out
    assert _snapshot(golden_root / "review") == before_rev


def test_golden_khong_sua_file_nguon(golden_root: Path):
    before = _snapshot(golden_root / "input")
    run_all_golden(golden_root)
    assert _snapshot(golden_root / "input") == before


def _snapshot(folder: Path) -> dict[str, int]:
    if not folder.exists():
        return {}
    return {
        str(p.relative_to(folder)): p.stat().st_size
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }
