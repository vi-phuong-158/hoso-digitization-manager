# Source Git migration report

## VERDICT

`SOURCE_CODE_GIT_MIGRATION_PASS`

## SOURCE

- Original: external source checkout (path intentionally omitted)
- Target: this public repository checkout
- Method: source copy only; the original checkout was not deleted, renamed, or moved.

## DATA

- Data root used by laptop config: machine-local path, intentionally omitted
- Data moved: `NO`
- Source inventory counts are intentionally omitted from public documentation.
- Target does not contain the real corpus, source PDF bytes, runtime logs, or production DB.

## GIT

- Repository root: this repository checkout
- Branch: `main`
- First baseline commit: `227e47c227d6e9f3d6884a919286b192a4e8ca9c`
- Final validated migration SHA: `89979df7430c5314ef6a2a8061a308656dbc8155`
- Tag: `v0.1.0-pilot`

## GITHUB

- Repository: `vi-phuong-158/hoso-digitization-manager`
- Visibility: `PUBLIC`
- Remote: `https://github.com/vi-phuong-158/hoso-digitization-manager`
- Push status: `SUCCESS` (`main` pushed; tag pushed after final validation)

## SAFETY

```text
Real PDF tracked by Git: NO
Production DB tracked: NO
Logs tracked: NO
Local config tracked: NO
Secrets detected: NO
Source data modified: NO
Source data moved: NO
```

The laptop `config.local.json` is ignored and contains machine-specific paths.
The checked-in `config.example.json` contains placeholders only. The target
runtime DB remains ignored and local to the target/bundle; the old source DB in
the data checkout was left untouched. Do not run one live SQLite file
simultaneously from two machines.

## VALIDATION

- Full pytest: `332 collected; 330 passed; 0 failed; 2 skipped` in 17.16s.
- Skips: optional blind-analysis and extra-real-corpus checks; those source data
  trees were intentionally excluded from Git.
- Golden CLI: PASS — 1 file, 18 logical documents, 29 pages, 0 errors.
- Compile: `python -m compileall -q app tests` PASS.
- Real-data smoke: completed before public sanitization; operational counts and
  machine-specific paths are intentionally omitted here. Source snapshot was
  unchanged.
- Windows package: PASS — PyInstaller onedir executable rebuilt; packaged
  `/health` returned offline OK and dashboard returned 200.
- Runtime: offline path retained; no network/API dependency was introduced.

## CONFIG

- Source run: create ignored `config.local.json` from `config.example.json`.
- Laptop: set `data_root` to the operator's local data checkout.
- Desktop: set `data_root` to that machine's Google Drive mirror path.
- `HOSO_DATA_ROOT` can override the JSON `data_root` without source changes.
- `config.json` beside the executable is used for packaged runs; source runs
  prefer `config.local.json`.

## KNOWN LIMITATIONS

- The two skipped tests require additional real blind-analysis/corpus data and
  remain intentionally skipped because that data must not enter Git.
- The smoke gate did not invoke OS-level PDF/folder opening; it exercised the
  safe route resolution through the full test suite and kept the real corpus
  read-only.
