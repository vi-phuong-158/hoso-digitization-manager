# Working log — source Git migration

## 2026-08-25

- Read the workspace and nested project instructions before editing.
- Confirmed the source checkout contains both application code and real runtime/data trees.
- Created a separate source-only target checkout.
- Copied source, tests, synthetic fixtures, safe docs, taxonomy, requirements and packaging files.
- Excluded real corpus, runtime databases, logs, caches, build output and old Git metadata.
- Removed copied pilot reports that contained real source filenames/hashes; original files were untouched.
- Added machine-specific configuration support: ignored `config.local.json` and `HOSO_DATA_ROOT`.
- Added `MIGRATION_INVENTORY.md` and `PII_SECRET_AUDIT.md`.
- Anonymized the checked-in Golden fixture label to `Synthetic Person`; Golden tests remain isolated and synthetic.
- Added `httpx2` test dependency required by the installed Starlette TestClient.
- Full validation: 330 passed, 2 skipped; Golden CLI PASS; compileall PASS.
- Real-data smoke: SUCCESS against external D: root using a temporary DB; source snapshot unchanged.
- Rebuilt and launched the Windows onedir package; health/dashboard PASS and D: data root confirmed.
- Initialized local Git on `main`; baseline commit is `227e47c227d6e9f3d6884a919286b192a4e8ca9c`.
- GitHub repository confirmed and main pushed successfully.
- `MIGRATION_REPORT.md` records the final migration verdict, safety gates and limitations.

Validation and Git/GitHub results are appended after each gate is run.

## 2026-08-25 — Phase 11 productization

- Starting checkout: `main`, SHA `d9938410ac0c75cabff7b83d59f9f9307bbf9e78`; created `feat/phase-11-productization` after `git pull --ff-only` reported up to date.
- UX audit recorded in `docs/PHASE11_UX_BASELINE.md`; real data was not opened or captured.
- Refined manager shell, dashboard, cases table, case detail, checklist, settings, scan history and local CSS/JS/SVG assets. Added Vietnamese status language, loading/error/empty/toast states and row navigation.
- Added metadata backup/restore routes and database integrity validation. Restore validates the backup, creates a safety backup and atomically replaces only the SQLite metadata file.
- Added `v0.2.0` identity, startup diagnostics, no-console launcher, server-start wait, single-instance notification and per-user Inno Setup script.
- Added Phase 11 fixture tests: `3 passed`; existing manager tests: `23 passed`.
- Full suite checkpoint: `329 passed, 2 skipped, 1 failed` on the first run because the runtime no-network gate correctly rejected an initial `socket` import in the launcher. Removed that import and retained the offline `uvicorn.Server.started` readiness signal.
- Rebuilt PyInstaller onedir executable from repository source: build completed; bounded executable smoke still requires a clean follow-up runtime investigation before PASS.
- Inno Setup compiler was not present (`ISCC_NOT_FOUND`); installer artifact is therefore pending and no installer PASS is claimed.
- Full final validation: `333 passed, 2 skipped, 0 failed`; Golden CLI: `18 logical documents / 29 pages`, PASS.
- Visual QA with synthetic fixture at 1366×768 covered empty dashboard, populated dashboard, cases/filter table and case detail. Found and fixed empty-state scan binding; no real-data screenshot was used or committed.
- Source offline/security gate passed in the full suite. The only URL reference is the local browser address `127.0.0.1`; no CDN/font/telemetry asset was added.
- No commit, push, PR, merge or tag was created in this session. Branch remains reviewable with uncommitted Phase 11 changes.

## 2026-08-25 — Phase 11B runtime and release closure

- Diagnosed the packaged GUI startup path with milestone logging. The issue was slow PyInstaller cold-start plus Uvicorn console logging in a GUI build without console streams.
- Switched startup logging to append mode, disabled Uvicorn console logging for the GUI bundle, and lazy-loaded `pypdf` from the scan path.
- Rebuilt the GUI artifact and verified cold-start `/health` in `59.1s`; warm restart was `1.2s` and configuration/database persistence remained intact.
- Rehearsed the second-instance path: the original listener stayed healthy and the second launch used the local notification path without replacing the server.
- Full validation after Phase 11B changes: `333 passed, 2 skipped, 0 failed`; Golden `18 logical documents / 29 pages`, PASS.
- Synthetic scale benchmark: `500 cases / 5,000 PDFs`; first scan `11.198s`, warm scan `9.109s`, unchanged warm rehashes `0`.
- `ISCC.exe` remains unavailable. The official Inno Setup installation attempt was rejected at the external system-install approval gate; installer build, clean install, shortcut and uninstall gates remain pending.
- Productization commit `675a56504a5165c00dc9daecb1e9513ae88d2b00` was pushed to `origin/feat/phase-11-productization`; no PR, merge or release tag was created while the mandatory installer gate is red.

## 2026-08-25 — Phase 11C release closure

- Re-audited tracked public content and removed stale workstation paths,
  private-repository wording and real inventory details from public docs.
- Hardened local runtime boundaries: TrustedHost localhost allow-list, POST +
  CSRF for state-changing routes, mutation lock, safe startup logging and
  ignored local config fallback.
- Fixed Windows SQLite restore to use the SQLite backup API rather than
  deleting/replacing a live WAL sidecar; hardened Git-integrity subprocess
  decoding for Python 3.13.
- Added explicit test package paths and CI workflow. Full regression:
  `339 passed, 2 skipped, 0 failed`; Golden: `18 logical documents / 29 pages`,
  PASS.
- Synthetic benchmark: `500 cases / 5,000 PDFs`; first `20.575s`, warm
  `13.376s`, unchanged warm rehashes `0`, errors `0`.
- Packaged EXE A/B: UPX on/off both `80.58 MB` bundle and `12.86 MB` EXE;
  release choice is `upx=False`. Corrected-harness cold-ish startup was
  `1.4s`, `1.3s`, `1.3s`; warm `1.3s`.
- Installed official Inno Setup 6.7.3 after Authenticode and release-hash
  verification. Installer compiled successfully; clean-install runtime,
  backup/restore, persistence, shortcuts, single-instance and uninstall gates
  passed using synthetic temporary data.
- PR, merge, tag and GitHub release remain pending until the release-candidate
  commit is pushed and remote CI is green.

## 2026-08-25 — Phase 11C published release

- PR #1 passed both push and pull-request CI workflows and merged into `main`.
- Merged main SHA and tag target: `604b81d3f5b328078778abbcf80229172d5fb5dd`;
  annotated tag `v0.2.0` pushed successfully.
- Rebuilt the portable EXE and Inno Setup installer from tagged main, verified
  final packaged `/health` as `ok`, `offline=true`, with matching build SHA.
- GitHub release published with the final installer asset; productization
  verdict is `DIGITIZATION_MANAGER_V0_2_PRODUCTIZATION_PASS`.
