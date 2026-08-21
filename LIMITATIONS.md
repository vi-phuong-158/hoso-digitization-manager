# LIMITATIONS.md — Giới hạn còn lại

Cập nhật sau vòng **Incremental processing** (state registry SQLite local).

Trạng thái: 198 unit test xanh (151 cũ + 47 mới cho state/incremental); golden
acceptance xanh với cả provider `fixture` lẫn `agent`.

---

## -1. Giới hạn mới: đánh số `.1/.2/...` chỉ trong phạm vi MỘT lượt chạy

Naming engine (`app/naming.py`) không đổi — vẫn deterministic, vẫn đánh số cũ→mới
theo ngày. Nhưng với incremental processing, mỗi lượt `process`/`apply` chỉ gom
các tài liệu **mới được xử lý trong chính lượt đó** để tính thứ tự `.1/.2/...`,
KHÔNG biết tới các tài liệu cùng loại đã `PROCESSED` từ lượt trước.

Hệ quả: nếu lượt 1 apply một tài liệu loại `04` (ra file bare `04.xxx.pdf`), rồi
lượt 2 (sau khi thêm PDF mới) cũng có đúng một tài liệu loại `04` MỚI, lượt 2 sẽ
tính nó là "tài liệu duy nhất loại 04 trong lượt này" và cũng thử đặt tên
`04.xxx.pdf` — trùng với file lượt 1 đã ghi.

**Đây không phải lỗi âm thầm.** Cơ chế content-key trong `writer.py` phát hiện
tên trùng nhưng nội dung nguồn khác nhau → báo xung đột → `BLOCKED_RUNTIME`,
không ghi đè, nguồn đó thành `FAILED` (không tự retry). Đã có test chuyên biệt
xác nhận hành vi chặn an toàn này:
`tests/test_incremental_pipeline.py::test_nhieu_tai_lieu_cung_loai_qua_nhieu_lan_apply_bi_chan_an_toan`.

**Việc cần làm tiếp (DEV mode, cần người vận hành chốt trước):** thiết kế cách
naming engine biết về sequence đã dùng của các lượt trước (ví dụ đọc
`output/<người>/_manifest.json` để tìm `max(sequence)` hiện có cho mỗi loại,
rồi nối tiếp) — **nhưng phải cân nhắc kỹ**: nếu tài liệu mới có ngày SỚM HƠN các
tài liệu đã áp dụng trước đó, đặt đúng thứ tự thời gian nghĩa là phải RENAME các
file đã ghi trước đó (đổi `.1`→`.2` v.v.) — đây là hành động ảnh hưởng tới ID đã
commit, ngoài phạm vi nhiệm vụ này và cần chính sách rõ ràng trước khi tự động hoá.

---

## 0. Đã gỡ khỏi danh sách blocker

- **Incremental processing** — hồ sơ được bổ sung liên tục không còn khiến toàn bộ
  PDF (kể cả đã xử lý) bị Agent đọc lại. Xem `RUNBOOK_ANTIGRAVITY.md` mục
  "Incremental processing" và `app/state.py`/`app/incremental.py`.

- **Gemini API rehearsal** — không còn là gate. Runtime đã chuyển sang Antigravity-native:
  Agent đọc PDF ngay trong workspace, ghi `analysis/<người>/<pdf>.json`, code local xử lý.
  `app/providers/gemini_provider.py` được đánh dấu `NOT_USED_IN_ANTIGRAVITY_RUNTIME`,
  không tự đăng ký vào registry, không nằm trong runtime path.
- **Văn bằng không đọc được ngày cấp** — sau khi Agent đọc trực tiếp bằng thị giác,
  cả 3 tài liệu trước đây "không có ngày" đều đã có ngày (xem mục 2).

---

## 1. Ràng buộc còn lại (cần người vận hành chốt) — nhóm 86 trùng ngày

Sau rehearsal thật, **mọi** văn bằng nhóm `86` đều đọc được ngày cấp. Nhưng nhóm này
vẫn phải ra `review/` vì một lý do duy nhất và có thật:

| Tài liệu | Trang | Ngày cấp |
|----------|-------|----------|
| Chứng chỉ tiếng Anh A1 | 13–14 | **2015-01-26** |
| Chứng chỉ tin học ứng dụng trình độ A | 15–16 | **2015-01-26** |

Hai chứng chỉ do cùng Trung tâm Ngoại ngữ – Tin học (Học viện ANND) cấp **cùng ngày**.
Theo `AGENTS.md` Phase E ("không tự đánh `.1/.2` theo thứ tự scan") và mục 5
("duplicate-type ordering ambiguity: HUMAN REVIEW"), pipeline **không** được tự chọn
ai là `.6`, ai là `.7`. Toàn nhóm 86 vì thế sang REVIEW.

Ba phương án đề xuất (mục 5 báo cáo rehearsal). **Chưa áp dụng phương án nào.**

## 2. Ngày văn bản: những chỗ Agent đã đọc được thêm

Ba tài liệu trước đây `null` nay có ngày, đọc trực tiếp từ ảnh trang:

| Tài liệu | Ngày | Căn cứ | Độ tin cậy |
|----------|------|--------|-----------|
| Giấy chứng nhận bồi dưỡng tiếng Lào | 2024-06-24 | Dòng ngày viết tay bên phần tiếng Lào: *Viêng Chăn, 24.6.2024* | 0.88 — chữ viết tay |
| Chứng nhận QP&AN đối tượng 4 | 2020-12-31 | *Hà Nội, ngày 31 tháng 12 năm 2020*; số hiệu `QPAN/8136/311220` khớp | 0.92 |
| Chứng nhận sơ cấp lý luận chính trị (loại 70) | 2017-06-26 | *Hà Nội, ngày 26 tháng 06 năm 2017* | 0.93 |

Golden không khai `document_date` cho ba tài liệu này nên không có xung đột.
Nếu người vận hành muốn khóa các ngày này vào golden, phải sửa golden **có phê duyệt**,
không phải việc của runtime.

## 3. Một quyết định đọc cần người vận hành biết — giấy khai sinh (trang 6–7)

Trang 6 có dòng *"Đăng ký ngày 17 tháng 3 năm 1995"*, nhưng ô
*"CHỨNG NHẬN SAO Y BẢN CHÍNH — Ngày … tháng … năm …"* **bỏ trống**.

Agent báo `document_date: null` và ghi ngày đăng ký vào `notes`, vì:
- ngày văn bản của **bản sao** là ngày chứng nhận sao y — không có;
- 17/3/1995 là ngày đăng ký khai sinh gốc, tức một trường **nội dung**;
- golden (đã được duyệt) khai `document_date: null`.

Nếu quy định nội bộ coi ngày đăng ký khai sinh là ngày văn bản, đây là thay đổi
chính sách — báo để DEV mode xử lý, không sửa trong runtime.

Cũng lưu ý: tài liệu là **bản sao**, trong khi danh mục `75` ghi "Khai sinh gốc".
Golden đã chốt dùng nhãn 75 theo bản chất tài liệu; nếu đơn vị chỉ nhận bản gốc
thì phải chuyển sang REVIEW, **không** tự đổi taxonomy.

## 4. Case golden mơ hồ vẫn treo — bằng THPT (trang 17–18)

Golden yêu cầu nhận diện ứng viên `86` nhưng **đưa REVIEW** vì danh mục 86 không nêu
văn bằng phổ thông. Pipeline làm đúng như vậy (`LOW_CONFIDENCE` + `AGENT_FLAGGED_REVIEW`).
Cần chốt chính sách: bằng THPT có thuộc 86 hay không. Đây là thay đổi taxonomy/quy định,
làm ở DEV mode.

## 5. Antigravity: chưa xác minh được quy ước đường dẫn

Các file rule/agent/workflow đã tạo đúng đường dẫn người vận hành nêu:

```
.agents/rules/party-record-digitization.md
.agents/agents/document-processor/agent.md
.agents/workflows/process-party-record.md
```

**Chưa** xác minh được Antigravity thực sự nạp đúng ba đường dẫn này và đúng cú pháp
frontmatter, vì phiên làm việc hiện tại không chạy bên trong Antigravity. Cần mở
Antigravity một lần để xác nhận rule hiện trong danh sách active và
`/process-party-record` gọi được. Nếu Antigravity dùng quy ước khác, chỉ cần **di chuyển
file**, nội dung giữ nguyên.

## 6. Rehearsal này do Claude (Opus 5) đóng vai Runtime Agent

Phiên rehearsal được thực hiện bằng chính khả năng vision của model đang chạy, không
phải bởi Gemini bên trong Antigravity. Ý nghĩa:

- Hợp đồng JSON, validator, segmenter, naming, QC **đã được kiểm chứng end-to-end**
  với dữ liệu nhận thức thật (không dùng fixture).
- Nhưng **chưa** biết Gemini trong Antigravity đọc các trang này chính xác đến đâu —
  đặc biệt: ngày viết tay tiếng Lào (trang 1), chữ nhũ vàng chìm trên bìa đỏ
  (trang 6, 10), và mặt sau giấy khai sinh (trang 7).
- Việc cần làm tiếp: chạy đúng workflow này trong Antigravity, so `analysis/*.json`
  do Gemini sinh ra với bản hiện có, rồi chạy `test-golden --provider agent`.
  Nếu lệch: **không sửa golden**, ghi nhận cho DEV mode.
- Một cảnh báo về tính độc lập: model chạy rehearsal đã biết trước nhãn golden từ
  phiên xây dựng trước đó, nên đây **không phải** một bài kiểm tra mù. Bài kiểm tra
  mù thật sự là lần Gemini chạy đầu tiên trong Antigravity.

## 7. Phạm vi segmentation đã kiểm và chưa kiểm

Đã kiểm bằng dữ liệu thật + unit test:

- một PDF chứa nhiều tài liệu độc lập;
- bìa nằm **sau** trang nội dung; bìa nằm **trước** trang nội dung;
- mặt trước + mặt sau (giấy khai sinh);
- trang tiếp nối nhiều trang;
- bìa mơ hồ → REVIEW; trang phụ mồ côi → vẫn được kể tới, gắn cờ REVIEW;
- Agent gom trang khác segmenter local → `AGENT_SEGMENTATION_MISMATCH` → REVIEW.

**Chưa** có dữ liệu thật cho:

- một tài liệu bị cắt ngang **hai file PDF khác nhau** (pipeline chỉ gom trang trong
  phạm vi một file nguồn, theo đúng schema manifest của `AGENTS.md`);
- PDF bị đảo lộn thứ tự trang so với bản giấy;
- hai bản scan trùng của cùng một tài liệu (chưa có bước khử trùng lặp);
- tài liệu nhiều trang xen kẽ nhau (interleaved).

## 8. Khác

- Fixture (`fixtures/vision/`) chỉ phủ hồ sơ Nguyễn Hữu Hải. Hồ sơ khác chạy
  `--provider fixture` sẽ báo lỗi rõ ràng thay vì đoán bừa.
- Có một thư mục hồ sơ mới `input/Vi Ngọc Phương/` (1 PDF) xuất hiện trong workspace,
  **chưa xử lý**, chưa có `analysis/`, chưa có golden.
- Bằng chứng "màu/mẫu bìa khớp" ở segmenter hiện xấp xỉ bằng **khổ trang** (đọc từ PDF).
  Riêng bìa trang 16 khổ trang không phân biệt được, phải nhờ tiêu đề — nếu gặp hồ sơ
  scan toàn bộ cùng một khổ, segmenter phụ thuộc gần như hoàn toàn vào tín hiệu của Agent.
- Chưa có bước khử trùng lặp tài liệu.
- Chưa đổi tên thư mục hồ sơ theo `[M1].[M2]...\[SoCCCD]_[HoTen]` — đúng `mvp_behavior`.
- Đường dẫn đích giới hạn 240 ký tự (Windows MAX_PATH). Vượt thì pipeline **dừng**
  chứ không cắt tên trong danh mục.
- Chưa có GUI (đúng yêu cầu).
