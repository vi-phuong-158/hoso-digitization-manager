# Phase 11 — UX baseline

Ngày khảo sát: 2026-08-25. Phạm vi: manager FastAPI/Jinja offline, dùng fixture
tổng hợp; không mở hoặc chụp dữ liệu PDF thật.

## Cách khảo sát

- Đọc shell, routes, templates và stylesheet hiện hữu.
- Chạy manager route tests với fixture synthetic và kiểm tra HTML/JSON của
  dashboard, danh sách, chi tiết, settings.
- Kiểm tra các luồng quét, tìm kiếm/lọc, checklist override, complete/reopen,
  mở PDF, settings và backup metadata.

## Hiện trạng trước Phase 11

| Khu vực | Quan sát | Tác động |
|---|---|---|
| App shell | Sidebar cơ bản nhưng thiếu Lịch sử quét, trạng thái active và data root | Người dùng khó biết đang ở đâu và dữ liệu nào đang dùng |
| Dashboard | Nhiều card số liệu nhưng chưa có bảng đơn vị đủ cột, progress bar và thứ tự ưu tiên rõ | Chưa trả lời nhanh “làm hồ sơ nào tiếp theo” |
| Hồ sơ | Filter có nhưng lộ enum kỹ thuật, table chưa có ƯT1/cập nhật và row click | Khó scan bằng mắt, cần nhớ mã trạng thái |
| Chi tiết | Một panel checklist phẳng, chưa nhóm ưu tiên/override UI; action dùng `alert()` | Nhiều thao tác thừa, trạng thái và lỗi khó hiểu |
| Settings | Chỉ hiển thị path, chưa có đổi root, diagnostics và restore | Người dùng thường không tự cấu hình/chuyển máy được |
| Trạng thái | Màu xanh chung và hiển thị enum kỹ thuật | Không nhất quán giữa nghiệp vụ và giao diện |
| States | Empty có một phần; thiếu loading/error inline | Scan lỗi có nguy cơ mất ngữ cảnh dashboard |
| Windows | Có executable/lock cơ bản nhưng startup mở browser trước khi server sẵn sàng; chưa có installer chuẩn | Double-click có thể gặp race/port conflict; cài đặt còn thủ công |

## Hướng chỉnh sửa đã khóa

- Giữ FastAPI/Jinja/SQLite, không thêm chart/frontend dependency, không sửa
  scanner/classifier/taxonomy.
- Dùng palette xanh navy–teal–amber, system font stack local, semantic HTML,
  focus ring, hover/pressed feedback và responsive desktop/tablet.
- Ưu tiên hiển thị tiếng Việt; enum chỉ còn ở diagnostics/history khi cần.
- UI sorting **Cần xử lý** là heuristic trình bày: thiếu ƯT1 → cần bổ sung →
  đang số hóa/chờ kiểm tra → cảnh báo; không thay đổi business status engine.
- Backup/restore chỉ tác động SQLite metadata và luôn có safety backup trước
  restore.
