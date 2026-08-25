# Hồ sơ Digitization Manager — Pilot Report

Captured: 2026-08-24 (Asia/Saigon)

## VERDICT

`DIGITIZATION_MANAGER_MVP_READY_FOR_LOCAL_PILOT`

## BASELINE

- Existing pipeline baseline: `151 passed`.
- Final validation suite: `168 passed in 17.40s`.
- Golden: `HAI_GOLDEN.json` — `18 logical document / 29 trang`, `0 lỗi`.
- Git: this checkout has no `.git` worktree, so starting/final HEAD SHA and phase commits are unavailable. No Git metadata was initialized.

## IMPLEMENTED

- Local FastAPI + Jinja2 UI with dashboard, list/search/filter/sort, case detail, checklist, warnings, history, notes, settings, scan runs, and safe open actions.
- SQLite WAL metadata database; no PDF bytes stored.
- Read-only incremental scanner: folder/file parsing, malformed-safe inventory, SHA-256 only for new/changed files, missing reconciliation, reappearance, duplicate warnings, unreadable-PDF warnings.
- Official 104-item taxonomy adapter and priority-aware progress.
- State machine: `CHUA_XU_LY`, `DANG_SO_HOA`, `CHO_KIEM_TRA`, `CAN_BO_SUNG`, explicit `HOAN_THANH`, reopen, checklist overrides, history, changed-after-completion warning.
- Read-only adapters for existing `_manifest.json` / `manifest.apply.json` / `manifest.dryrun.json`; Noop/filesystem fallback when absent.
- Synthetic 10-folder fixture tree and offline E2E smoke.
- Windows onedir packaging: `dist/HosoManager/HosoManager.exe`.

## DATA SAFETY

- Source PDFs modified: **NO**.
- Source PDF rename/move/delete: **NO**.
- External upload/analytics/CDN: **NO**.
- Existing pipeline artifacts modified: **NO**.
- State-changing POSTs require CSRF token; open-file endpoints accept only database IDs and enforce canonical containment under `data_root`.

## INTEGRATION

- Taxonomy: `document_types.json` through existing `app.catalog`.
- Manifest/ledger: existing output/log JSON schema; read-only `ManifestProvider`.
- Fallback: `NoopProvider` + filesystem scanner; no false review state when integration is not configured.

## VALIDATION

- Unit/integration/route/E2E/legacy regression: `168 passed`.
- Golden acceptance: PASS.
- Compile check: `python -m compileall -q app tests` PASS.
- Windows packaging: PyInstaller 6.19.0 on Windows 11 / Python 3.12.9 PASS.
- Executable runtime smoke: `/health` returned `{"status":"ok","service":"hoso-digitization-manager","offline":true}` on `127.0.0.1:8765`.
- Incremental benchmark on 10 synthetic folders / 10 PDFs: first scan `128.37 ms`, `10` hashes; unchanged second scan `137.96 ms`, `0` hashes.

## PILOT SUMMARY

Actual repository input inventory: 2 folders, 4 PDFs, 50 pages total; HAI has 3 PDFs/29 pages, Vi Ngọc Phương has 1 PDF/21 pages. The existing HAI manifest confirms its three source hashes.

Synthetic fixture acceptance: 10 folders, 10 PDFs, malformed folder, unknown name, duplicate bytes, missing/no-file cases, unreadable PDF, completion/change warning, and reappearance behavior.

Exact source PDF SHA-256:

| Source file | SHA-256 |
|---|---|
| `input/Nguyễn Hữu Hải/Bang cap cua HAI.pdf` | `af2752447a0006d4a23daf34f09910c7d08d2f95b5fae5e4073e64eff3959e21` |
| `input/Nguyễn Hữu Hải/Phieu bo sung hs dang vien 2020 HAI.pdf` | `a179d62465161085e11e2d5df8481d7520f7c11f5a62c09ba74506f987367d35` |
| `input/Nguyễn Hữu Hải/Quyet dinh dieu dong HAI.pdf` | `6642a39763732646a9a933ff84ca7c477247aad40d65aafebc0cee1b5c2824b5` |
| `input/Vi Ngọc Phương/vi-phuong.pdf` | `caf017dfe848c8e4f4edc81462eee6afb2ba329545ea7be3f317bc2bef10b673` |

## KNOWN LIMITATIONS

- The checkout has no Git metadata, so checkpoint commits cannot be represented here.
- The current runtime has no Playwright package; E2E acceptance uses real FastAPI/TestClient routes and the packaged executable health smoke instead.
- Folder names and raw input filenames in the existing sample are intentionally malformed; the Manager reports warnings and does not auto-rename them.
- Manifest/ledger enrichment requires setting `manifest_path` or `ledger_path` in `config.json`; core filesystem scanning does not require it.

## NEXT ACTION

Copy the onedir bundle to a pilot Windows machine, set `data_root` in `config.json` to a read-only source root, launch `HosoManager.exe`, and run the first dry metadata scan.
