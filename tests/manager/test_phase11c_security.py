from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.manager.config as config_module
import app.manager.entrypoint as entrypoint
import app.manager.routes as routes_module
from app.manager.config import Settings
from app.manager.main import create_app
from app.manager.mutation import MutationBusy, MutationLock
from tests.manager.test_scanner import make_pdf


def client_for(tmp_path: Path) -> tuple[TestClient, Path]:
    root = tmp_path / "input"
    folder = root / "25.000.036.001.015_012345678901_Synthetic_Person"
    folder.mkdir(parents=True)
    make_pdf(folder / "01.Ly_lich_nguoi_xin_vao_dang.pdf")
    client = TestClient(
        create_app(Settings(data_root=root, database_path=tmp_path / "data" / "manager.db")),
        base_url="http://127.0.0.1",
    )
    return client, root


def get_csrf(client: TestClient) -> str:
    client.get("/")
    token = client.cookies.get("csrf_token")
    assert token
    return token


def scan_case(client: TestClient) -> int:
    token = get_csrf(client)
    assert client.post("/scan", headers={"X-CSRF-Token": token}).status_code == 200
    return client.get("/cases?format=json").json()["items"][0]["id"]


def test_get_backup_is_not_a_mutation(tmp_path: Path):
    client, _ = client_for(tmp_path)
    response = client.get("/backup")
    assert response.status_code == 405
    assert client.get("/backups").json() == {"items": []}
    assert not (tmp_path / "data" / "backups").exists()


def test_open_case_requires_post_csrf_and_safe_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client, root = client_for(tmp_path)
    case_id = scan_case(client)
    opened: list[str] = []
    monkeypatch.setattr(routes_module.os, "startfile", lambda value: opened.append(str(value)), raising=False)

    assert client.get(f"/open/case/{case_id}").status_code == 405
    assert client.post(f"/open/case/{case_id}").status_code == 403
    token = get_csrf(client)
    response = client.post(f"/open/case/{case_id}", headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert opened == [str((root / "25.000.036.001.015_012345678901_Synthetic_Person").resolve())]

    with client.app.state.db.session() as conn:
        conn.execute("UPDATE cases SET folder_path=? WHERE id=?", (str(tmp_path / "outside"), case_id))
    assert client.post(f"/open/case/{case_id}", headers={"X-CSRF-Token": token}).status_code == 404
    assert len(opened) == 1


def test_trusted_hosts_are_local_only(tmp_path: Path):
    client, _ = client_for(tmp_path)
    assert client.get("/health", headers={"Host": "127.0.0.1"}).status_code == 200
    assert client.get("/health", headers={"Host": "localhost:8765"}).status_code == 200
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400


def test_mutation_lock_releases_after_conflict_and_exception():
    lock = MutationLock()
    with lock.acquire():
        with pytest.raises(MutationBusy):
            with lock.acquire():
                pass
    with pytest.raises(RuntimeError):
        with lock.acquire():
            raise RuntimeError("fixture failure")
    with lock.acquire():
        pass


def test_settings_save_defaults_to_ignored_local_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_module, "REPO_ROOT", tmp_path)
    settings = Settings(data_root=tmp_path / "input", database_path=tmp_path / "data" / "manager.db")
    saved = settings.save()
    assert saved == tmp_path / "config.local.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["data_root"] == str((tmp_path / "input").resolve())
    assert not (tmp_path / "manager-config.json").exists()


def test_startup_failure_logs_safe_message_and_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(entrypoint, "executable_root", lambda: tmp_path)
    monkeypatch.setattr(entrypoint, "_run", lambda root: (_ for _ in ()).throw(ValueError("secret path must not leak")))
    monkeypatch.setattr(entrypoint.sys, "platform", "linux")
    with pytest.raises(SystemExit) as error:
        entrypoint.main()
    assert error.value.code == 1
    log = (tmp_path / "startup.log").read_text(encoding="utf-8")
    assert "fatal_error: ValueError" in log
    assert "secret path must not leak" not in log
