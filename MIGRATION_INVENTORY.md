# Migration inventory

## Source checkout

- Original: `D:\\01. Công việc\\Số hóa hồ sơ Đảng viên`
- Target: `D:\\04. Github\\hoso-digitization-manager`
- Method: copy only; the original checkout and its data remain in place.

## Copied

- `app/`: application and deterministic digitization pipeline source.
- `tests/`: unit, integration, manager, runtime-safety and Golden tests.
- `fixtures/`: checked-in synthetic page-signal fixtures only.
- `test_cases/`: checked-in synthetic Golden contract only.
- `docs/`, `.agents/`: project documentation and runtime instructions.
- `document_types.json`, `requirements.txt`, PyInstaller spec and build script.
- Safe project documentation required to build and operate the source repository.

## Excluded

- `input/`, `output/`, `review/`, `analysis/`, `analysis_blind/`: real corpus and
  processing artifacts.
- `logs/`, `state/`, `data/`: runtime databases, WAL files, and logs.
- `.venv/`, `.pytest_cache/`, `build/`, `dist/`, `.git/`: environment, caches,
  generated binaries, and source repository metadata.
- Old pilot reports containing real source filenames/hashes: excluded from the
  Git candidate; the source copies were not modified.
- `config.local.json`: created only as an ignored laptop-local configuration.

## Uncertain

No uncertain file was copied. Any future file not clearly classified as source,
test, safe synthetic fixture, or documentation must be reviewed before copying.
