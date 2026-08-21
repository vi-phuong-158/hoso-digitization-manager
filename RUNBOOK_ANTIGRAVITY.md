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
| `status "<thư mục>"` | Chỉ đọc: đếm NEW/STALE_ANALYSIS/ANALYZED_PENDING_APPLY/REVIEW_REQUIRED/PROCESSED/FAILED/DUPLICATE_SOURCE. Không mở PDF. |
| `process "<thư mục>"` | Dry-run (mặc định). **Chỉ gọi Vision cho nguồn NEW/STALE**, tái dùng cache cho phần còn lại. Không ghi `output/`, `review/`. |
| `process "<thư mục>" --apply` | Ghi thật. Chỉ chạy khi QC đạt. Nguồn PROCESSED vẫn SKIP hoàn toàn. |
| `process "<thư mục>" --retry-review` | Đọc lại (Vision) các nguồn đang REVIEW_REQUIRED thay vì dùng cache. |
| `process "<thư mục>" --retry-failed` | Xử lý lại các nguồn FAILED/INTERRUPTED. |
| `process "<thư mục>" --no-state` | Tắt incremental — xử lý lại TOÀN BỘ nguồn như trước khi có state registry. |
| `process "<thư mục>" --json` | In manifest JSON thay vì summary. |
| `review-list "<thư mục>"` | Liệt kê logical document đang REVIEW_PENDING (loại, ngày, lý do). |
| `resolve-review <id> --type-id <mã> [--subtype <mã>] [--date yyyy-mm-dd] [--date-precision DAY\|MONTH\|YEAR]` | Chốt TAXONOMY (vd type 87 + subtype quyết định nhân sự). KHÔNG đọc lại PDF. |
| `resolve-review <id> --supporting` | Chốt là `SUPPORTING_DOCUMENT` (ngoài danh mục 104 loại). |
| `resolve-review <id> --duplicate-of <id gốc>` | Chốt là `DUPLICATE` của một logical document đã biết — không tạo output riêng. |
| `reconcile "<thư mục>"` | Đối chiếu state DB với file thật trên đĩa; báo STATE_OUTPUT_MISMATCH/orphan, không tự sửa. |
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

**Hai trục tách biệt.** "AI đã đọc xong" (`ANALYZED_PENDING_APPLY`/`REVIEW_REQUIRED`,
có cache) khác với "nghiệp vụ đã xong" (`PROCESSED`). Cache được gắn **fingerprint**
(taxonomy + schema hợp đồng); đổi `document_types.json` hay hợp đồng JSON làm cache
hết hạn (`STALE_ANALYSIS`), tự động đọc lại — không cần thao tác gì thêm.

- Dry-run **không bao giờ** đánh dấu PROCESSED.
- Một nguồn có tài liệu REVIEW **không bao giờ** tự thành PROCESSED chỉ vì đã
  apply/copy ra `review/` — phải `resolve-review` từng logical document trước.
- Apply thất bại (QC fail hoặc xung đột ghi/đổi tên) → nguồn đó thành `FAILED`,
  **không tự retry**; cần `--retry-failed` rõ ràng ở lần sau.
- Tiến trình bị dừng đột ngột giữa chừng (crash, đóng Antigravity) → nguồn đó hiện
  `INTERRUPTED` ở lần chạy sau, cũng cần `--retry-failed` mới xử lý lại.

### Đặt tên toàn cục (global naming)

Đánh số `.1/.2/...` cho nhiều tài liệu cùng `type_id` nhìn **TOÀN BỘ** hồ sơ của
một người (mọi nguồn, mọi lượt chạy), không chỉ lượt hiện tại:

- Thêm tài liệu mới hơn → chỉ thêm số tiếp theo, không đụng file cũ.
- Thêm tài liệu cũ hơn (chen vào giữa) → các file `.1/.2/...` **đã ghi trước đó
  có thể bị đổi tên** để đúng thứ tự thời gian. Đây là hành vi ĐÚNG, không phải lỗi.
  Nội dung file không đổi, chỉ tên thay đổi; `logical_document_id` (khóa nội bộ
  trong manifest) giữ nguyên nên vẫn truy vết được lịch sử.
- Hai tài liệu trùng ngày: xếp bằng tie-break xác định (tiêu đề chuẩn hoá → mã
  băm nguồn → số trang) — `same_date_tie_break: "deterministic"` trong manifest.
  Không dùng thứ tự scan làm mốc thời gian.
- Việc đổi tên thực thi bằng kế hoạch 2 pha an toàn (đổi sang tên tạm trước, rồi
  mới đổi sang tên cuối) — lỗi giữa chừng (đĩa đầy, quyền ghi...) sẽ **rollback
  về đúng trạng thái ban đầu**, báo `BLOCKED_RUNTIME`, và nguồn liên quan thành
  `FAILED` — không có trạng thái nửa-đổi-tên nào được commit.

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
| `ORDERING_MISSING_RELIABLE_DATE` | Có tài liệu cùng loại thiếu ngày đáng tin cậy | `resolve-review` bổ sung ngày, hoặc xác nhận ngày đã đọc là đúng |

Lưu ý: hai tài liệu cùng loại **trùng ngày** không còn là lý do REVIEW — global
naming (mục dưới) tự xếp bằng tie-break xác định, không cần người vận hành can thiệp.

## Bốn chính sách sau blind runtime test (DEV POLICY CLOSURE)

- **Type 87 + subtype** — quyết định nhân sự (điều động/bố trí/bổ nhiệm/thăng
  cấp bậc hàm/nâng bậc lương/nghỉ hưu) quy về `type_id=87`, kèm `subtype`
  metadata phụ (không đổi tên file chính thức, không tạo type mới).
- **SUPPORTING_DOCUMENT** — tài liệu ngoài danh mục 104 loại, người vận hành
  xác nhận bằng `resolve-review ... --supporting`. Tên file
  `SUPPORTING.<Ten_tai_lieu>.pdf` (hoặc `.N.pdf` nếu trùng tiêu đề) — không
  dùng STT 01-104 giả.
- **DUPLICATE** — bản scan trùng, xác nhận bằng
  `resolve-review ... --duplicate-of <id>`. Không xóa/mutate nguồn, không tạo
  output thứ hai. Nghi ngờ chưa chắc → vẫn REVIEW.
- **Partial date precision** — `document_date` có thể chỉ ở mức MONTH/YEAR
  (`date_precision`), không tự bịa ngày đầy đủ. Hai tài liệu có khoảng ngày
  chồng lấn nhưng không bằng nhau hệt (theo precision) → `ORDER_AMBIGUOUS`,
  vẫn REVIEW, không tự đoán thứ tự.

Chi tiết đầy đủ: `.agents/rules/party-record-digitization.md` mục 9.

## Apply lại nhiều lần

- Không có gì mới/thay đổi: 0 thao tác ghi/đổi tên, không tạo bản trùng, không đụng mtime file.
- Rename plan lỗi giữa chừng: **rollback về đúng trạng thái ban đầu**, không ghi file nào, báo `BLOCKED_RUNTIME`.

## Runtime Agent bị cấm

- sửa `AGENTS.md`;
- sửa `document_types.json`;
- sửa `test_cases/*`, `fixtures/*`;
- sửa source code trong `app/`, sửa tests;
- tự thay threshold;
- tự tạo taxonomy mới;
- tự đặt tên file / đánh số `.1/.2`, tự đổi chính sách global naming/tie-break;
- tự resolve một logical document REVIEW_PENDING thay người vận hành;
- tự gán `subtype` type 87, tự chuyển UNKNOWN sang SUPPORTING_DOCUMENT, tự xác
  nhận DUPLICATE khi chưa có bằng chứng deterministic, tự bịa ngày đầy đủ khi
  chỉ đọc được tháng/năm;
- đọc lại (Vision) nguồn đã có cache hợp lệ (PROCESSED hoặc fingerprint chưa đổi);
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
