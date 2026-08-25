# Hồ sơ Digitization Manager

Ứng dụng Windows chạy offline để theo dõi tiến độ số hóa hồ sơ. Ứng dụng chỉ
đọc thư mục PDF nguồn, lưu metadata quản lý vào SQLite cục bộ và bind trên
`127.0.0.1`.

## Cài đặt

Chạy `HosoManager-Setup-v0.2.0.exe`. Installer cài theo user tại
`%LOCALAPPDATA%\Programs\HosoManager`, tạo shortcut Start Menu và tùy chọn
Desktop. Installer không chứa PDF thật hoặc database production.

## Mở ứng dụng

Double-click shortcut. Ứng dụng kiểm tra instance đang chạy, khởi động server
localhost rồi mở trình duyệt. Nếu đã có một instance, instance thứ hai không
khởi động thêm server.

## Chọn thư mục dữ liệu

Vào **Cấu hình**, nhập data root của máy hiện tại rồi bấm **Lưu cấu hình**.
Mỗi máy có thể dùng một đường dẫn khác nhau, ví dụ `D:\Data\HoSoSoHoa` hoặc
thư mục Google Drive tương ứng. Không cần sửa source.

## Quét và theo dõi tiến độ

Bấm **Quét lại** trên thanh đầu trang. Dashboard hiển thị tổng hồ sơ, tiến độ,
thiếu ưu tiên 1 và danh sách **Cần xử lý**. Scanner incremental nên lần quét
không đổi sẽ không đọc lại PDF đã biết.

## Checklist và hoàn thành hồ sơ

Mở **Hồ sơ**, chọn một dòng để xem chi tiết. Checklist được nhóm theo ưu tiên;
chọn trạng thái dễ hiểu như **Có tài liệu**, **Không phát sinh**, **Chưa xác
định** hoặc **Cần bổ sung**. Nút **Đánh dấu hoàn thành** luôn yêu cầu xác nhận
và sự kiện được ghi vào lịch sử. Có thể **Mở lại** khi cần xử lý tiếp.

## Sao lưu và khôi phục

Vào **Cấu hình → Sao lưu và khôi phục**. Backup chỉ chứa metadata quản lý:
checklist, ghi chú, trạng thái và lịch sử; không chứa PDF. Restore kiểm tra
SQLite, tạo safety backup database hiện tại rồi mới thay thế.

Không mở đồng thời cùng một database quản lý trên hai máy, nhất là khi
database nằm trong thư mục Google Drive đồng bộ.

## Chuyển sang máy khác

Cài ứng dụng trên máy mới, chọn data root mới trong Cấu hình, rồi chép một
backup SQLite metadata vào thư mục `data\backups` của ứng dụng để restore.
PDF nguồn vẫn ở thư mục dữ liệu; ứng dụng không di chuyển hoặc đổi tên PDF.

## Lỗi thường gặp

- **Chưa chọn thư mục dữ liệu**: kiểm tra đường dẫn data root trong Cấu hình.
- **Không có hồ sơ**: kiểm tra thư mục có subfolder hồ sơ và bấm Quét lại.
- **Có cảnh báo**: mở hồ sơ để xem file thiếu, file lỗi hoặc pipeline review.
- **Không mở được ứng dụng**: kiểm tra instance cũ, port localhost, và file
  `startup.log` cạnh executable.

## Chạy từ source (DEV)

```powershell
python -m pytest tests -q
./build_manager.ps1
./build_installer.ps1
```

Runtime nghiệp vụ vẫn tuân thủ `AGENTS.md`: không tự đổi taxonomy, không sửa
PDF nguồn, mặc định không upload và không cần Internet.
