# Working log — source Git migration

## 2026-08-25

- Read the workspace and nested project instructions before editing.
- Confirmed the source checkout contains both application code and real runtime/data trees.
- Created `D:\\04. Github\\hoso-digitization-manager` as a separate target.
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
- GitHub private repository confirmed and main pushed successfully.
- `MIGRATION_REPORT.md` records the final migration verdict, safety gates and limitations.

Validation and Git/GitHub results are appended after each gate is run.
