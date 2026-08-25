# Hồ sơ Digitization Manager

Ứng dụng local/offline nằm trong `app/manager`. Chạy từ repository root:

```powershell
python -m uvicorn app.manager.main:app --host 127.0.0.1 --port 8765
```

Mở `http://127.0.0.1:8765/`, vào `Cấu hình` để xem root hiện tại, rồi dùng
`Quét lại dữ liệu`. Mặc định Manager đọc `input/`, lưu metadata ở
`data/manager.db`, không lưu binary PDF.

Để build Windows onedir, chạy `./build_manager.ps1`; xem `PACKAGING.md` để
cấu hình `config.json` cạnh `HosoManager.exe`.

Manager tái sử dụng `document_types.json`, scanner/pipeline artifacts hiện hữu
và đọc manifest/ledger theo cấu hình. Khi không có artifact integration, nó
chạy bằng filesystem fallback.
