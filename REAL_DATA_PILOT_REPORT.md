# Phase 10 — Real Data Pilot & Hardening

Captured: 2026-08-24 (Asia/Saigon)

## Verdict

`DIGITIZATION_MANAGER_REAL_DATA_PILOT_PARTIAL`

The implementation is locally testable and safe for a controlled pilot, but the requested final `DIGITIZATION_MANAGER_REAL_DATA_PILOT_PASS` is not claimed: the real corpus contains only 2 hồ sơ, so the required manual spot-check of at least 20 real hồ sơ cannot be satisfied without fabricating data.

## Real corpus evidence

- Inventory: 2 person folders, 4 source PDFs, 50 source pages.
- Pilot scan: `SUCCESS`, 2 cases created, 4 source documents inventoried, 0 scanner errors.
- Taxonomy: 104 active catalog items, sourced from existing `document_types.json`.
- Existing pipeline integration: 18 logical-document entries loaded read-only from existing manifest artifacts; no manifest/ledger/output source was modified.
- UI/API smoke with temporary DB: dashboard, cases list/search JSON, case details, settings, scan runs and metadata backup all returned HTTP 200.
- All 2 real cases were inspected through filesystem metadata, Manager detail JSON and pipeline evidence. No critical source-to-case mismatch was found in the available corpus.
- 20-case gate: `NOT FEASIBLE` — only 2 real cases exist in `input/`.

## Source immutability

Before/after snapshots covered every file under `input/`, including size, mtime and SHA-256 for all 4 PDFs. Result: `source_unchanged: true`.

Observed SHA-256 values remained:

- `af2752447a0006d4a23daf34f09910c7d08d2f95b5fae5e4073e64eff3959e21`
- `a179d62465161085e11e2d5df8481d7520f7c11f5a62c09ba74506f987367d35`
- `6642a39763732646a9a933ff84ca7c477247aad40d65aafebc0cee1b5c2824b5`
- `caf017dfe848c8e4f4edc81462eee6afb2ba329545ea7be3f317bc2bef10b673`

No source PDF was renamed, moved, deleted, overwritten, uploaded or rasterized.

## Hardening and validation gates

| Gate | Result |
|---|---|
| State persistence across restart | PASS — fixture covers override, completion, restart, change-after-completion warning |
| Incremental add/delete/reappear/modify | PASS — existing scanner tests plus Phase 10 fixture |
| Backup/restore | PASS — SQLite online backup, metadata-only; restored DB integrity `ok` |
| DB integrity/WAL | PASS — `PRAGMA integrity_check = ok`; WAL enabled |
| Offline/no AI/cloud dependency | PASS — runtime no-network tests and offline health response |
| Localhost/path traversal | PASS — localhost validation and ID/canonical-root checks; traversal fixture safe-fails |
| Scale benchmark | PASS — 500 cases / 5,000 PDFs: first 16.20s/5,000 hashes; unchanged 11.99s/0 hashes; one changed 12.07s/1 hash |
| Golden acceptance | PASS — 18 logical documents / 29 pages / 0 errors |
| Regression | PASS — `172 passed in 18.89s` |
| Windows onedir build | PASS — `dist/HosoManager/HosoManager.exe`, 9,899,844 bytes; single-launch `/health` 200 |
| Double-launch packaged observation | PARTIAL — lock implementation and unit coverage pass; direct hidden-process orchestration was not deterministic on this Windows desktop runner |
| Git provenance/checkpoint commits | BLOCKED — no `.git` metadata exists in workspace or nearby parent directories |

## Changed artifacts

- Added SQLite metadata backup operation and `GET /backup`.
- Integrated existing manifest logical documents into checklist/status evidence.
- Added Windows single-instance lock behavior.
- Added Phase 10 hardening tests and temporary probe/benchmark helpers.
- Rebuilt Windows onedir package.
- No real input PDF/folder content changed.

## Reproduction commands

```powershell
python tools/phase10_real_probe.py
python tools/phase10_scale_bench.py
python -m pytest tests -q
python -m app.cli test-golden --provider agent
powershell -ExecutionPolicy Bypass -File .\build_manager.ps1
```

## Pilot decision

Proceed only as a controlled local pilot with the existing 2-case corpus and human review of warnings. To reach the requested PASS verdict, add at least 18 more real hồ sơ, rerun the stratified 20-case manual review, and repeat the package launch/restart smoke on the target pilot machine.
