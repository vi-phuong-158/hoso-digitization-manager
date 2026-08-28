# Working log — local Manager

## 2026-08-28

- Chuẩn hóa data root mặc định về `done\output`.
- Sửa navigation để Tổng quan, Hồ sơ, Thêm tài liệu, Scan/AI, Rà soát, Sao lưu và Cài đặt mở đúng route.
- Thêm manual document workflow: multipart upload ngắn hạn, thumbnail theo trang, drag-and-drop, rotation, xóa trang, taxonomy selector, preview filename, atomic PDF write và rescan index.
- Bổ sung metadata event tối giản cho tài liệu nhập thủ công.
- Đã chạy: `26 passed` cho regression Manager và acceptance ảnh/PDF manual add trong thư mục tạm.
- Full suite baseline còn bị chặn bởi fixture `analysis` đã không có trong worktree hiện hữu; không tự khôi phục dữ liệu phân tích/PII để làm xanh test. Browser visual QA cũng bị chặn bởi lỗi khởi tạo runtime nội bộ.

## Closure acceptance — 2026-08-28

- Full regression: `353 passed, 2 skipped`.
- Golden acceptance: PASS — 18 logical documents / 29 pages / 0 errors.
- Production root read-only smoke: 34 case folders / 2,198 PDFs; dashboard, list, detail, rescan HTTP 200. Only SQLite metadata index was refreshed.
- TEMP runtime smoke: health, all navigation routes, manual-add page, taxonomy 104, and restart persistence passed.
- Canonical `build_manager.ps1 -SkipInstaller` was attempted and stopped by its required clean-worktree guard; no commit, reset, stash, or bypass was performed.
- Browser automation remained unavailable due internal runtime initialization error; independent HTTP/TestClient UI smoke passed.