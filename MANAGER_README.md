# Hồ sơ Digitization Manager

Ứng dụng local/offline nằm trong `app/manager`. Chạy từ repository root:

```powershell
python -m uvicorn app.manager.main:app --host 127.0.0.1 --port 8765
```

Mở `http://127.0.0.1:8765/`, vào `Cấu hình` để xem root hiện tại, rồi dùng
`Quét lại dữ liệu`. Mặc định Manager đọc `input/`, lưu metadata ở
`data/manager.db`, không lưu binary PDF.

Để build Windows onedir, chạy `./build_manager.ps1`; xem `PACKAGING.md` để
cấu hình `config.local.json` khi chạy từ source hoặc `config.json` cạnh
`HosoManager.exe`. Biến môi trường `HOSO_DATA_ROOT` có thể override `data_root`.

Source code và dữ liệu được tách riêng:

- Source: `D:\\04. Github\\hoso-digitization-manager`
- Laptop data root: cấu hình local tới `D:\\01. Công việc\\Số hóa hồ sơ Đảng viên`
- Desktop data root: cấu hình local tới thư mục Google Drive mirror tương ứng

Không commit `config.local.json`, `config.json`, database runtime, log hoặc PDF.

Manager tái sử dụng `document_types.json`, scanner/pipeline artifacts hiện hữu
và đọc manifest/ledger theo cấu hình. Khi không có artifact integration, nó
chạy bằng filesystem fallback.
