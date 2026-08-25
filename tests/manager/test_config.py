from __future__ import annotations

import json
from pathlib import Path

import app.manager.config as config_module
from app.manager.config import Settings


def test_from_file_prefers_ignored_local_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "REPO_ROOT", tmp_path)
    local = tmp_path / "config.local.json"
    local.write_text(json.dumps({"data_root": "external-data"}), encoding="utf-8")

    settings = Settings.from_file()

    assert settings.config_path == local
    assert settings.data_root == (tmp_path / "external-data").resolve()


def test_environment_data_root_overrides_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "REPO_ROOT", tmp_path)
    config = tmp_path / "config.local.json"
    config.write_text(json.dumps({"data_root": "from-file"}), encoding="utf-8")
    monkeypatch.setenv("HOSO_DATA_ROOT", "E:/external-data")

    settings = Settings.from_file()

    assert settings.data_root == Path("E:/external-data").resolve()
