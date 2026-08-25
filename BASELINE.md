# Baseline — Hồ sơ Digitization Manager

Captured: 2026-08-24 (Asia/Saigon)

## Repository state

- Working directory is not a Git worktree: `git status`, branch, HEAD, and remotes all fail with `not a git repository`.
- Therefore phase checkpoint commits cannot be created in this checkout. No Git metadata was initialized or modified.
- Existing source PDFs under `input/` were treated as read-only.

## Existing pipeline

- Python package: `app/`.
- Existing deterministic pipeline covers inventory, page observations, segmentation, classification policy, taxonomy-backed naming, manifest, writer, and QC.
- Official taxonomy: `document_types.json`, 104 document types.
- Existing provider path is local analysis JSON (`analysis/` and `fixtures/vision/`); no network is required by the runtime path.
- Existing artifacts from the source checkout were excluded; checked-in Golden assets are synthetic.
- Golden acceptance: `test_cases/HAI_GOLDEN.json`.

## Baseline tests

After installing the already-declared `pypdf` dependency in the local Python environment:

```text
151 passed in 19.74s
```

The first attempt failed only because `pypdf` was missing from the environment; `requirements.txt` already declared it. The application remains designed to run offline after dependencies are installed.

## Manager implementation decision

The Manager is added as an isolated `app.manager` package so the existing digitization engine remains unchanged and reusable. The Manager uses FastAPI + Jinja2 + SQLite, stores metadata only, scans source folders read-only, and exposes pipeline manifest/ledger adapters without changing existing artifacts.

## Phase 0 gate

`PHASE_0_BASELINE_CAPTURED`
