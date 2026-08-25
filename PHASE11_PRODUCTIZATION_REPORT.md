# Phase 11 productization report

## VERDICT

`DIGITIZATION_MANAGER_V0_2_TECHNICAL_PASS_INSTALLER_GATE_PENDING`

Application, source regression, Golden, benchmark and packaged GUI runtime
gates are green. The final product verdict remains pending because this host has
neither `ISCC.exe` nor an approved external installation path for Inno Setup;
the actual installer and clean-install verification have not run.

## BASELINE

- Starting branch: `main`
- Starting SHA: `d9938410ac0c75cabff7b83d59f9f9307bbf9e78`
- Final branch: `feat/phase-11-productization`
- Final SHA: pending commit; changes are currently uncommitted

## UX

- Dashboard: operational summary cards, overall progress, status bars, unit
  table and heuristic “Cần xử lý” queue.
- Case list: Vietnamese status labels, quick-filter chips, search, unit/warning/
  priority filters, sorting and full-row navigation.
- Case detail: two-column layout, status/progress header, grouped checklist,
  direct checklist override, warnings, notes, files and recent history.
- Settings: machine-specific data root, diagnostics, version/build identity and
  metadata backup/restore.
- Error states: empty data root, empty result, empty dashboard, toast errors,
  scan loading state and restore validation messages.
- Visual QA: synthetic fixture at 1366×768; the empty-state scan binding issue
  was found and fixed. No real PII screenshot was created.

## WINDOWS

- Executable: PyInstaller onedir build completed from repository source at
  `dist/HosoManager/HosoManager.exe`; console disabled and version metadata
  embedded.
- Single instance: existing Windows file lock retained and second launch gives
  a clear local message.
- Installer: Inno Setup script added at `installer/HosoManager.iss`, with
  per-user install location, Start Menu/Desktop shortcuts, uninstall support and
  exclusions for config/database/PDF data. `ISCC.exe` was not installed, so no
  installer binary was produced.
- Startup: launcher waits on Uvicorn's local bound-server signal before opening
  the browser and writes append-only `startup.log` milestones. Cold-start smoke
  reached `/health` in `59.1s`; warm restart reached it in `1.2s`.
- The GUI bundle disables Uvicorn console logging (there is no console stream)
  and lazy-loads `pypdf` on scan, keeping the cold-start within the bound.
- Offline: source/runtime tests pass; no CDN or runtime external service was
  added.

## DATA CONFIG

- Machine-specific configuration remains in local `config.json`/`config.local.json`
  or `HOSO_DATA_ROOT`.
- No source code hard-codes the laptop's D: data root for runtime selection.
- The visual fixture and test databases were temporary and removed after testing.

## BACKUP

- SQLite backup uses the SQLite backup API and timestamped metadata-only files.
- Restore validates `PRAGMA integrity_check`, checks required tables, creates a
  safety backup, then atomically replaces the metadata database.
- Fixture coverage: backup, restore, invalid backup rejection and SQLite
  integrity all pass.

## VALIDATION

- Unit/integration/API/UI regression: `333 passed, 2 skipped, 0 failed`.
- Golden: PASS — `18 logical documents`, `29 pages`.
- E2E fixture routes: manager tests and new Phase 11 fixture tests pass; full
  Playwright suite was not present in the repository.
- 500/5,000 synthetic benchmark: first scan `11.198s`, warm scan `9.109s`,
  unchanged warm rehashes `0`, errors `0`.
- Offline/security: full runtime no-network, localhost/path safety and CSRF
  tests pass.
- Windows runtime: PyInstaller build pass; cold and warm `/health` smoke pass.
- Installer: script present; compiler unavailable (`ISCC_NOT_FOUND`).

## DATA SAFETY

```text
PDF renamed: NO
PDF moved: NO
PDF deleted: NO
PDF modified: NO
External upload: NO
```

## GIT

- Branch: `feat/phase-11-productization`
- Commits: no new commit created in this session
- PR: not created
- CI: not run
- Merge status: unmerged
- Release/tag status: no `v0.2.0` tag

## KNOWN LIMITATIONS

- Need Inno Setup installed to compile and test the actual installer, shortcut
  and uninstall flow.
- The repository has no Playwright E2E suite; synthetic browser QA covered the
  relevant manager screens.

## NEXT ACTION

Install/enable Inno Setup on the Windows build host, then run
`build_installer.ps1`, clean-install, shortcut/uninstall and final release
checks. Do not tag `v0.2.0` before those gates are green.
