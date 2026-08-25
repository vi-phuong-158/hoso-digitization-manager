# Phase 11C — Release closure report

## VERDICT

`DIGITIZATION_MANAGER_V0_2_PRODUCTIZATION_PASS`

All mandatory local and remote release gates are green. The productization
changes are merged into `main` and published as `v0.2.0`.

## SECURITY FIXES

- Localhost-only `TrustedHostMiddleware` accepts only `127.0.0.1` and
  `localhost`.
- State-changing backup and folder-open actions require POST plus CSRF; the
  old state-changing `GET /backup` route is removed.
- Scan, backup and restore mutations use a non-blocking process-local lock and
  return a clear conflict response instead of overlapping SQLite operations.
- Restore validates the backup, creates a safety backup, and uses SQLite's
  backup API so Windows WAL handles are not deleted or replaced while open.
- Startup failure logging keeps exception types and safe messages only; local
  config paths and raw exception text are not written to `startup.log`.
- Local fallback configuration is `config.local.json`, which is ignored by
  Git. Installer exclusions cover runtime config, databases, logs, locks,
  PDFs and input/output/review/backup folders.

## STARTUP

- PyInstaller onedir EXE starts hidden, binds only to localhost and exposes
  `/health` with `offline: true`.
- Corrected-harness packaged measurements: cold-ish runs `1.4s`, `1.3s`,
  `1.3s`; warm restart `1.3s`; all health checks passed.
- A/B packaging comparison: UPX enabled and disabled both measured
  `80.58 MB` bundle / `12.86 MB` EXE with no observed runtime or size gain;
  release configuration is `upx=False` for reproducibility.

## EXE

- Build command: `build_manager.ps1`.
- Portable bundle: `dist/HosoManager/HosoManager.exe`.
- Tagged-main source commit: `604b81d3f5b328078778abbcf80229172d5fb5dd`.
- Final EXE SHA-256: `994bb64ef1c63b6517dbe8f30f5b395e7ecd632849ee94a174b67809205f6691`.

## INSTALLER

- Inno Setup 6.7.3 compiled `HosoManager-Setup-v0.2.0.exe` successfully.
- Clean-install evidence in an isolated per-user test path:
  installer exit `0`; installed `/health` and dashboard `200`; backup and
  restore passed; config persistence passed; second instance was blocked while
  the first remained healthy; Start Menu and Desktop shortcuts were created;
  uninstaller exit `0`; program files were removed. User-created
  `config.local.json` was preserved as expected and the temporary install root
  was then removed.
- Installer artifact checksum is refreshed after the final release rebuild.
- Final installer size: `30.64 MB`; SHA-256:
  `5f72f0644aeda605c8e4026cf70fdf45fc5cafe0b813d2b8c76ba1e60e21305c`.

## CI

- Added `.github/workflows/ci.yml` for Python 3.12 compile and full pytest on
  pushes to `main`/feature and pull requests to `main`.
- Local command mirrors CI: `python -m compileall -q app tests` and
  `python -m pytest tests -q`.
- Remote CI: PASS on both push and pull-request workflows.

## TESTS

- Full regression: `339 passed, 2 skipped, 0 failed`.
- No test failure is hidden; Python 3.13 subprocess decoding and Windows WAL
  restore regressions were fixed and rerun.

## GOLDEN

- `python -m app.cli test-golden --provider agent`
- PASS: `18 logical documents / 29 pages`, `0 lỗi`.

## BENCHMARK

- Synthetic-only benchmark: `500 cases / 5,000 PDFs`.
- First scan: `20.575s`; warm scan: `13.376s`.
- First analyzed sources: `500`; unchanged warm rehashes: `0`; errors: `0`.

## PUBLIC REPOSITORY AUDIT

- Current tracked-content audit found no real PDFs, runtime databases, logs,
  credentials, private keys, real corpus names or exact workstation data paths.
- `PII_SECRET_AUDIT.md` records the re-audit as PASS. Synthetic fixture values
  remain deterministic test data.

## DATA SAFETY

```text
PDF renamed: NO
PDF moved: NO
PDF deleted: NO
PDF modified: NO
External upload: NO
Real corpus opened: NO
```

## PR

- PR: [#1](https://github.com/vi-phuong-158/hoso-digitization-manager/pull/1),
  merged.
- Required review scope: security/runtime hardening, CI, packaging and public
  repository audit only; no taxonomy or Golden changes.

## GIT

- Release-candidate branch: `feat/phase-11-productization`.
- Release-candidate commit: `089ba0f85b7dc763bd2999ed1824e2b926f73ba9`.

## MERGE

- Merge target: `main`.
- Merge status: merged into `main` at
  `604b81d3f5b328078778abbcf80229172d5fb5dd`.

## RELEASE

- Tag: `v0.2.0` on the merged main commit.
- GitHub release: https://github.com/vi-phuong-158/hoso-digitization-manager/releases/tag/v0.2.0
- Installer attachment was rebuilt from tagged `main` and uploaded.

## KNOWN LIMITATIONS

- The repository has no Playwright E2E suite; manager route and packaged
  runtime checks use synthetic fixtures and HTTP smoke tests.
- The release installer is unsigned by this project; Inno Setup's compiler
  output is otherwise built and verified locally.
