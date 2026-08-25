from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.manager.config import Settings
from app.manager.db import Database
from app.manager.main import create_app
from app.pdf_inventory import sha256_file


def snapshot(root: Path) -> dict[str, dict[str, int | str]]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            result[str(path.relative_to(root))] = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256_file(path) if path.suffix.lower() == ".pdf" else "",
            }
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    repo = Path(__file__).resolve().parents[1]
    source = repo / "input"
    before = snapshot(source)
    temp = Path(tempfile.mkdtemp(prefix="digitization-real-pilot-"))
    try:
        settings = Settings(data_root=source, database_path=temp / "manager.db", manifest_path=repo / "output")
        client = TestClient(create_app(settings))
        health = client.get("/health").json()
        client.get("/")
        csrf = client.cookies.get("csrf_token")
        response = client.post("/scan", headers={"X-CSRF-Token": csrf})
        listing = client.get("/cases?format=json").json()
        cases = []
        for item in listing["items"]:
            case_id = item["id"]
            detail_response = client.get(f"/cases/{case_id}?format=json")
            detail = detail_response.json()
            cases.append({
                "case_id": case_id,
                "source_files": len(detail["documents"]),
                "pipeline_documents": len(detail["pipeline_documents"]),
                "warnings": len(detail["warnings"]),
                "status": detail["case"]["effective_status"],
                "detail_status": detail_response.status_code,
            })
        ui = {
            "dashboard": client.get("/").status_code,
            "cases": client.get("/cases").status_code,
            "cases_json": client.get("/cases?format=json").status_code,
            "settings": client.get("/settings?format=json").status_code,
            "scan_runs": client.get("/scan-runs").status_code,
            "backup": client.get("/backup").status_code,
        }
        after = snapshot(source)
        db = Database(settings.database_path)
        metrics = {
            "cases": db.one("SELECT COUNT(*) AS n FROM cases")["n"],
            "present_cases": db.one("SELECT COUNT(*) AS n FROM cases WHERE is_present=1")["n"],
            "source_documents": db.one("SELECT COUNT(*) AS n FROM documents WHERE is_present=1")["n"],
            "pipeline_documents": db.one("SELECT COUNT(*) AS n FROM pipeline_documents")["n"],
            "warnings": db.one("SELECT COUNT(*) AS n FROM warnings WHERE active=1")["n"],
            "taxonomy_items": db.one("SELECT COUNT(*) AS n FROM taxonomy_items WHERE active=1")["n"],
            "scan_runs": db.one("SELECT COUNT(*) AS n FROM scan_runs")["n"],
        }
        source_pdfs = [item for item in before if item.lower().endswith(".pdf")]
        print(json.dumps({
            "health": health,
            "scan": response.json(),
            "inventory": {
                "folders": len({str(Path(name).parent) for name in before}),
                "files": len(before),
                "pdfs": len(source_pdfs),
                "pdf_pages": sum((db.one("SELECT COALESCE(SUM(page_count),0) AS n FROM documents WHERE is_present=1")["n"],)),
            },
            "metrics": metrics,
            "cases": cases,
            "ui": ui,
            "source_unchanged": before == after,
            "source_before": before,
            "source_after": after,
            "backup_path": str(settings.database_path.with_name(settings.database_path.stem + ".backup.sqlite")),
        }, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()





