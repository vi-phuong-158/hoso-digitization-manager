# OPUS5_HIGH_BUILD_TASK.md

## Nhiệm vụ

Bạn đang ở DEV mode. Hãy xây MVP production-safe cho repo số hóa hồ sơ Đảng viên.

Trước khi làm:
1. Đọc `AGENTS.md`.
2. Đọc `document_types.json`.
3. Đọc `test_cases/HAI_GOLDEN.json`.
4. Không thay đổi 3 file trên để làm test dễ hơn.

## Mục tiêu

Xây pipeline local có khả năng:

`folder người -> PDF scan -> page analysis -> document segmentation -> classification 01-104/UNKNOWN -> deterministic naming -> dry-run manifest -> apply -> output/review`

Điểm bắt buộc:
- Một PDF có thể chứa nhiều logical documents.
- Bìa/mặt sau phải ghép đúng với trang nội dung.
- Tách PDF bằng page objects, giữ nguyên chất lượng.
- Không sửa/xóa source.
- Mặc định dry-run.
- Runtime model/provider phải adapter-based để sau này Gemini có thể thực thi mà không sửa business logic.

## Thiết kế ưu tiên

Giữ đơn giản. Khuyến nghị Python.

Các module tối thiểu:
- `catalog.py`
- `pdf_inventory.py`
- `vision_adapter.py`
- `segmenter.py`
- `classifier.py`
- `naming.py`
- `manifest.py`
- `writer.py`
- `qc.py`
- `cli.py`

Provider/model không được hard-code vào core logic.

Ví dụ interface:

```python
class DocumentVisionProvider:
    def analyze_pages(self, pdf_path, page_numbers): ...
    def classify_document(self, pdf_path, page_numbers, candidates): ...
```

Sau này Gemini chỉ cần một adapter/provider hoặc config phù hợp.

## CLI mong muốn

```bash
python -m app.cli process input/NGUYEN_HUU_HAI --dry-run
python -m app.cli process input/NGUYEN_HUU_HAI --apply
python -m app.cli test-golden
```

Tên lệnh có thể khác nếu có lý do tốt, nhưng phải dễ dùng.

## Yêu cầu kiểm thử

Tạo:
- unit tests cho naming;
- unit tests cho page coverage/overlap;
- unit tests cho duplicate ordering;
- unit tests cho copy/split không sửa source;
- golden acceptance dùng `test_cases/HAI_GOLDEN.json`.

Golden test phải chạy được bằng provider fixture/mock trước.
Nếu có quyền gọi model thật, chạy thêm model rehearsal nhưng không thay golden label.

## Runtime contract

Sau khi build xong, tạo `RUNBOOK_GEMINI.md` để Gemini runtime chỉ cần:
1. đặt tài liệu vào `input/<TEN_NGUOI>/`;
2. chạy dry-run;
3. xem summary/review;
4. apply khi được yêu cầu.

Gemini runtime không được:
- sửa code;
- sửa taxonomy;
- sửa golden test;
- tự hạ threshold.

## Không làm

- Không MarkItDown.
- Không Pinecone/RAG/vector DB.
- Không database server.
- Không GUI ở vòng đầu.
- Không rewrite PDF thành ảnh.
- Không log toàn văn tài liệu.
- Không tự upload tài liệu tới provider/model khác.

## Definition of Done

Chỉ báo `READY_FOR_RUNTIME_REHEARSAL` khi:
- source tree sạch;
- unit tests pass;
- golden segmentation pass;
- classification exact hoặc đúng REVIEW theo golden;
- page coverage 100%;
- overlap 0%;
- input source hashes không đổi;
- dry-run không ghi output;
- apply tạo output đúng;
- chạy apply lặp lại không âm thầm tạo duplicate;
- có `RUNBOOK_GEMINI.md`;
- có báo cáo ngắn về giới hạn còn lại.

Nếu chưa đạt, báo blocker cụ thể. Không tuyên bố hoàn thành giả.
