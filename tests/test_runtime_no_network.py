"""Runtime Antigravity-native: KHÔNG API key, KHÔNG gọi AI qua mạng.

Đây là hàng rào kiến trúc. Nếu ai đó cắm lại một provider gọi API vào runtime
path, các test này phải đỏ.
"""
from __future__ import annotations

import ast
import os
import socket
from pathlib import Path

import pytest

from app.pipeline import Workspace, process_person_folder
from app.vision_adapter import ProviderError, available_providers, get_provider

# Module duy nhất được phép nhắc tới SDK model; nó KHÔNG nằm trong runtime path.
QUARANTINED = {"gemini_provider.py"}

NETWORK_MODULES = {
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "http",
    "socket",
    "aiohttp",
    "websockets",
    "google",
    "openai",
    "anthropic",
    "boto3",
}

CREDENTIAL_WORDS = ("API_KEY", "APIKEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "BEARER")


def runtime_sources(repo_root: Path) -> list[Path]:
    return [
        p
        for p in sorted((repo_root / "app").rglob("*.py"))
        if p.name not in QUARANTINED
    ]


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_runtime_source_khong_import_thu_vien_mang(repo_root: Path):
    offenders: list[str] = []
    for src in runtime_sources(repo_root):
        bad = imported_roots(src) & NETWORK_MODULES
        if bad:
            offenders.append(f"{src.relative_to(repo_root)}: {sorted(bad)}")
    assert not offenders, "Runtime path không được import thư viện mạng:\n" + "\n".join(offenders)


def test_runtime_source_khong_doc_bien_moi_truong_bi_mat(repo_root: Path):
    """Không module runtime nào được đọc API key / token / secret từ môi trường."""
    offenders: list[str] = []
    for src in runtime_sources(repo_root):
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            literals: list[str] = []
            # os.environ["X"] / os.environ.get("X") / os.getenv("X")
            if isinstance(node, ast.Subscript) and _is_environ(node.value):
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    literals.append(node.slice.value)
            if isinstance(node, ast.Call):
                fn = node.func
                is_env_call = (
                    isinstance(fn, ast.Attribute)
                    and (
                        (fn.attr == "get" and _is_environ(fn.value))
                        or (fn.attr in ("getenv", "environb") and _is_os(fn.value))
                    )
                )
                if is_env_call and node.args and isinstance(node.args[0], ast.Constant):
                    if isinstance(node.args[0].value, str):
                        literals.append(node.args[0].value)
            for name in literals:
                if any(w in name.upper() for w in CREDENTIAL_WORDS):
                    offenders.append(f"{src.relative_to(repo_root)}: đọc biến môi trường {name!r}")
    assert not offenders, "Runtime path không được yêu cầu API key:\n" + "\n".join(offenders)


def _is_environ(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "environ" and _is_os(node.value)


def _is_os(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "os"


def test_vision_adapter_khong_nap_adapter_api(repo_root: Path):
    text = (repo_root / "app" / "vision_adapter.py").read_text(encoding="utf-8")
    # Chỉ được nhắc tên trong phần ghi chú giải thích, không được import.
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "provider" in node.module:
            names = {a.name for a in node.names}
            assert "gemini_provider" not in names
        if isinstance(node, ast.ImportFrom) and node.level and node.module == "providers":
            names = {a.name for a in node.names}
            assert names == {"agent_provider", "fixture_provider"}, names


def test_registry_chi_co_provider_offline():
    assert set(available_providers()) == {"agent", "fixture"}
    for name in available_providers():
        info = get_provider(name).describe()
        assert info.get("api_key_required", False) is False or "api_key" not in info


def test_provider_goi_api_khong_ton_tai_trong_runtime():
    for name in ("gemini", "openai", "claude", "vertex"):
        with pytest.raises(ProviderError, match="chưa đăng ký"):
            get_provider(name)


def test_pipeline_chay_duoc_khi_khong_co_bien_moi_truong_api(
    monkeypatch, tmp_path: Path, hai_folder: Path
):
    """Xoá sạch mọi biến môi trường dạng API key -> pipeline vẫn phải chạy."""
    for key in list(os.environ):
        if any(h in key.upper() for h in ("API_KEY", "TOKEN", "SECRET", "GEMINI", "OPENAI")):
            monkeypatch.delenv(key, raising=False)
    result = process_person_folder(
        hai_folder, provider_name="agent", workspace=Workspace(tmp_path), write_manifest=False
    )
    assert result.qc.passed
    assert result.manifest["provider"]["api_key_required"] is False
    assert result.manifest["provider"]["network"] == "none"


def test_pipeline_khong_mo_ket_noi_mang(monkeypatch, tmp_path: Path, hai_folder: Path):
    """Chặn socket ở tầng thấp nhất: chạm vào mạng là test đỏ."""
    calls: list[str] = []

    def blocked(*args, **kwargs):
        calls.append("socket")
        raise AssertionError("Runtime đã cố mở kết nối mạng!")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    result = process_person_folder(
        hai_folder, provider_name="agent", workspace=Workspace(tmp_path), write_manifest=False
    )
    assert result.qc.passed
    assert calls == []
