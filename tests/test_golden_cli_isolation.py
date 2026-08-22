"""Golden CLI must be reproducible without production/personal PDFs."""
from __future__ import annotations

import socket
from pathlib import Path

from pypdf import PdfReader

from app import cli
from app.golden_fixtures import (
    deterministic_blank_pdf,
    isolated_golden_workspace,
    load_golden_contracts,
)


CANONICAL_MISSING_SOURCE = "Phieu bo sung hs dang vien 2020 HAI.pdf"
EXPECTED_SHA256_BY_PAGES = {
    1: "403d2584f217560f6904c89d18363b219c53c412192dadb77dea833cce1e15a3",
    8: "c4071c50073f80e4ac297f061d4f1cfb2b19e15e89f2636248b22bb1dca9036a",
    20: "40504a637d86fba756b4d279d3e69f839b1d0dd23bac067e9b1c4a81249c18c7",
}


def test_synthetic_golden_pdf_contract_is_stable_and_isolated(repo_root: Path, tmp_path: Path):
    """The common factory creates valid deterministic PDFs, never production files."""
    assert not (repo_root / "input" / "Nguyễn Hữu Hải" / CANONICAL_MISSING_SOURCE).exists()
    contracts = load_golden_contracts(repo_root)

    for pages, expected_sha in EXPECTED_SHA256_BY_PAGES.items():
        import hashlib
        assert hashlib.sha256(deterministic_blank_pdf(pages)).hexdigest() == expected_sha

    with isolated_golden_workspace(repo_root, temp_parent=tmp_path) as staged:
        assert staged.root.parent == tmp_path
        assert CANONICAL_MISSING_SOURCE in staged.source_sha256
        seen: set[str] = set()
        for _, golden in contracts:
            for case in golden["cases"]:
                name = case["source_file"]
                pdf = staged.person_folder / name
                assert pdf.is_file()
                assert len(PdfReader(pdf).pages) == case["source_pages"]
                seen.add(name)
        assert "Bo sung HAI.pdf" not in seen
        assert (staged.analysis_root / "Nguyễn Hữu Hải" / "Phieu bo sung hs dang vien 2020 HAI.json").is_file()

    # Temporary fixture root is removed under the normal (non-debug) contract.
    assert list(tmp_path.iterdir()) == []
    assert not (repo_root / "input" / "Nguyễn Hữu Hải" / CANONICAL_MISSING_SOURCE).exists()


def test_golden_cli_agent_uses_only_synthetic_temp_input_no_network(
    repo_root: Path, monkeypatch, capsys
):
    """Exercise the actual CLI path while production input remains untouched."""
    production = repo_root / "input" / "Nguyễn Hữu Hải"
    before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in production.glob("*.pdf")}
    assert CANONICAL_MISSING_SOURCE not in before
    calls: list[str] = []

    def blocked(*args, **kwargs):
        calls.append("socket")
        raise AssertionError("Golden CLI đã cố mở kết nối mạng")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    assert cli.main(["--root", str(repo_root), "test-golden", "--provider", "agent"]) == 0
    output = capsys.readouterr().out
    assert "GOLDEN ACCEPTANCE: PASS" in output
    assert calls == []
    after = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in production.glob("*.pdf")}
    assert after == before
    assert not (production / CANONICAL_MISSING_SOURCE).exists()
