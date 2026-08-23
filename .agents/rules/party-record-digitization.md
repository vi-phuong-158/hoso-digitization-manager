---
name: party-record-digitization
description: Luật bắt buộc khi số hóa hồ sơ đảng viên trong workspace này. Áp dụng cho mọi agent đọc/xử lý PDF trong input/.
alwaysApply: true
---

# LUẬT SỐ HÓA HỒ SƠ ĐẢNG VIÊN

Ưu tiên: **đúng > truy vết được > tự động hóa cao**.
Hợp đồng đầy đủ ở `AGENTS.md`. File này là bản rút gọn bắt buộc tuân thủ.

Bạn ở **RUNTIME MODE**. Bạn làm phần **nhận thức**; code local làm phần **quyết định**.

## 0b. Yêu cầu batch toàn bộ input

Nếu người vận hành nói *"Xử lý toàn bộ hồ sơ trong input"*, dùng workflow
batch thay vì bắt họ chạy lệnh cho từng người:

1. `python -m app.cli batch-run input --dry-run --json` để orchestration đánh
   dấu source `NEW`/`STALE` chưa có analysis.
2. Chỉ đọc bằng Vision source hiện trong `vision_required_sources`; ghi đúng
   JSON contract.
3. `python -m app.cli batch-run input` để validate/freeze và auto-apply duy
   nhất các hồ sơ AUTO_SAFE.
4. Chỉ hỏi operator về `NEEDS_REVIEW`/`MISSING_SOURCE`. Không tự retire source,
   không tự resolve REVIEW, không đọc lại cache hợp lệ.

Một người `BLOCKED` không được làm dừng các người độc lập khác. Chỉ lỗi baseline
toàn cục/state DB mới có thể trả `BATCH_SYSTEM_BLOCKED`.

## 0. Incremental — TRƯỚC KHI đọc bất kỳ PDF nào

Hồ sơ được bổ sung liên tục theo thời gian (`input/<TEN_NGUOI>/` có thể có
thêm PDF mới bất cứ lúc nào). **Trước khi mở bất kỳ PDF nào bằng Vision**, chạy:

```
python -m app.cli status "input/<TEN_NGUOI>"
```

Lệnh này chỉ đọc SHA-256 + state registry cục bộ (`state/processing_state.db`),
KHÔNG mở nội dung PDF. Sáu trạng thái một nguồn có thể ở:

| Trạng thái | Ý nghĩa | Agent đọc lại PDF? |
|---|---|---|
| `NEW` | chưa từng phân tích | **Có** |
| `STALE_ANALYSIS` | đã phân tích nhưng taxonomy/schema đã đổi từ đó | **Có** (cache không còn tin cậy) |
| `ANALYZED_PENDING_APPLY` | đã phân tích xong, không có gì cần review, chưa apply | Không — dùng cache |
| `REVIEW_REQUIRED` | đã phân tích xong nhưng còn logical document cần người chốt | Không, trừ khi người vận hành nói `retry review` |
| `PROCESSED` | nghiệp vụ đã hoàn tất (apply xong + hết review treo + QC PASS) | Không, tuyệt đối |
| `FAILED` / `INTERRUPTED` | lỗi kỹ thuật / tiến trình từng bị gián đoạn | Không, trừ khi người vận hành nói `retry failed` |
| `DUPLICATE_SOURCE` | trùng nội dung với file khác đã/sẽ xử lý | Không, vĩnh viễn |

**Chỉ đọc bằng Vision file `NEW`/`STALE_ANALYSIS`, hoặc file người vận hành yêu
cầu retry rõ ràng.** `python -m app.cli process "input/<TEN_NGUOI>"` tự động áp
dụng đúng luật này — chỉ cần chạy nó, không cần tự lọc file bằng tay; luật này
tồn tại để bạn HIỂU vì sao lệnh đó không xin phân tích lại những file cũ.

**Quan trọng:** "AI đã đọc xong" (`ANALYZED_PENDING_APPLY`/`REVIEW_REQUIRED`)
và "nghiệp vụ đã xong" (`PROCESSED`) là HAI KHÁI NIỆM KHÁC NHAU. Một nguồn có
tài liệu REVIEW không bao giờ tự thành `PROCESSED` chỉ vì đã apply/copy ra
`review/` — phải chờ người vận hành chốt bằng `resolve-review` (mục 8).

Nếu `status` báo `STATE_OUTPUT_MISMATCH` (state nói đã xử lý nhưng file đầu ra
bị thiếu): báo cho người vận hành, **không tự tạo lại**, không tự đoán nguyên nhân.

## 1. Phạm vi hồ sơ

1. Mỗi thư mục `input/<TEN_NGUOI>/` là hồ sơ của **một người**. Không trộn hồ sơ.
2. **Một PDF KHÔNG đồng nghĩa một tài liệu.** Một PDF có thể chứa một tài liệu một trang,
   một tài liệu nhiều trang, **nhiều tài liệu độc lập**, trang nội dung + bìa,
   mặt trước + mặt sau, hoặc nhiều văn bản cùng loại khác ngày.
3. Phải đọc **đủ tất cả các trang** của mọi PDF **NEW** (mục 0). Không được lấy mẫu,
   không được đoán trang chưa đọc. Mỗi trang phải có một mô tả trong `pages[]`.

## 2. Thứ tự bắt buộc

4. **Segmentation trước classification.** Xác định ranh giới tài liệu ở cấp trang trước,
   rồi mới phân loại theo **toàn bộ** logical document — không phân loại chỉ bằng trang đầu.
5. Bìa, mặt sau và trang tiếp nối phải được **ghép đúng** vào tài liệu tương ứng.
   Bìa/mặt sau không phải tài liệu độc lập nếu tiêu đề, khổ giấy, mẫu bìa và trình tự scan
   cho thấy chúng thuộc tài liệu liền kề. **Không đổi thứ tự trang.**
   Không chắc bìa thuộc trước hay sau → `needs_review: true`.

## 3. Taxonomy

6. Chỉ được dùng `type_id` trong khoảng `01`–`104`, hoặc `UNKNOWN`. Không có loại 105.
7. Phải đọc `document_types.json` trước khi phân loại. Đó là nguồn chân lý duy nhất.
8. **Không tự tạo taxonomy**, không đổi mã, không đổi tên danh mục.
   Các cặp dễ nhầm phải soi kỹ: 01/02 · 03/85 · 05/06 · 07/09/10 · 19/72/73 · 22/36/67 ·
   37/39 · 43/45 · 47/61/62/63/65 · 50/52 · 54/55/56/59 · 57/58 · **70/86** ·
   92/93/94/95 · 98/99 · 100/60 · 103/104.
   `70` = bằng/chứng chỉ **lý luận chính trị**. `86` = văn bằng/chứng chỉ chuyên môn,
   nghiệp vụ, ngoại ngữ, tin học, bồi dưỡng. Không khớp rõ → REVIEW, **không ép nhãn**.

## 4. Đặt tên (global, nhìn TOÀN BỘ hồ sơ)

9. **Không tự nghĩ filename.** Không gửi `target_file`, `filename`, `sequence`, `status`.
   Tên file do naming engine local sinh từ `document_types.json`. JSON có khóa dạng đó sẽ bị từ chối.
10. Đánh số `.1/.2/...` cho nhiều tài liệu cùng `type_id` nhìn **TOÀN BỘ** tài liệu
    đã biết của một người (mọi nguồn, mọi lượt chạy trước), không chỉ lượt hiện
    tại. Thêm một tài liệu cũ hơn có thể khiến các file `.1/.2/...` **đã ghi từ
    trước bị đổi tên** (không phải đổi nội dung) để đúng thứ tự thời gian — đây
    là hành vi ĐÚNG của hệ thống, không phải lỗi.
11. **Không dùng thứ tự scan/liệt kê file làm mốc thời gian.** Hai tài liệu
    trùng ngày được xếp bằng tie-break xác định (tiêu đề chuẩn hoá -> mã băm
    nguồn -> số trang), không đoán "cái nào có trước".
12. Runtime Agent **không được tự sửa chính sách đặt tên/global naming** (không
    đổi thứ tự ưu tiên tie-break, không tự chọn cách renumber khác).

## 5. Bảo toàn hồ sơ

13. **Không sửa, đổi tên, di chuyển hay xóa PDF trong `input/`.** Chỉ đọc.
    Trạng thái "đã xử lý" được lưu ở `state/processing_state.db` (SQLite local,
    khóa bằng SHA-256) — **không** ghi metadata, watermark, chữ `PROCESSED`,
    hay annotation vào chính file PDF để đánh dấu. Global naming (mục 4) chỉ được
    phép đổi tên file trong `output/`/`review/` — **không bao giờ** đụng tới `input/`.
14. Không sửa `AGENTS.md`.
15. Không sửa `document_types.json`.
16. Không sửa `test_cases/*` (golden tests) và `fixtures/*`.
17. Không tự hạ ngưỡng confidence, không tự đổi chính sách AUTO/REVIEW.

## 6. Khi không chắc

18. **Không chắc → REVIEW. Không đoán.** Đặt `needs_review: true` kèm `review_reason` ngắn.
    Cụ thể: không đọc được loại; rơi vào cặp dễ nhầm mà không tách bạch được;
    không rõ ranh giới tài liệu. Ngày văn bản chỉ ghi khi đọc được chắc chắn —
    chỉ thấy năm thì để `document_date: null`, **không suy diễn ngày/tháng**.
19. **Runtime Agent không sửa source code**, không sửa test, không sửa schema state DB,
    không tự triển khai logic mới khi gặp ca lạ. Ca lạ → báo `REVIEW_REQUIRED` và
    ghi nhận để DEV mode xử lý.
20. **Không upload tài liệu ra bất kỳ dịch vụ nào ngoài luồng đã được người vận hành phê duyệt.**
    Pipeline local không gọi API AI qua mạng; đừng thêm.
21. **Không ghi toàn văn hồ sơ hay dữ liệu cá nhân không cần thiết vào log**, chat hay JSON.
    `title_short` tối đa 200 ký tự; `notes`/`review_reason` tối đa 300 ký tự.

## 7. Đầu ra của bạn

Mỗi PDF nguồn `NEW`/`STALE_ANALYSIS` → một file JSON:

```
analysis/<TEN_NGUOI>/<ten_pdf_khong_duoi>.json
```

Đúng hợp đồng trong `app/agent_contract.py`. Sau đó chạy:

```
python -m app.cli process "input/<TEN_NGUOI>"
```

Mặc định là **dry-run**. Chỉ chạy `--apply` khi người vận hành yêu cầu rõ bằng chữ `apply`.

## 8. Chốt REVIEW không cần đọc lại PDF

Khi `status`/`process` báo có logical document `REVIEW_PENDING`, liệt kê chi tiết:

```
python -m app.cli review-list "input/<TEN_NGUOI>"
```

Người vận hành chốt loại/ngày đúng — Agent **KHÔNG được tự resolve thay người
vận hành**, chỉ được trình bày lựa chọn và chờ quyết định rõ ràng:

```
python -m app.cli resolve-review <logical_document_id> --type-id <mã> [--subtype <mã>] [--date yyyy-mm-dd] [--date-precision DAY|MONTH|YEAR]
python -m app.cli resolve-review <logical_document_id> --supporting
python -m app.cli resolve-review <logical_document_id> --duplicate-of <logical_document_id gốc>
```

Lệnh này KHÔNG đọc lại PDF — chỉ ghi quyết định vào state DB. Sau đó `process
... --apply` sẽ tính lại tên file (mục 4) và ghi file thật. Nguồn chỉ chuyển
sang `PROCESSED` khi **mọi** logical document của nó đã được giải quyết (AUTO
hoặc REVIEW đã resolve) **và** apply thành công **và** QC PASS.

## 9. Bốn chính sách phát sinh sau blind runtime test (DEV POLICY CLOSURE)

**Type 87 — quyết định nhân sự.** Điều động/bố trí/bổ nhiệm/thăng cấp bậc
hàm/nâng bậc lương/nghỉ hưu **được phép** quy về `type_id = 87` kèm `subtype`
metadata phụ (`transfer`/`assignment`/`appointment`/
`professional_title_appointment`/`promotion_salary`/`retirement`/
`other_personnel_decision`). `subtype` **không đổi filename chính thức** của
type 87, không tạo taxonomy mới. Chỉ người vận hành mới gõ `--subtype` khi
`resolve-review`; Agent không tự gán.

**Supporting — ngoài danh mục 104 loại.** Không được tự ép vào type gần nhất,
**không** tạo type 105+. Tài liệu `TYPE_UNKNOWN` chỉ chuyển sang
`classification_kind = SUPPORTING_DOCUMENT` khi người vận hành xác nhận bằng
`resolve-review ... --supporting`. Tên file dùng namespace riêng
`SUPPORTING.<Ten_tai_lieu>.pdf` (hoặc `.N.pdf` nếu trùng tiêu đề) — **không**
dùng số thứ tự 01–104 giả. Agent **không được tự AUTO** từ UNKNOWN sang
SUPPORTING_DOCUMENT.

**Duplicate — bản scan trùng.** Không xóa/mutate PDF nguồn. Chỉ đánh dấu
`classification_kind = DUPLICATE` (kèm `duplicate_of` trỏ tới bản gốc) khi
người vận hành xác nhận bằng `resolve-review ... --duplicate-of <id>`. Một
tài liệu DUPLICATE **không bao giờ** có output riêng. Agent chỉ được tự AUTO
duplicate nếu có bằng chứng deterministic rất mạnh (hash ảnh/trang giống hệt);
nghi ngờ mà chưa chắc → giữ nguyên REVIEW, không tự đoán.

**Partial date precision.** `document_date` có thể chỉ biết đến MONTH hoặc
YEAR — không được tự bịa thành ngày đầy đủ. Ghi `date_precision`
(`DAY`/`MONTH`/`YEAR`/`UNKNOWN`) đúng với độ chính xác đọc được. Naming engine
so khoảng ngày (theo precision) để xếp thứ tự; nếu khoảng của hai tài liệu
CHỒNG LẤN nhưng không bằng nhau hệt (vd MONTH "2023-11" và DAY "2023-11-05") →
`ORDER_AMBIGUOUS`, không tự giả định ai trước ai sau.

**Chính sách chuẩn hóa Bằng THPT & Hồ sơ Đoàn (Operator Confirmed):**
- **Bằng tốt nghiệp THPT** -> xếp vào **Mã 86** (Văn bằng, chứng chỉ chuyên môn).
- **Tài liệu Đoàn giới thiệu vào Đảng** (kiểm điểm đoàn viên, kiểm phiếu, biên bản hội nghị, báo cáo chi đoàn đề nghị giới thiệu...) -> xếp vào **Mã 40** (`40.Nghi_quyet_gioi_thieu_doan_vien_uu_tu_vao_Dang`).
- **Bản kiểm điểm người xin vào Đảng (Mẫu 2B-KNĐ)** -> xếp vào **Mã 37** (`37.Don_xin_vao_Dang`).
- **Báo cáo kết nạp đảng viên sau khi tổ chức lễ kết nạp** -> xếp vào **Mã 05** (`05.Quyet_dinh_ket_nap_dang_vien`).

