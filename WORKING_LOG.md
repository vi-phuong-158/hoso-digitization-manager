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

Validation and Git/GitHub results are appended after each gate is run.
