from pathlib import Path

from fastapi.testclient import TestClient

from app.manager.config import Settings
from app.manager.main import create_app


def test_health_and_dashboard(tmp_path: Path):
    settings = Settings(data_root=tmp_path / "input", database_path=tmp_path / "data" / "app.db")
    app = create_app(settings)
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/health").json()["offline"] is True
    response = client.get("/")
    assert response.status_code == 200
    assert "Hồ sơ Digitization Manager" in response.text


def test_settings_post_requires_csrf(tmp_path: Path):
    settings = Settings(data_root=tmp_path / "input", database_path=tmp_path / "data" / "app.db")
    client = TestClient(create_app(settings), base_url="http://127.0.0.1")
    assert client.post("/settings", json={"data_root": str(tmp_path)}).status_code == 403
