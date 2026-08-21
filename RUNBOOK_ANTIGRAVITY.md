# RUNBOOK — Antigravity Runtime Agent

> Runtime chính thức. Không API key, không gọi model qua mạng.
> Agent trong Antigravity đọc PDF; code local làm phần deterministic.
> Nguyên tắc gốc nằm ở `AGENTS.md` — không được sửa.

## Quy trình

1. Scan hồ sơ. Hồ sơ được **bổ sung liên tục theo thời gian** — cứ thêm PDF mới
   vào đúng thư mục người, không cần dọn PDF cũ.
2. Đặt các PDF (mới hoặc cũ trộn lẫn) vào `input/<TEN_NGUOI>/`.
3. Yêu cầu Antigravity Agent xử lý (`/process-party-record`, hoặc chỉ cần nói
   *"Xử lý input/<TEN_NGUOI>"*).
4. Agent tự chạy `status` trước — PDF đã `PROCESSED` được **SKIP**, không đọc lại.
5. Agent chạy dry-run cho các PDF `NEW`.
6. Xem AUTO / REVIEW.
7. Nếu đồng ý → trả lời `apply`.
8. Kiểm tra `output/`, `review/`, manifest.

## Lệnh

```bash
python -m app.cli status "input/<TEN_NGUOI>"
```

```bash
python -m app.cli process "input/<TEN_NGUOI>"
```

```bash
python -m app.cli process "input/<TEN_NGUOI>" --apply
```

| Lệnh | Ý nghĩa |
|------|---------|
| `status "<thư mục>"` | Chỉ đọc: đếm NEW/PROCESSED/REVIEW_REQUIRED/FAILED/DUPLICATE_SOURCE. Không mở PDF. |
| `process "<thư mục>"` | Dry-run (mặc định). **Chỉ xử lý nguồn NEW**, SKIP nguồn đã PROCESSED. Không ghi `output/`, `review/`. |
| `process "<thư mục>" --apply` | Ghi thật. Chỉ chạy khi QC đạt. Nguồn đã PROCESSED vẫn SKIP. |
| `process "<thư mục>" --retry-review` | Đọc lại các nguồn đang REVIEW_REQUIRED (dry-run). |
| `process "<thư mục>" --retry-failed` | Đọc lại các nguồn FAILED/INTERRUPTED. |
| `process "<thư mục>" --no-state` | Tắt incremental — xử lý lại TOÀN BỘ nguồn như trước khi có state registry. |
| `process "<thư mục>" --json` | In manifest JSON thay vì summary. |
| `inventory "<thư mục>"` | Liệt kê file nguồn + số trang + SHA-256 (không liên quan state). |
| `import-state "<thư mục>"` | Nạp lại state PROCESSED từ manifest/output đã có sẵn (hồ sơ xử lý trước khi có state registry — xem mục "Migration" dưới). |
| `state-export [--out file.json]` | Xuất toàn bộ `state/processing_state.db` ra JSON để backup/kiểm tra. |
| `test-golden` | Golden acceptance (mặc định provider `fixture`). |
| `test-golden --provider agent` | Golden acceptance trên chính output của Agent. |
| `providers` | Liệt kê provider và catalog. |

Provider mặc định của `process` là `agent`. Không có cờ mạng, không có API key.

## Incremental processing (không đọc lại PDF đã xử lý)

Mỗi PDF được nhận diện bằng **SHA-256 nội dung**, không phải tên file:

- Đổi tên file mà nội dung giữ nguyên (hoặc di chuyển) → vẫn nhận ra đã xử lý, **không đọc lại**.
- Cùng tên nhưng nội dung bị thay (hash đổi) → coi là nguồn **mới**, phải xử lý.
- Hai file khác tên, cùng nội dung (hash trùng) → chỉ file đầu tiên (theo alphabet) được xử lý,
  file còn lại là `DUPLICATE_SOURCE`, không bao giờ tạo output.
- Dry-run **không bao giờ** đánh dấu PROCESSED — chỉ apply thành công + QC PASS mới đánh dấu.
- Apply thất bại (QC fail hoặc xung đột file đích) → nguồn đó thành `FAILED`, **không tự retry**;
  cần `--retry-failed` rõ ràng ở lần sau.
- Tiến trình bị dừng đột ngột giữa chừng (crash, đóng Antigravity) → nguồn đó hiện `INTERRUPTED`
  ở lần chạy sau, cũng cần `--retry-failed` mới xử lý lại — không tự coi là PROCESSED.

**Giới hạn đã biết:** đánh số `.1/.2/...` cho nhiều tài liệu cùng loại chỉ tính trong
PHẠM VI MỘT LƯỢT CHẠY. Nếu lượt sau thêm một tài liệu CÙNG LOẠI với tài liệu đã có
từ lượt trước, tên file có thể trùng với file đã ghi — pipeline sẽ **CHẶN AN TOÀN**
(`BLOCKED_RUNTIME`, không ghi đè âm thầm) thay vì tự đánh số tiếp. Xem `LIMITATIONS.md`.

### Migration cho hồ sơ đã xử lý trước khi có state registry

Hồ sơ đã `apply` thành công (có `output/<người>/_manifest.json` hợp lệ) trước khi
tính năng incremental tồn tại (ví dụ bộ HAI) sẽ hiện là `NEW` nếu không migration
trước — vì registry còn trống. Chạy một lần:

```bash
python -m app.cli import-state "input/<TEN_NGUOI>"
```

Lệnh này CHỈ đánh `PROCESSED` khi bằng chứng đầy đủ (ledger khớp SHA-256/số trang,
mọi file đích thực sự tồn tại trên đĩa). Thiếu bằng chứng → `STATE_IMPORT_REVIEW_REQUIRED`,
không đụng registry, không suy đoán.

## Agent phải làm gì trước khi chạy `process`

Với **mỗi** PDF, Agent đọc **mọi** trang rồi ghi một file:

```
analysis/<TEN_NGUOI>/<ten_pdf_khong_duoi>.json
```

Schema đầy đủ: `.agents/agents/document-processor/agent.md`.
Validator local sẽ từ chối JSON sai hợp đồng — khi đó **sửa JSON, không sửa code**.

Thiếu file này thì pipeline dừng với thông báo rõ ràng; không có chuyện đoán bừa.

## Đọc kết quả

- `output/<TEN_NGUOI>/` — tài liệu AUTO, tên chuẩn theo `document_types.json`.
- `output/<TEN_NGUOI>/_manifest.json` — manifest chính thức + sổ ghi để apply lại không tạo bản trùng.
- `review/<TEN_NGUOI>/` — tài liệu cần người quyết định. Tiền tố `_REVIEW.`, **không** phải tên chuẩn.
- `logs/<TEN_NGUOI>/manifest.dryrun.json`, `manifest.apply.json` — nhật ký từng lần chạy.

## Lý do REVIEW

| Mã | Nghĩa | Cần làm gì |
|----|-------|------------|
| `LOW_CONFIDENCE` | Agent không đủ chắc (< 0.80) | Tự xác định loại |
| `AGENT_FLAGGED_REVIEW` | Chính Agent xin REVIEW | Đọc `review_reason` trong manifest |
| `SECOND_PASS_STILL_LOW` / `SECOND_PASS_DISAGREES` | Hai lượt đọc không thống nhất | Quyết định thủ công |
| `TYPE_UNKNOWN` | Không khớp loại nào trong 104 loại | Quyết định thủ công |
| `CONFUSABLE_TYPE_NARROW_MARGIN` | Cặp dễ nhầm (vd 70 vs 86), cách biệt hẹp | Chọn loại đúng |
| `SEGMENTATION_AMBIGUITY` | Không chắc bìa/mặt sau thuộc tài liệu nào | Xác định ranh giới trang |
| `AGENT_SEGMENTATION_MISMATCH` | Agent gom trang khác segmenter local | Xác định lại ranh giới trang |
| `ORDERING_MISSING_RELIABLE_DATE` | Nhiều tài liệu cùng loại, thiếu ngày đáng tin | Chốt thứ tự `.1/.2/...` |
| `ORDERING_DUPLICATE_DATE` | Nhiều tài liệu cùng loại trùng ngày | Chốt thứ tự `.1/.2/...` |

## Apply lại nhiều lần

- File đích đã đúng: bỏ qua, không ghi lại, không tạo bản trùng.
- File đích tồn tại nhưng khác nội dung: **dừng toàn bộ, không ghi file nào**, báo `BLOCKED_RUNTIME`.
- Ghi đè có chủ đích chỉ khi người vận hành yêu cầu rõ và dùng `--force`.

## Runtime Agent bị cấm

- sửa `AGENTS.md`;
- sửa `document_types.json`;
- sửa `test_cases/*`, `fixtures/*`;
- sửa source code trong `app/`, sửa tests;
- tự thay threshold;
- tự tạo taxonomy mới;
- tự đặt tên file / đánh số `.1/.2`;
- sửa/xóa/di chuyển input;
- gửi tài liệu ra dịch vụ ngoài luồng đã được người vận hành phê duyệt.

Gặp ca lạ → `REVIEW_REQUIRED`, ghi nhận cho DEV mode. Không tự vá.

## Trạng thái kết thúc

Chỉ dùng:
- `DRY_RUN_PASS`
- `APPLY_PASS`
- `REVIEW_REQUIRED`
- `BLOCKED_QC`
- `BLOCKED_RUNTIME`

Không dùng từ "hoàn tất" nếu còn file chưa được accounted for.

CLI in đúng một trong các trạng thái này ở dòng cuối. Exit code: `0` cho
`DRY_RUN_PASS`/`APPLY_PASS`/`REVIEW_REQUIRED`, `2` cho `BLOCKED_*`, `3` cho lỗi pipeline.

## Kiểm tra hệ thống còn nguyên vẹn

```bash
python -m pytest tests -q
```

```bash
python -m app.cli test-golden --provider agent
```

Cả hai phải xanh. Nếu đỏ: **DỪNG**, báo người vận hành, không tự sửa code.
