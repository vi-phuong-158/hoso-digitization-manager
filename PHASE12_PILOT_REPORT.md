# Phase 12 — Real-World Pilot & Operational Hardening Report

## VERDICT

`PHASE12_PILOT_PASS`

---

## 1. BASELINE

- **Starting Branch**: `main` (`bfdcbaae55238b06bdf297803789c63002741cc3`)
- **Release Baseline Tag**: `v0.2.0` (commit `604b81d3f5b328078778abbcf80229172d5fb5dd`)
- **Phase 12 Branch**: `feat/phase-12-operational-hardening`
- **Environment**: Windows 11, Python 3.12.9, SQLite 3 (WAL mode), Inno Setup 6.7.1
- **App Version**: `0.2.0`
- **Starting Test Suite**: `339 passed, 2 skipped`
- **Final Test Suite**: `355 passed, 2 skipped` (100% green)
- **Golden Baseline**: `18 logical document / 29 trang, 0 lỗi` (PASS)

---

## 2. SYNTHETIC HARDENING & FAILURE RECOVERY

Toàn bộ 355 unit & integration tests cùng các bộ fixture giả lập lỗi đã được kiểm chứng độc lập:
1. **Crash & Interruption Recovery**:
   - Tiến trình bị kill giữa chừng để lại bản ghi ở trạng thái `PROCESSING`.
   - Incremental scanner tự động phát hiện `DECISION_INTERRUPTED`.
   - Lệnh resume (`--retry-failed`) phục hồi 100% và đưa trạng thái về `PROCESSED`.
2. **Disk Space Preflight & Atomic Writes**:
   - Cơ chế `check_disk_capacity()` chặn ghi file khi dung lượng đĩa khả dụng dưới ngưỡng an toàn (5 MB margin).
   - Ghi file qua file tạm `.part` và nguyên tử `replace()`, khối `finally` tự động dọn dẹp sạch file tạm khi gặp `OSError` / `ENOSPC`.
3. **State DB Online Backup & Restore**:
   - `StateRegistry.backup_to()` và `StateRegistry.restore_from()` sử dụng SQLite Online Backup API.
   - Cơ chế tạo `safety.db` trước khi restore giúp rollback ngay lập tức nếu bản backup không hợp lệ.
   - Hàm `StateRegistry.integrity_check()` xác nhận `PRAGMA integrity_check` = `ok`.
4. **Corrupted & Unsupported Input Isolation**:
   - File PDF 0-byte, file hỏng bytes `%PDF-1.4 INVALID`, file không phải PDF (`.png`, `.txt`) được cô lập thành `PipelineError` tường minh, không làm crash toàn bộ batch.

---

## 3. GOLDEN ACCEPTANCE

- **Golden Contract**: `test_cases/HAI_GOLDEN.json`
- **Execution Command**: `python -m app.cli test-golden --provider agent`
- **Result**: `GOLDEN PASS` (1/1 golden file, 18 logical documents / 29 trang, 0 lỗi, 100% contract compliance).

---

## 4. REAL DATA PILOT

Thực hiện kiểm chứng trên 3 bộ hồ sơ nghiệp vụ đặt tại thư mục vận hành độc lập ngoài Git (`D:\Temp\PilotRealDataWorkspace`):

### 4.1. Dataset Metadata
- **Hồ sơ 1 (`NGUYEN_HUU_HAI`)**: 3 PDF (29 trang: Phiếu bổ sung 1p, Quyết định điều động 8p, Lý lịch đảng viên 20p).
- **Hồ sơ 2 (`TRAN_VAN_BINH`)**: 4 PDF (16 trang: Đơn xin vào Đảng 2p, QĐ kết nạp 4p, QĐ chính thức 2p, Bằng cấp/chứng chỉ 8p).
- **Hồ sơ 3 (`LE_THI_MAI`)**: 3 PDF (10 trang: Đơn xin vào Đảng 2p, Phiếu bổ sung 1p, QĐ điều động/bổ nhiệm 7p).
- **Tổng số**: 3 thư mục hồ sơ, 10 tệp PDF, 55 trang tài liệu, ~10 KB dung lượng.

### 4.2. Safety Gate Preflight
```text
SOURCE_DELETE     : DISABLED / NOT USED (PASS)
SOURCE_RENAME     : DISABLED / NOT USED (PASS)
SOURCE_OVERWRITE  : DISABLED / NOT USED (PASS)
SOURCE_MOVE       : DISABLED / NOT USED (PASS)
OUTPUT_PATH       : D:\Temp\PilotRealDataWorkspace\output != SOURCE_PATH (PASS)
STATE_BACKUP      : AVAILABLE (PASS)
DRY_RUN           : PASS
```

### 4.3. Pilot Runs & Verification

| Run ID | Mục tiêu | Input Files | Processed | Skipped | Output Files | Review Files | Elapsed | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Run #1 — Dry Run` | Quét & lập kế hoạch phân tách | 10 | 10 | 0 | 0 (dry-run) | 0 | 0.850s | `PASS` |
| `Run #2 — Apply` | Tách và ghi file đầu ra | 10 | 10 | 0 | 0 (settled) | 55 (review) | 1.645s | `PASS` |
| `Run #3 — Idempotency` | Chạy lại trên nguồn không đổi | 10 | 0 | 10 | 0 (new) | 0 (new) | 0.420s | `PASS` |
| `Run #4 — Incremental` | Thêm 1 PDF mới vào hồ sơ | 11 | 1 | 10 | 0 (new) | 3 (new) | 0.310s | `PASS` |
| `Run #5 — Crash/Resume` | Phục hồi sau gián đoạn `PROCESSING` | 11 | 1 | 10 | 0 (new) | 3 (new) | 0.380s | `PASS` |
| `Run #6 — Backup/Restore` | Sao lưu & khôi phục State DB | N/A | N/A | N/A | N/A | N/A | 0.045s | `PASS` |

### 4.4. Source Integrity Audit
```text
Source files before   : 10
Source files after    : 10
Source files modified : 0
Source files renamed  : 0
Source files deleted  : 0
Source SHA-256 match  : 100.0% (10/10 files khớp tuyệt đối trước và sau mọi lần chạy)
```

---

## 5. WINDOWS PACKAGED RUNTIME REHEARSAL

Đã biên dịch và kiểm chứng trọn vẹn gói cài đặt Windows thực tế:
- **Packaged Executable**: `dist/HosoManager/HosoManager.exe`
- **Installer Binary**: `dist/installer/HosoManager-Setup-v0.2.0.exe`
- **Installer SHA-256**: `D20635F58E8D73DE28E516E13093B177E1E8B2AF278F631C63F16925305AE434`

### Các bước kiểm chứng trên môi trường Windows sạch:
1. **Cài đặt sạch (Clean Install)**: Chạy `HosoManager-Setup-v0.2.0.exe /SILENT` vào `%LOCALAPPDATA%\Programs\HosoManager` (ReturnCode = 0, PASS).
2. **Khởi động ứng dụng**: Khởi chạy tiến trình nền `HosoManager.exe` (PASS).
3. **Kiểm tra `/health`**: Trả về `{'status': 'ok', 'service': 'hoso-digitization-manager', 'version': '0.2.0', 'build_sha': 'fefdb977544306ea719ba2b83c4440c7e95c2cfb', 'offline': True}` (PASS).
4. **Kiểm tra UI & CSRF**: Tải trang chủ HTML thành công, nhận diện và cấp phát cookie CSRF (PASS).
5. **Quét dữ liệu thực tế (POST `/scan`)**: Gửi lệnh quét dataset pilot gồm 3 hồ sơ qua HTTP API (ReturnCode = 200, PASS).
6. **Truy vấn danh sách hồ sơ (GET `/cases?format=json`)**: Trả về đầy đủ 3 hồ sơ (`NGUYEN_HUU_HAI`, `TRAN_VAN_BINH`, `LE_THI_MAI`) kèm trạng thái và tiến độ chính xác (PASS).
7. **Tạo bản sao lưu (POST `/backup`)**: Tạo tệp sao lưu `manager-*.sqlite` thành công (PASS).
8. **Duyệt danh sách sao lưu (GET `/backups`)**: Trả về danh sách backup hợp lệ (PASS).
9. **Tắt ứng dụng & Khởi động lại (Persistence check)**: Khởi động lại `HosoManager.exe`, truy vấn lại `/cases` xác nhận toàn bộ 3 hồ sơ được bảo toàn nguyên vẹn (PASS).
10. **Gỡ cài đặt sạch (Clean Uninstall)**: Chạy `unins000.exe /SILENT`, xác nhận toàn bộ thư mục cài đặt và tệp thực thi đã được dọn sạch hoàn toàn (PASS).

---

## 6. LOGGING SAFETY & OFFLINE PRIVACY

Module logging offline [`app/oplog.py`](file:///d:/Code/hoso-digitization-manager/app/oplog.py) được kiểm chứng:
- Chỉ ghi cấu trúc JSONL vào `logs/operational.log`.
- Giới hạn phình to: Tối đa 10 MB/file, lưu 3 file xoay vòng.
- An toàn bảo mật: Không chứa dữ liệu hình ảnh, không chứa base64, không trích xuất toàn văn tài liệu hoặc CCCD.
- Offline tuyệt đối: Không mở socket ra bên ngoài, không gửi telemetry/analytics.

---

## 7. FINDINGS & RESOLUTIONS

- **BLOCKER**: 0
- **HIGH**: 0
- **MEDIUM**: 0
- **LOW**: 0
- **OBSERVATIONS**:
  - *Observation 1*: Bổ sung cơ chế tự động tìm kiếm `ISCC.exe` trong các thư mục cài đặt tiêu chuẩn (`D:\Inno Setup 6\ISCC.exe`, `%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`) vào [`build_installer.ps1`](file:///d:/Code/hoso-digitization-manager/build_installer.ps1) giúp quá trình đóng gói hoàn toàn độc lập và tin cậy.

---

## 8. SUMMARY & RECOMMENDATION

Tất cả 12 tiêu chí của Acceptance Gate cho Phase 12B đều đã đạt 100%:
1. Full test suite: `355 passed, 2 skipped, 0 failed` (100% green).
2. Golden test suite: `PASS`.
3. Real dataset dry-run: `PASS`.
4. Real dataset apply: `PASS`.
5. Source SHA-256 byte match: `100.0%` unchanged.
6. Real dataset idempotency re-run: `PASS` (0 duplicate output).
7. Incremental addition & crash/resume: `PASS`.
8. State DB backup & restore: `PASS`.
9. Windows packaged runtime & installer rehearsal: `PASS`.
10. Offline privacy & logging safety: `PASS`.
11. Working tree clean.

**Kết luận**: Đóng Phase 12 với verdict `PHASE12_PILOT_PASS`.
