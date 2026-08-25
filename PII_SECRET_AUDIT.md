# PII and secret audit

Date: 2026-08-25 (Asia/Saigon)

## Scope

The target repository was scanned before Git initialization for real PDFs,
SQLite/runtime files, logs, local configuration, credentials, API keys, private
keys, absolute data paths in production code, CCCD-like values, and names copied
from the real corpus.

## Result

- Real PDF tracked candidate: **NO**
- Production SQLite/runtime DB candidate: **NO**
- Runtime logs candidate: **NO**
- `.env`/credential/token/private-key candidate: **NO**
- Real corpus manifest/ledger candidate: **NO**
- Personal names copied from the real corpus: **NO**
- Production source code hard-coded to the laptop or desktop data path: **NO**

The Golden assets use the label `Synthetic Person` and generate blank PDFs plus
temporary analysis in the test workspace. Any CCCD-shaped values in manager unit
fixtures are deterministic synthetic test values, not corpus records.

`config.local.json` contains the laptop data root for local execution and is
ignored by Git. It is not part of the commit or push candidate.
