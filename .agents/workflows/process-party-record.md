---
name: process-party-record
description: Xử lý một thư mục hồ sơ đảng viên từ đầu tới dry-run summary. Không tự apply.
agent: document-processor
---

# /process-party-record

Đầu vào: tên thư mục hồ sơ, ví dụ `input/Nguyễn Hữu Hải`
(hoặc chỉ cần nói *"Xử lý input/Nguyễn Hữu Hải"*).

Workflow này **luôn dừng ở dry-run**. Không bao giờ tự `apply`.

---

## Bước 1 — Nạp luật

Đọc `.agents/rules/party-record-digitization.md` và `document_types.json`.
Xác nhận bạn đang ở **RUNTIME MODE**: không sửa code, không sửa taxonomy, không sửa test.

## Bước 2 — Incremental status + Inventory

```
python -m app.cli status "<thư mục>"
```

Chỉ đọc SHA-256 + `state/processing_state.db` (không mở nội dung PDF). Kết quả
chia file thành `NEW` / `ALREADY_PROCESSED` (SKIP) / `REVIEW_PENDING` (SKIP) /
`FAILED_PREVIOUSLY` (SKIP) / `INTERRUPTED` (SKIP) / `DUPLICATE_SOURCE` (SKIP).

```
python -m app.cli inventory "<thư mục>"
```

Ghi lại: số PDF, số trang từng file, SHA-256. Nếu thư mục rỗng hoặc PDF hỏng → dừng, báo lỗi.
Nếu `status` báo `STATE_OUTPUT_MISMATCH` → báo người vận hành, dừng, không tự sửa.

## Bước 3 — Đọc tài liệu (CHỈ các file NEW)

Với **mỗi** PDF ở trạng thái `NEW` (bỏ qua mọi file khác — đó chính là điểm của
incremental processing: không đọc lại việc đã làm), xem **mọi** trang (số trang
phải khớp inventory ở bước 2). Với mỗi trang xác định: `page_role`, tiêu đề
ngắn, ngày (nếu đọc chắc chắn), mở đầu hay tiếp nối, hướng ghép nếu là bìa/mặt
sau, ứng viên `type_id` + confidence.

Nếu `status` không có file `NEW` nào (toàn bộ `ALREADY_PROCESSED`): bỏ qua Bước 3-4,
chạy thẳng Bước 5 (dry-run vẫn nên chạy để xác nhận, sẽ báo "không có nguồn mới").

## Bước 4 — Sinh analysis JSON

Ghi `analysis/<TEN_NGUOI>/<ten_pdf>.json` cho từng PDF, đúng schema trong
`.agents/agents/document-processor/agent.md`.

Tự kiểm trước khi ghi:
- `pages[]` phủ đủ `1..page_count`, không lặp;
- `documents[]` phủ đủ `1..page_count`, không chồng lấn, không rỗng;
- `type_id` ∈ `01`–`104` ∪ `UNKNOWN`;
- không có khóa tên file / số thứ tự / trạng thái;
- ngày `yyyy-mm-dd` hoặc `null`; chỉ đọc được năm → `null`.

## Bước 5 — Validate + dry-run

```
python -m app.cli process "<thư mục>"
```

Validator local sẽ từ chối JSON sai hợp đồng. Nếu bị từ chối:
**sửa JSON của bạn, KHÔNG sửa code.**

## Bước 6 — QC

Đọc khối `--- QC ---` trong output. Mọi check phải PASS:
`page_coverage`, `page_overlap`, `source_unchanged`, `status_coverage`,
`naming_from_catalog`, `filename_collision`, `document_count_sane`.

Có check FAIL → trạng thái `BLOCKED_QC`, dừng, báo người vận hành. Không tự vá.

## Bước 7 — Trình bày summary

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

## Bước 8 — Dừng

Kết thúc tại đây. Nói rõ với người vận hành:

> Muốn ghi file thật, trả lời `apply`.

Chỉ khi người vận hành trả lời đúng chữ `apply` mới chạy:

```
python -m app.cli process "<thư mục>" --apply
```

rồi báo lại `output/`, `review/`, manifest.
