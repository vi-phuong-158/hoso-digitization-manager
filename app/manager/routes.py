from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import Settings
from .db import Database
from .integration import ensure_schema, integrate_case, provider_for
from .mutation import MutationBusy, MutationLock
from .scanner import ScanService
from .status import mark_complete, now as status_now, recompute_case, reopen, set_checklist_override, set_manual_status, update_note
from .taxonomy import TaxonomyAdapter
from .version import APP_NAME, APP_VERSION, BUILD_SHA


STATUS_LABELS = {
    "CHUA_XU_LY": "Chưa xử lý",
    "DANG_SO_HOA": "Đang số hóa",
    "CHO_KIEM_TRA": "Chờ kiểm tra",
    "CAN_BO_SUNG": "Cần bổ sung",
    "HOAN_THANH": "Hoàn thành",
}
CHECKLIST_LABELS = {
    "CO_TAI_LIEU": "Có tài liệu",
    "KHONG_PHAT_SINH": "Không phát sinh",
    "CHUA_XAC_DINH": "Chưa xác định",
    "CAN_BO_SUNG": "Cần bổ sung",
}


def _json_requested(request: Request) -> bool:
    return request.query_params.get("format") == "json" or "application/json" in request.headers.get("accept", "")


def _dict(row) -> dict:
    return dict(row) if row else {}


def dashboard_context(db: Database) -> dict:
    rows = db.all("SELECT * FROM cases WHERE is_present=1")
    counts = {status: 0 for status in ("CHUA_XU_LY", "DANG_SO_HOA", "CHO_KIEM_TRA", "CAN_BO_SUNG", "HOAN_THANH")}
    for row in rows:
        counts[row["effective_status"]] = counts.get(row["effective_status"], 0) + 1
    total = len(rows)
    progress = round(sum(row["progress_percent"] for row in rows) / total, 2) if total else 0.0
    units = {}
    for row in rows:
        unit = row["unit_code"] or "Chưa xác định"
        units.setdefault(unit, []).append(row)
    unit_rows = []
    for unit, unit_cases in sorted(units.items()):
        completed = sum(row["effective_status"] == "HOAN_THANH" for row in unit_cases)
        unit_rows.append({
            "unit": unit,
            "count": len(unit_cases),
            "completed": completed,
            "unfinished": len(unit_cases) - completed,
            "missing_p1": sum(row["missing_priority1_count"] for row in unit_cases),
            "progress": round(sum(row["progress_percent"] for row in unit_cases) / len(unit_cases), 2),
        })
    def action_key(row):
        status_rank = {"CAN_BO_SUNG": 1, "DANG_SO_HOA": 2, "CHO_KIEM_TRA": 3}.get(row["effective_status"], 4)
        return (0 if row["missing_priority1_count"] else 1, status_rank, -row["warning_count"], row["last_scanned_at"] or "")
    action_rows = sorted(
        [row for row in rows if row["effective_status"] in {"CAN_BO_SUNG", "DANG_SO_HOA", "CHO_KIEM_TRA"} or row["warning_count"]],
        key=action_key,
    )
    last_run = db.one("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1")
    return {
        "total": total,
        "counts": counts,
        "progress": progress,
        "missing_p1": sum(row["missing_priority1_count"] for row in rows),
        "review_pending": db.one("SELECT COUNT(*) AS n FROM warnings WHERE active=1 AND warning_type IN ('REVIEW_PENDING','CAN_XAC_MINH')")["n"],
        "unit_rows": unit_rows,
        "action_rows": action_rows[:10],
        "last_run": _dict(last_run),
        "status_labels": STATUS_LABELS,
    }


def _case_payload(db: Database, case_id: int) -> dict:
    row = db.one("SELECT * FROM cases WHERE id=?", (case_id,))
    if row is None:
        raise LookupError("Không tìm thấy hồ sơ")
    with db.session() as conn:
        state = recompute_case(conn, case_id)
        case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        documents = [dict(item) for item in conn.execute("SELECT * FROM documents WHERE case_id=? AND is_present=1 ORDER BY relative_path", (case_id,)).fetchall()]
        warnings = [dict(item) for item in conn.execute("SELECT * FROM warnings WHERE case_id=? AND active=1 ORDER BY severity DESC,id", (case_id,)).fetchall()]
        history = [dict(item) for item in conn.execute("SELECT * FROM case_history WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()]
        pipeline_documents = [dict(item) for item in conn.execute("SELECT * FROM pipeline_documents WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]
    checklist = state["checklist"]
    for item in checklist:
        item["status_label"] = CHECKLIST_LABELS.get(item["status"], item["status"])
    return {
        "case": dict(case),
        "documents": documents,
        "warnings": warnings,
        "history": history,
        "pipeline_documents": pipeline_documents,
        "checklist": checklist,
        "checklist_groups": {
            1: [item for item in checklist if item["priority"] == 1],
            2: [item for item in checklist if item["priority"] == 2],
            3: [item for item in checklist if item["priority"] not in {1, 2}],
        },
        "status_label": STATUS_LABELS.get(case["effective_status"], case["effective_status"]),
        "status_labels": STATUS_LABELS,
        "checklist_labels": CHECKLIST_LABELS,
    }


def register_routes(app, cfg: Settings, db: Database, templates: Jinja2Templates) -> None:
    from .main import _csrf_valid, _payload
    taxonomy = TaxonomyAdapter.load()
    taxonomy.seed(db)
    scanner = ScanService(cfg, db, taxonomy)
    ensure_schema(db)
    integration_provider = provider_for(cfg, taxonomy)
    mutation_lock = MutationLock()

    @app.get("/cases")
    def cases(request: Request, q: str = "", status: str = "", unit: str = "", warning: int = 0, missing_p1: int = 0, page: int = 1, sort: str = "updated"):
        page = max(page, 1)
        where = ["c.is_present=1"]
        params: list = []
        if q:
            where.append("(c.person_name_display LIKE ? OR c.person_name_raw LIKE ? OR c.citizen_id LIKE ?)")
            params.extend([f"%{q}%"] * 3)
        if status:
            where.append("c.effective_status=?"); params.append(status)
        if unit:
            where.append("c.unit_code=?"); params.append(unit)
        if warning:
            where.append("EXISTS (SELECT 1 FROM warnings w WHERE w.case_id=c.id AND w.active=1)")
        if missing_p1:
            where.append("c.missing_priority1_count>0")
        order = {"updated": "c.last_scanned_at DESC", "progress": "c.progress_percent ASC", "name": "COALESCE(c.person_name_display,c.folder_name) COLLATE NOCASE"}.get(sort, "c.last_scanned_at DESC")
        sql = "SELECT c.* FROM cases c WHERE " + " AND ".join(where) + f" ORDER BY {order} LIMIT 100 OFFSET ?"
        params.append((page - 1) * 100)
        rows = [dict(row) for row in db.all(sql, tuple(params))]
        units = [row["unit_code"] for row in db.all("SELECT DISTINCT unit_code FROM cases WHERE is_present=1 AND unit_code IS NOT NULL ORDER BY unit_code")]
        context = {
            "rows": rows,
            "q": q,
            "status": status,
            "unit": unit,
            "warning": warning,
            "missing_p1": missing_p1,
            "sort": sort,
            "units": units,
            "status_labels": STATUS_LABELS,
        }
        if _json_requested(request):
            return {"items": rows, "page": page, "count": len(rows)}
        return templates.TemplateResponse(request=request, name="cases.html", context=context)

    @app.get("/cases/{case_id}")
    def case_detail(request: Request, case_id: int):
        try:
            payload = _case_payload(db, case_id)
        except LookupError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)
        if _json_requested(request):
            return payload
        return templates.TemplateResponse(request=request, name="case_detail.html", context=payload)

    @app.post("/cases/{case_id}/status")
    async def case_status(request: Request, case_id: int):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        payload = await _payload(request)
        try:
            with db.session() as conn:
                result = set_manual_status(conn, case_id, payload.get("status", ""))
            return result
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.post("/cases/{case_id}/complete")
    async def complete_case(request: Request, case_id: int):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        payload = await _payload(request)
        try:
            with db.session() as conn:
                return mark_complete(conn, case_id, payload.get("reviewed_by"))
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.post("/cases/{case_id}/reopen")
    async def reopen_case(request: Request, case_id: int):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        try:
            with db.session() as conn:
                return reopen(conn, case_id)
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.post("/cases/{case_id}/checklist/{taxonomy_code}")
    async def checklist_action(request: Request, case_id: int, taxonomy_code: str):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        payload = await _payload(request)
        try:
            with db.session() as conn:
                return set_checklist_override(conn, case_id, taxonomy_code, payload.get("status", ""), payload.get("note"))
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.post("/cases/{case_id}/note")
    async def case_note(request: Request, case_id: int):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        payload = await _payload(request)
        with db.session() as conn:
            update_note(conn, case_id, payload.get("note"))
        return {"ok": True}

    @app.post("/scan")
    async def scan_all(request: Request):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        try:
            with mutation_lock.acquire():
                result = scanner.scan()
                _integrate_all(db, integration_provider)
                _recompute_all(db)
                return result.as_dict()
        except MutationBusy as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.post("/scan/{case_id}")
    async def scan_one(request: Request, case_id: int):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        try:
            with mutation_lock.acquire():
                result = scanner.scan(case_id)
                _integrate_all(db, integration_provider, case_id)
                _recompute_all(db, case_id)
                return result.as_dict()
        except MutationBusy as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)

    def _backup_dir(create: bool = True) -> Path:
        path = cfg.database_path.parent / "backups"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _backup_list() -> list[dict]:
        items = []
        backup_dir = _backup_dir(create=False)
        if not backup_dir.is_dir():
            return items
        for path in sorted(backup_dir.glob("manager-*.sqlite"), key=lambda item: item.stat().st_mtime, reverse=True):
            check = db.integrity_check(path)
            items.append({"name": path.name, "path": str(path), "size_bytes": path.stat().st_size, "valid": check.get("ok", False)})
        return items

    @app.post("/backup")
    async def create_backup(request: Request):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        try:
            with mutation_lock.acquire():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                target = _backup_dir() / f"manager-{stamp}.sqlite"
                db.backup_to(target)
                return {"ok": True, "path": str(target), "metadata_only": True, "integrity": db.integrity_check(target)}
        except MutationBusy as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/backups")
    def backups():
        return {"items": _backup_list()}

    @app.post("/restore")
    async def restore_metadata(request: Request):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        payload = await _payload(request)
        name = Path(payload.get("name", "")).name
        backup_dir = _backup_dir(create=True)
        source = backup_dir / name
        if source.parent != backup_dir or source.suffix.lower() != ".sqlite" or not source.is_file():
            return JSONResponse({"detail": "Backup không hợp lệ hoặc không nằm trong thư mục backup của ứng dụng."}, status_code=400)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        safety = backup_dir / f"manager-before-restore-{stamp}.sqlite"
        try:
            with mutation_lock.acquire():
                safety_path = db.restore_from(source, safety)
        except MutationBusy as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)
        except (OSError, ValueError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return {"ok": True, "restored": source.name, "safety_backup": str(safety_path), "integrity": db.integrity_check()}

    @app.get("/scan-runs")
    def scan_runs(request: Request):
        items = [dict(row) for row in db.all("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 50")]
        if _json_requested(request):
            return {"items": items}
        return templates.TemplateResponse(request=request, name="scan_runs.html", context={"items": items})

    @app.post("/open/case/{case_id}")
    async def open_case(request: Request, case_id: int):
        if not _csrf_valid(request):
            return JSONResponse({"detail": "CSRF token không hợp lệ"}, status_code=403)
        row = db.one("SELECT folder_path FROM cases WHERE id=?", (case_id,))
        if row is None:
            return JSONResponse({"detail": "Không tìm thấy hồ sơ"}, status_code=404)
        path = _safe_path(cfg.data_root, Path(row["folder_path"]))
        if path is None or not path.is_dir():
            return JSONResponse({"detail": "Thư mục không còn tồn tại"}, status_code=404)
        _open_local(path)
        return {"ok": True, "path": str(path)}

    @app.get("/open/document/{document_id}")
    def open_document(document_id: int):
        row = db.one("SELECT relative_path,filename FROM documents WHERE id=? AND is_present=1", (document_id,))
        if row is None:
            return JSONResponse({"detail": "Không tìm thấy tài liệu"}, status_code=404)
        path = _safe_path(cfg.data_root, cfg.data_root / Path(row["relative_path"]))
        if path is None or not path.is_file() or path.suffix.lower() != ".pdf":
            return JSONResponse({"detail": "Tài liệu không hợp lệ"}, status_code=404)
        return FileResponse(path, media_type="application/pdf", filename=row["filename"])


def _integrate_all(db: Database, provider, only_case_id: int | None = None) -> None:
    if provider.__class__.__name__ == "NoopProvider":
        return
    rows = db.all("SELECT id FROM cases WHERE is_present=1" + (" AND id=?" if only_case_id else ""), ((only_case_id,) if only_case_id else ()))
    for row in rows:
        integrate_case(db, row["id"], provider, status_now())


def _recompute_all(db: Database, only_case_id: int | None = None) -> None:
    with db.session() as conn:
        rows = conn.execute("SELECT id FROM cases WHERE is_present=1" + (" AND id=?" if only_case_id else ""), ((only_case_id,) if only_case_id else ())).fetchall()
        for row in rows:
            recompute_case(conn, row["id"])


def _safe_path(root: Path, path: Path) -> Path | None:
    try:
        root = root.resolve()
        candidate = path.resolve()
        candidate.relative_to(root)
        return candidate
    except (OSError, ValueError):
        return None


def _open_local(path: Path) -> None:
    launcher = getattr(os, "startfile", None)
    if launcher is not None:
        try:
            launcher(str(path))
        except OSError:
            pass

