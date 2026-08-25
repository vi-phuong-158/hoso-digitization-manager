from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.manager.config import Settings
from app.manager.db import Database
from app.manager.scanner import ScanService
import app.manager.scanner as scanner_module
from tests.manager.test_scanner import make_pdf


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    temp = Path(tempfile.mkdtemp(prefix="digitization-scale-bench-"))
    try:
        root = temp / "input"
        root.mkdir()
        seed = temp / "seed.pdf"
        make_pdf(seed)
        base = seed.read_bytes()
        for folder_no in range(500):
            folder = root / f"25.000.036.001.015_{folder_no:012d}_Person_{folder_no:04d}"
            folder.mkdir()
            for file_no in range(10):
                # Trailing comments preserve the valid PDF while making every
                # fixture byte sequence distinct for duplicate detection.
                (folder / f"01.Ly_lich_nguoi_xin_vao_dang.{file_no}.pdf").write_bytes(base + f"\n% fixture-{folder_no}-{file_no}\n".encode())
        db = Database(temp / "manager.db")
        db.initialize()
        service = ScanService(Settings(data_root=root, database_path=temp / "manager.db"), db)
        original = scanner_module.sha256_file
        calls = {"n": 0}

        def counted(path):
            calls["n"] += 1
            return original(path)

        scanner_module.sha256_file = counted
        started = time.perf_counter(); first = service.scan(); first_ms = round((time.perf_counter() - started) * 1000, 2)
        first_hashes = calls["n"]
        calls["n"] = 0
        started = time.perf_counter(); second = service.scan(); second_ms = round((time.perf_counter() - started) * 1000, 2)
        second_hashes = calls["n"]
        changed = next(root.rglob("*.pdf"))
        changed.write_bytes(changed.read_bytes() + b"\n% changed")
        calls["n"] = 0
        started = time.perf_counter(); third = service.scan(); third_ms = round((time.perf_counter() - started) * 1000, 2)
        third_hashes = calls["n"]
        print(json.dumps({
            "fixture_folders": 500,
            "fixture_pdfs": 5000,
            "first_ms": first_ms,
            "first_hashes": first_hashes,
            "first_status": first.status,
            "second_ms": second_ms,
            "second_hashes": second_hashes,
            "second_status": second.status,
            "third_ms_one_changed": third_ms,
            "third_hashes_one_changed": third_hashes,
            "third_status": third.status,
            "db_cases": db.one("SELECT COUNT(*) AS n FROM cases")["n"],
            "db_documents": db.one("SELECT COUNT(*) AS n FROM documents")["n"],
            "db_integrity": db.one("PRAGMA integrity_check")[0],
        }, indent=2))
    finally:
        scanner_module.sha256_file = original if "original" in locals() else scanner_module.sha256_file
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()

