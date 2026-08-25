---
name: batch-party-record
description: Xử lý toàn bộ input/ bằng batch orchestrator; chỉ Vision NEW/STALE và chỉ auto-apply hồ sơ AUTO_SAFE.
agent: document-processor
---

# /batch-party-record

Đầu vào mặc định: `input/`.

Khi người vận hành nói **"Xử lý toàn bộ hồ sơ trong input"**, dùng workflow
này. Không yêu cầu họ chạy lệnh theo từng người và không trình bày các bước nội
bộ trừ khi lỗi/debug.

1. Đọc `.agents/rules/party-record-digitization.md` và `document_types.json`.
2. Chạy:

   ```bash
   python -m app.cli batch-run input --dry-run --json
   ```

3. Với từng `vision_required_sources` trong report, đọc đủ mọi trang của đúng
   source đó và ghi `analysis/<người>/<pdf>.json` theo contract của agent.
   Không đọc Vision bất kỳ source cache/processed/retired nào.
4. Chạy:

   ```bash
   python -m app.cli batch-run input
   ```

5. Trả đúng batch report cuối: người `COMPLETED`/`ALREADY_COMPLETE`, người
   `NEEDS_REVIEW`, source `MISSING_SOURCE`, `RETIRED`, và lỗi kỹ thuật. Chỉ hỏi
   operator về các item NEEDS_HUMAN. Không tự resolve review hay retire source.

`batch-run` đã tự tách transaction boundary per-person: một hồ sơ lỗi không
dừng hồ sơ khác. Chỉ `BATCH_SYSTEM_BLOCKED` mới là lỗi global cần dừng toàn bộ.
