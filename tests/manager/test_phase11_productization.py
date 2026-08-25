from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.manager.config import Settings
from app.manager.main import create_app
from app.manager.version import APP_VERSION
from tests.manager.test_scanner import make_pdf


def client_for(tmp_path: Path) -> TestClient:
    root = tmp_path / "input"
    folder = root / "25.000.036.001.015_012345678901_Nguyen_Van_A"
    folder.mkdir(parents=True)
    make_pdf(folder / "01.Ly_lich_nguoi_xin_vao_dang.pdf")
    settings = Settings(data_root=root, database_path=tmp_path / "data" / "manager.db", config_path=tmp_path / "config.json")
    return TestClient(create_app(settings), base_url="http://127.0.0.1")


def csrf(client: TestClient) -> str:
    client.get("/")
    token = client.cookies.get("csrf_token")
    assert token
    return token


def test_phase11_health_and_operational_pages(tmp_path: Path):
    client = client_for(tmp_path)
    assert client.get("/health").json()["version"] == APP_VERSION
    token = csrf(client)
    assert client.post("/scan", headers={"X-CSRF-Token": token}).status_code == 200
    assert "Cần xử lý" in client.get("/").text
    assert "Lịch sử quét" in client.get("/scan-runs").text
    assert "status-badge" in client.get("/cases").text


def test_phase11_backup_restore_is_validated_and_safe(tmp_path: Path):
    client = client_for(tmp_path)
    token = csrf(client)
    client.post("/scan", headers={"X-CSRF-Token": token})
    case_id = client.get("/cases?format=json").json()["items"][0]["id"]
    backup = client.post("/backup", headers={"X-CSRF-Token": token})
    assert backup.status_code == 200
    backup_name = Path(backup.json()["path"]).name
    assert backup.json()["integrity"]["ok"] is True
    assert client.post(f"/cases/{case_id}/note", json={"note": "thay đổi sau backup"}, headers={"X-CSRF-Token": token}).status_code == 200
    restored = client.post("/restore", json={"name": backup_name}, headers={"X-CSRF-Token": token})
    assert restored.status_code == 200
    assert Path(restored.json()["safety_backup"]).is_file()
    assert client.get(f"/cases/{case_id}?format=json").json()["case"]["note"] is None
    assert client.post("/restore", json={"name": "..\\outside.sqlite"}, headers={"X-CSRF-Token": token}).status_code == 400


def test_phase11_settings_switches_machine_local_root(tmp_path: Path):
    client = client_for(tmp_path)
    token = csrf(client)
    new_root = tmp_path / "other-machine-data"
    new_root.mkdir()
    response = client.post("/settings", json={"data_root": str(new_root), "open_browser_on_start": "true"}, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert response.json()["data_root"] == str(new_root.resolve())
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["data_root"] == str(new_root.resolve())
