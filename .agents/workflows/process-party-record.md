---
name: process-party-record
description: Xử lý một thư mục hồ sơ đảng viên từ đầu tới dry-run summary. Không tự apply.
agent: document-processor
---

# /process-party-record

Đầu vào: tên thư mục hồ sơ, ví dụ `input/<person-folder>`
(hoặc chỉ cần nói *"Xử lý input/<person-folder>"*).

Workflow này **luôn dừng ở dry-run**. Không bao giờ tự `apply`.

---

## Bước 1 — Nạp luật

Đọc `.agents/rules/party-record-digitization.md` và `document_types.json`.
Xác nhận bạn đang ở **RUNTIME MODE**: không sửa code, không sửa taxonomy, không sửa test.

## Bước 2 — Incremental status + Inventory + hash

```
python -m app.cli status "<thư mục>"
```

Chỉ đọc SHA-256 + `state/processing_state.db` (không mở nội dung PDF). Kết quả
chia file thành `NEW`/`STALE_ANALYSIS` (cần Vision) · `ANALYZED_PENDING_APPLY`/
`REVIEW_REQUIRED` (đã có cache, SKIP Vision) · `PROCESSED` (SKIP hẳn) ·
`FAILED`/`INTERRUPTED` (SKIP trừ khi retry) · `DUPLICATE_SOURCE` (SKIP vĩnh viễn).

```
python -m app.cli inventory "<thư mục>"
```

Ghi lại: số PDF, số trang từng file, SHA-256. Nếu thư mục rỗng hoặc PDF hỏng → dừng, báo lỗi.
Nếu `status` báo `STATE_OUTPUT_MISMATCH` → báo người vận hành, dừng, không tự sửa.

## Bước 3 — Skip nguồn cũ, tái sử dụng cache hợp lệ

Nguồn `PROCESSED` → bỏ qua hoàn toàn. Nguồn `ANALYZED_PENDING_APPLY`/
`REVIEW_REQUIRED` với fingerprint còn khớp → dùng lại phân tích đã có, KHÔNG
gọi Vision. Chỉ nguồn `NEW`/`STALE_ANALYSIS` (hoặc retry rõ ràng) mới sang Bước 4.

## Bước 4 — Đọc tài liệu (chỉ NEW/STALE)

Với **mỗi** PDF `NEW`/`STALE_ANALYSIS`, xem **mọi** trang (số trang phải khớp
inventory ở bước 2). Với mỗi trang xác định: `page_role`, tiêu đề ngắn, ngày
(nếu đọc chắc chắn), mở đầu hay tiếp nối, hướng ghép nếu là bìa/mặt sau, ứng
viên `type_id` + confidence.

Nếu không có file nào cần Vision (mọi thứ đã cache/processed): bỏ qua Bước 4,
chạy thẳng Bước 6 (dry-run vẫn nên chạy để xác nhận, sẽ báo "không có nguồn mới").

## Bước 5 — Sinh analysis JSON

Ghi `analysis/<TEN_NGUOI>/<ten_pdf>.json` cho từng PDF, đúng schema trong
`.agents/agents/document-processor/agent.md`.

Tự kiểm trước khi ghi:
- `pages[]` phủ đủ `1..page_count`, không lặp;
- `documents[]` phủ đủ `1..page_count`, không chồng lấn, không rỗng;
- `type_id` ∈ `01`–`104` ∪ `UNKNOWN`;
- không có khóa tên file / số thứ tự / trạng thái;
- ngày `yyyy-mm-dd` hoặc `null`; chỉ đọc được năm → `null`.

## Bước 6 — Merge toàn hồ sơ + global naming plan + Validate + dry-run

```
python -m app.cli process "<thư mục>"
```

Validator local từ chối JSON sai hợp đồng — sai thì **sửa JSON, KHÔNG sửa
code**. Khi hợp lệ, kết quả được đóng băng vào state DB. Naming engine tự nhìn
**toàn bộ** tài liệu cùng `type_id` đã biết của người này (không chỉ lượt này)
để tính số thứ tự — dry-run cho biết trước cả những file cũ có bị đổi tên hay
không, không cần đoán.

## Bước 7 — QC

Đọc khối `--- QC ---` trong output. Các check liên quan: `page_coverage`,
`page_overlap`, `status_coverage`, `document_count_sane` (cho nguồn vừa phân
tích), và khi apply còn thêm `source_unchanged`, `outputs_readable`,
`global_naming_plan`.

Có check FAIL → trạng thái `BLOCKED_QC`, dừng, báo người vận hành. Không tự vá.

## Bước 7b — Trình bày summary

Báo đúng các mục sau (theo đúng tinh thần ví dụ dưới, không cần dump log kỹ thuật
trừ khi có lỗi):

```
HỒ SƠ: <TEN_NGUOI>

PDF hiện có: <n>
Đã xử lý trước: <k> -> SKIP
Mới bổ sung: <m>
Đang chờ review: <r>
Lỗi cũ: <f>

Đã phân tích mới:
- AUTO: <a>
- REVIEW: <b>

Không xử lý lại <k> PDF cũ.
```

Kèm chi tiết khi cần: **Segmentation** (page range từng tài liệu mới, tiêu đề ngắn) ·
**Classification** (`type_id` · confidence · AUTO/REVIEW) · **REVIEW** (lý do từng ca) ·
**QC** (coverage · overlap · missing · duplicate · filename collision · source mutation) ·
**Trạng thái cuối**: `DRY_RUN_PASS` | `REVIEW_REQUIRED` | `BLOCKED_QC` | `BLOCKED_RUNTIME`.

## Bước 8 — Nếu có REVIEW_PENDING, nêu rõ (không tự chốt)

Nếu manifest có logical document `needs_review: true`, liệt kê:

```
python -m app.cli review-list "<thư mục>"
```

Không tự chọn `type_id`/`subtype`/supporting/duplicate/ngày thay người vận
hành. Chờ họ chốt bằng một trong:

```
python -m app.cli resolve-review <logical_document_id> --type-id <mã> [--subtype <mã>] [--date yyyy-mm-dd] [--date-precision DAY|MONTH|YEAR]
python -m app.cli resolve-review <logical_document_id> --supporting
python -m app.cli resolve-review <logical_document_id> --duplicate-of <logical_document_id gốc>
```

(Xem `.agents/rules/party-record-digitization.md` mục 9 — chính sách type 87
subtype / SUPPORTING_DOCUMENT / DUPLICATE / partial date precision.)

## Bước 9 — Dừng

Kết thúc tại đây. Nói rõ với người vận hành:

> Muốn ghi file thật, trả lời `apply`.

Chỉ khi người vận hành trả lời đúng chữ `apply` mới chạy:

```
python -m app.cli process "<thư mục>" --apply
```

Apply xử lý cả nguồn `ANALYZED_PENDING_APPLY`/`REVIEW_REQUIRED` đã cache (không
gọi lại Vision) và có thể đổi tên file cũ nếu global naming yêu cầu (đã báo
trước ở Bước 6) — rồi báo lại `output/`, `review/`, manifest. Nguồn chỉ thành
`PROCESSED` khi hết review treo.
