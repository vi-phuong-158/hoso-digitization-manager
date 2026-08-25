# Phase 12C — Release Provenance & Real-Data Closure

Captured: 2026-08-25 (Asia/Saigon). This report intentionally does not claim a
pilot PASS. Counts and identifiers below are anonymized; no person name, file
name, source path, individual source hash, extracted text, or image is stored.

## Verdict

`PHASE12_REAL_DATA_PROVENANCE_GATE_PENDING`

The repository contains the RC provenance controls, but this checkout cannot
prove the claimed v0.2.0 release baseline or that the observed data originates
from an external operational workspace.

## V0.2.0 release baseline

The requested tag `v0.2.0` is absent from this checkout and no Git remote is
configured. Therefore neither the claimed tag commit nor the claimed released
installer checksum can be independently verified here.

| Evidence | Local result |
| --- | --- |
| `v0.2.0` tag | NOT AVAILABLE |
| Release installer artifact | NOT AVAILABLE |
| Immutable release confirmation | NO — evidence unavailable |

No tag was moved, created, or altered. No release was changed.

## Synthetic hardening and golden acceptance

- Targeted provenance tests: `3 passed`.
- Golden: `18 logical documents / 29 pages / 0 errors` — PASS.
- The full `pytest -q` suite was started twice but did not complete and both
  test processes were stopped. It must be rerun to a completed result before a
  release claim.

## Phase 12B rehearsal audit

`verify_phase12b_real_gate.py` was not present in the baseline checkout. The
existing Phase 10 probe reads `<REPOSITORY_WORKSPACE_ROOT>/input`; it uses no
`deterministic_blank_pdf()` or `PdfWriter` itself, but tests contain `PdfWriter`
fixtures. No evidence found establishes the input data's external operational
origin, so it is not classified as a true real-data pilot.

## Current workspace inventory (not true-real-data evidence)

```text
dataset_origin = unverified_workspace_inside_repository
dataset_inside_git_repo = true
dataset_generated_by_test_fixture = false
dataset_generated_by_golden_fixture = false
folder_count = 30
pdf_count = 223
page_count = 6905
total_bytes = 1874207889
```

The aggregate hash evidence is retained only in the local command output. Do
not publish per-file hashes or names.

## Windows RC candidate

The build contract now uses `0.2.1-rc1`, emits the distinct installer filename
`HosoManager-Setup-v0.2.1-rc1.exe`, and bundles `build_provenance.json` created
from the exact clean Git HEAD. `/health` exposes only version, build SHA, and
build timestamp. Candidate artifact hash and Windows install/runtime evidence
remain pending the post-commit build.

## Logging privacy

The Manager's runtime code has no application logger that emits extracted text
or PDF payloads; FastAPI/Uvicorn access logs contain route paths and status.
Historical files under the ignored `logs/` directory contain PII in directory
names, so historical logging privacy is **NOT PASS**. Do not publish or reuse
those logs as Phase 12C evidence; a separately authorized retention/redaction
operation is required.

## Required next action

Provide an external operational data root outside this checkout, run the
anonymized inventory first, then dry-run, apply outside the source root, source
integrity check, and idempotent rerun. Separately provide a clone/remote that
contains the immutable `v0.2.0` tag and released artifact evidence. Only then
can the remaining gates be evaluated.