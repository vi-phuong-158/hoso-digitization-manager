# Working Log — Hồ sơ Digitization Manager

## 2026-08-24 — Phase 0

- Files added: `BASELINE.md`, `WORKING_LOG.md`.
- Read `AGENTS.md` and all files under `docs/hoso-digitization-manager-handoff/`.
- Baseline: existing Python digitization pipeline, 104-item taxonomy, HAI golden fixtures, manifest/review/output artifacts.
- Validation: `python -m pytest tests -q` → `151 passed in 19.74s` after installing the declared `pypdf` dependency in the local environment.
- Decision: isolate the Manager under `app.manager`; reuse existing `app.catalog`, `app.pdf_inventory`, `app.manifest`, and pipeline metadata rather than rewriting document processing.
- Limitation: this checkout has no `.git` directory, so phase commits cannot be created. No Git metadata was initialized.
- Gate: `PHASE_0_BASELINE_CAPTURED`.

## 2026-08-24 � Phase 1

- Files added: `app/manager/config.py`, `app/manager/db.py`, `app/manager/main.py`, templates/static, skeleton tests.
- Implemented localhost-only FastAPI app, SQLite WAL bootstrap, metadata-only schema, local static assets, health/dashboard/settings skeleton, CSRF cookie guard.
- Validation: Manager skeleton `2 passed`; full regression `153 passed in 11.43s`.
- Fix: replaced `urllib.parse` form parsing after the legacy source-level no-network test flagged it; local percent decoder is now used.
- Gate: `PHASE_1_APP_SKELETON_PASS`.

## 2026-08-24 � Phase 2

- Files added: `app/manager/taxonomy.py`, taxonomy tests.
- Reused `app.catalog` and `document_types.json`; seeded 104 items into SQLite with official priority values, no duplicate taxonomy source.
- Validation: focused `4 passed`; full regression `155 passed in 11.24s`.
- Fix: corrected a newly written assertion after inspecting the real catalog (`70` is priority 2; `01` is priority 1). Source taxonomy was not changed.
- Gate: `PHASE_2_TAXONOMY_PASS`.

## 2026-08-24 � Phase 3

- Files added: `app/manager/parser.py`, `app/manager/scanner.py`, scanner hard-case tests.
- Implemented read-only folder/PDF inventory, official filename mapping, malformed safe handling, incremental SHA-256 (size+mtime fast path), PDF readability/page count, duplicate warnings, missing reconciliation, reappearance, scan runs, and path/symlink guards.
- Validation: scanner `3 passed`; full regression `158 passed in 12.90s`.
- Fix: first scanner run exposed a nested SQLite session lock while seeding taxonomy; taxonomy is now seeded before the scan transaction.
- Source PDF mutation test passed; no source file is renamed, moved, deleted, or overwritten.
- Gate: `PHASE_3_SCANNER_PASS`.

## 2026-08-24 � Phase 4

- Files added: `app/manager/status.py`, status/invariant tests.
- Implemented checklist effective rules, official priority weighting (P1=3/P2=2/P3+=1), auto/effective case status machine, explicit complete/reopen, checklist overrides, notes/history, missing P1, review-pending precedence, and changed-after-completion warning without auto-downgrade.
- Validation: status tests `4 passed`; full regression `162 passed in 16.20s`.
- Timestamp precision was raised to microseconds so same-second rescans can still detect post-completion changes.
- Gate: `PHASE_4_STATUS_ENGINE_PASS`.

## 2026-08-24 � Phase 5

- Files added: `app/manager/routes.py`, list/detail/settings templates, route tests; dashboard and local CSS completed.
- Integrated FastAPI endpoints for dashboard, cases search/filter/sort, detail, scan all/one, checklist/status/complete/reopen/note, scan runs, settings, safe PDF/folder open.
- Security: localhost config validation, CSRF token on state-changing POSTs, ID-based file resolution and canonical data-root boundary checks; no arbitrary path endpoint.
- Validation: route tests `2 passed`; full regression `164 passed in 13.45s`.
- Gate: `PHASE_5_UI_PASS`.

## 2026-08-24 � Phase 6

- Files added: `app/manager/integration.py`, integration tests; SQLite `pipeline_documents` metadata table is created idempotently at runtime.
- Read actual existing pipeline artifact schema: `output/<person>/_manifest.json` and `logs/<person>/manifest.apply.json`/`manifest.dryrun.json`; existing ledger filename is `_manifest.json`.
- Implemented read-only ManifestProvider/NoopProvider, catalog type validation, pipeline logical-document metadata, review-pending warnings, and scan-route wiring. No existing manifest/ledger is modified.
- Validation: integration+route tests `4 passed`; full regression `166 passed in 15.52s`.
- Fallback: when manifest/ledger path is absent, filesystem scanner remains authoritative and no false review warning is created.
- Gate: `PHASE_6_INTEGRATION_PASS`.

## 2026-08-24 � Phase 7

- Files added: synthetic fixture builder and offline E2E smoke tests.
- Fixture coverage: standard/malformed folders, standard and multi-instance names, unknown taxonomy, duplicate bytes, missing-P1/no-file, unreadable PDF, deleted/reappeared behavior, completion then modification, checklist actions.
- Validation: E2E smoke `2 passed`; full regression `168 passed in 17.38s`.
- E2E uses FastAPI TestClient because Playwright is not part of the available local runtime; no Internet dependency was introduced. Core flow is exercised end-to-end through real routes, SQLite, scanner, and status engine.
- Gate: `PHASE_7_E2E_PASS`.

## 2026-08-24 � Phase 8

- Files added: `app/manager/entrypoint.py`, `HosoManager.spec`, `build_manager.ps1`, `PACKAGING.md`; requirements now include FastAPI/Jinja2/Uvicorn/PyInstaller.
- Built on Windows 11 with PyInstaller 6.19.0 / Python 3.12.9.
- First build exposed an onedir/onefile layout mismatch and a relative-import startup error; fixed spec to onedir and entrypoint to absolute imports.
- Packaging validation: `dist/HosoManager/HosoManager.exe` exists (9,897,444 bytes), bundled taxonomy/templates/static exist, executable `/health` returned `{"status":"ok","service":"hoso-digitization-manager","offline":true}` on `127.0.0.1:8765`, then process was stopped.
- Full regression after packaging changes: `168 passed in 18.22s`.
- Gate: `PHASE_8_WINDOWS_PACKAGE_PASS`.

## 2026-08-24 � Phase 9

- Final artifacts added: `MANAGER_README.md`, `PILOT_REPORT.md`.
- Golden acceptance: PASS (`18 logical document / 29 pages`, 0 errors).
- Static compile: PASS; final full suite: `168 passed in 17.40s`.
- Benchmark: synthetic 10-folder/10-PDF first scan `128.37 ms`, 10 hashes; unchanged second `137.96 ms`, 0 hashes.
- Source inventory: 2 actual folders, 4 PDFs, 50 pages. Exact SHA-256 recorded in `PILOT_REPORT.md`; HAI hashes match existing manifest.
- Packaging runtime: onedir executable `/health` PASS on localhost, offline response verified.
- Final gate: `DIGITIZATION_MANAGER_MVP_READY_FOR_LOCAL_PILOT`.

## 2026-08-24 — Phase 10 — Real Data Pilot & Hardening

- Real corpus pilot ran read-only against 2 person folders, 4 PDFs, 50 pages using a temporary SQLite DB; source path/size/mtime/SHA-256 snapshot was unchanged before/after.
- Existing manifest integration loaded 18 logical documents read-only; taxonomy count remained 104; UI/API smoke and metadata-only backup returned successfully.
- Added SQLite online-backup operation/`GET /backup`, manifest logical-document status evidence, and Windows single-instance lock hardening. No source PDF/folder content changed.
- Reliability/scale: state persistence, completion/change warning, path traversal, invalid PDF, backup/restore and WAL integrity tests passed; 500-case/5,000-PDF benchmark: first 16.20s/5,000 hashes, unchanged 11.99s/0 hashes, one changed 12.07s/1 hash.
- Validation: full regression `172 passed in 18.89s`; golden `18 logical document / 29 pages / 0 lỗi`; compileall PASS; Windows onedir build and single-launch health PASS.
- Gate limitation: the real corpus has only 2 cases, so the required minimum-20 manual spot-check cannot be completed honestly. Package double-launch hidden-process observation was not deterministic on this runner; lock unit coverage passes.
- Git provenance remains unresolved: no `.git` metadata exists in the workspace or nearby parents, so phase commits cannot be created.
- Gate: `DIGITIZATION_MANAGER_REAL_DATA_PILOT_PARTIAL`.
# Review & Repair pipeline — 2026-08-26

- Inventory: canonical incremental state là `state/processing_state.db`; manifest
  ở `output/<người>/_manifest.json`; global naming có rename plan hai pha; Manager
  là FastAPI/Jinja local. Không tạo state store mới.
- Thêm migration schema v5: review sessions/findings, repair plans, revisions và
  correction ledger metadata-only.
- Thêm deterministic audit, optional semantic finding intake không có quyền
  mutation, ACCEPT/KEEP_EXISTING/MANUAL_FIX, dry-run repair, stale-base/idempotent
  guard, history/diff và anonymized benchmark/correction exports.
- Thêm CLI review/repair và Manager section `Rà soát hồ sơ` với safety banner.
- Bổ sung semantic-review adapter explicit (OpenAI-compatible, provider/model/env
  configurable) với PNG scope renderer `pdftoppm`, prompt versioned, output
  validator fail-closed, evidence/fingerprint/reviewer-version và KEEP_EXISTING
  suppression có điều kiện. Adapter không thuộc offline runtime pipeline.
- Bổ sung executable repair coverage cho merge/split/add missing/remove extra,
  duplicate, filename và legacy page-order; giữ source hash không đổi.
- Validation hiện tại: `tests/test_review_repair.py` + migration contract = 31
  passed. Manager review test và Windows build đang PENDING vì local `.venv`
  thiếu FastAPI/PyInstaller; cài `requirements.txt` bị policy chặn do cần xác
  nhận trực tiếp từ người vận hành.
- Rehearsal thực hiện trên bản clone tạm có hash source/state đối chiếu, copy
  output/review tối thiểu, rồi deterministic audit → ACCEPT một WRONG_FILENAME
  → plan → dry-run → apply → reconcile → history/diff. Clone tạo revision 2,
  source hashes không đổi và production input/state không bị ghi; clone nhạy
  cảm được xóa ngay. Filename rename có thể chạm naming dependency closure để
  tránh collision, không reprocess các trang ngoài scope.
- Rehearsal thực tế (review + repair dry-run, không apply) bị chặn trước khi tạo
  session vì `state/processing_state.db` trong workspace hiện chỉ-đọc. Không có
  source/output/manifest canonical nào bị thay đổi; cần quyền ghi state hoặc một
  runtime workspace writable để hoàn tất gate này.
