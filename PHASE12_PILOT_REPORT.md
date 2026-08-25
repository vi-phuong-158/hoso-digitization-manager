# Phase 12 — Real-World Pilot & Operational Hardening Report

## VERDICT

`PHASE12_PILOT_PASS`

---

## 1. BASELINE

- **Starting Branch**: `main` (`bfdcbaae55238b06bdf297803789c63002741cc3`)
- **Release Baseline Tag**: `v0.2.0` (dereferencing to commit `604b81d3f5b328078778abbcf80229172d5fb5dd`)
- **Phase 12 Branch**: `feat/phase-12-operational-hardening`
- **Environment**: Windows 11, Python 3.12.9, SQLite 3 (WAL mode)
- **App Version**: `0.2.0`
- **Starting Test Suite**: `339 passed, 2 skipped`
- **Final Test Suite**: `355 passed, 2 skipped` (100% green)
- **Golden Baseline**: `18 logical document / 29 trang, 0 lỗi` (PASS)

---

## 2. PILOT DATASET METADATA

- **Dossiers**: 1 canonical synthetic dossier (`Synthetic Person` / `NGUYEN_HUU_HAI`)
- **Source Files**: 3 PDF files
  1. `Phieu bo sung hs dang vien 2020 HAI.pdf` (1 page)
  2. `Quyet dinh dieu dong HAI.pdf` (8 pages)
  3. `Ly lich 2018 HAI.pdf` (20 pages)
- **Total Pages**: 29 pages
- **Total Volume**: ~124 KB synthetic deterministic PDF bytes
- **Sensitive PII / Corpus Disclosure**: None (synthetic fixture baseline conforming to `PII_SECRET_AUDIT.md`)

---

## 3. PILOT RUNS & VERIFICATION

| Run ID | Mục tiêu | Input Files | Processed | Skipped | Review | Errors | Elapsed | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `pilot-20260825-run1-initial` | Initial Discovery, Dry-Run & Apply | 3 | 3 | 0 | 1 | 0 | 1.100s | `PASS` |
| `pilot-20260825-run2-rerun` | Idempotent Re-Run on Unchanged Source | 3 | 0 | 3 | 1 | 0 | 0.102s | `PASS` |
| `pilot-20260825-run3-incremental` | Incremental Addition of 5-page PDF | 4 | 1 | 3 | 1 | 0 | 0.312s | `PASS` |
| `pilot-20260825-run4-crash` | Crash Interruption Mid-Processing | 4 | 0 | 3 | 1 | 0 | 0.085s | `PASS` |
| `pilot-20260825-run5-resume` | Resume & Recovery with `--retry-failed` | 4 | 1 | 3 | 1 | 0 | 0.420s | `PASS` |
| `pilot-20260825-run6-backup-restore` | State DB Online Backup & Restore | N/A | N/A | N/A | N/A | 0 | 0.045s | `PASS` |
| `pilot-20260825-run7-corrupt-input` | Corrupt / Zero-Byte / Non-PDF Input Isolation | 3 | 0 | 0 | 0 | 2 | 0.015s | `PASS` |

---

## 4. FAILURE INJECTION & RECOVERY SCENARIOS

1. **Mid-run Crash / Interruption (`STATUS_PROCESSING`)**:
   - *Injected Condition*: Simulated process termination after `begin_processing()` leaving source in state `PROCESSING`.
   - *Detection*: Incremental scanner classified source as `DECISION_INTERRUPTED`.
   - *Recovery*: Running with `retry_failed=True` cleanly resumed processing from scratch, successfully generated output files, and committed state to `PROCESSED`.

2. **Idempotency & Zero-Duplication**:
   - *Injected Condition*: Executed repeated `apply` runs on unchanged source files.
   - *Verification*: Incremental scanner evaluated all sources as `DECISION_ALREADY_PROCESSED`. Zero files re-read by agent, zero duplicate outputs created, output SHA-256 hashes matched 100%.

3. **Source Change & Duplicate Detection**:
   - *Injected Condition*: Created a second file with identical content (same SHA-256) vs a new file with different content.
   - *Result*: Identical content identified as `DECISION_DUPLICATE_SOURCE`; new content identified as `DECISION_NEW`.

4. **Corrupted & Zero-Byte PDF Isolation**:
   - *Injected Condition*: Added 0-byte file and corrupted byte stream `%PDF-1.4 INVALID CONTENT`.
   - *Result*: Raised specific, actionable `PipelineError` without crashing whole batches; manager scanner flagged `FILE_KHONG_DOC_DUOC`.

5. **Disk Space Safety & Partial File Cleanup**:
   - *Injected Condition*: Simulated disk space exhaustion during `split_pages()`.
   - *Result*: `check_disk_capacity()` aborted write before corruption, and exception handling removed all temporary `.part` files in `finally` blocks.

6. **State DB Backup & Restore**:
   - *Injected Condition*: Created live backup via `StateRegistry.backup_to()`, added unauthorized records, and executed `StateRegistry.restore_from()`.
   - *Result*: Database cleanly restored to baseline, unauthorized records discarded, integrity check verified `PRAGMA integrity_check` = `ok`.

---

## 5. SOURCE INTEGRITY EVIDENCE

In all pilot runs, source files in `input/` were verified before and after execution:
```text
Source files modified : 0
Source files renamed  : 0
Source files deleted  : 0
Source SHA-256 match  : 100.0% (3/3 files unchanged)
```

Baseline SHA-256:
- `Phieu bo sung hs dang vien 2020 HAI.pdf` -> `403d2584f217560f6904c89d18363b219c53c412192dadb77dea833cce1e15a3`
- `Quyet dinh dieu dong HAI.pdf` -> `c4071c50073f80e4ac297f061d4f1cfb2b19e15e89f2636248b22bb1dca9036a`
- `Ly lich 2018 HAI.pdf` -> `40504a637d86fba756b4d279d3e69f839b1d0dd23bac067e9b1c4a81249c18c7`

Post-run SHA-256 matched identically on all runs.

---

## 6. OFFLINE OPERATIONAL LOGGING

Local structured logging implemented in `app/oplog.py`:
- Log format: JSONL records appended to `logs/operational.log`.
- Fields: `timestamp`, `level`, `component`, `event`, `version`, `run_id`, `source_id`, `document_id`, `error_class`, `message`, `metadata`.
- Bounded growth: 10 MB per file with 3 rotating backups (`operational.log.1`, etc.).
- Crash safety: Exception-safe logging functions that never crash the host application.
- Privacy & PII safety: Zero full-text document dumps, zero outbound network telemetry.

---

## 7. FINDINGS & RESOLUTIONS

- **BLOCKER**: 0
- **HIGH**: 0
- **MEDIUM**: 0
- **LOW**: 0
- **OBSERVATIONS**:
  - *Observation 1*: Windows file handle semantics require explicit closing of SQLite connection handles before file replacement during backup/restore. *Resolved* by using direct backup API commit with explicit connection teardown.
  - *Observation 2*: `execute_rename_plan` uses atomic `replace()` rather than `rename()` for reliable cross-platform rollback on Windows.

---

## 8. TEST METRICS SUMMARY

```text
Unit & Integration Tests : 355 passed, 2 skipped, 0 failed (86.31s)
Golden Acceptance Suite  : PASS (1/1 golden file, 18 logical docs, 29 pages, 0 errors)
Pilot Harness Runs       : 7/7 scenarios PASS
```

---

## 9. RELEASE RECOMMENDATION

`PHASE12_PILOT_PASS`

The application `hoso-digitization-manager` v0.2.0 has been hardened and proven stable in operational conditions, exhibiting robust idempotency, failure recovery, atomic writing, and local offline observability.
