# Smart Door Pi — Mô tả hệ thống

Tài liệu này mô tả tổng quan kiến trúc, luồng hoạt động và cách vận hành hệ thống Smart Door Pi trong repository này.

## Tổng quan
Hệ thống là một khóa cửa thông minh chạy trên Raspberry Pi, gồm:
- Ứng dụng UI viết bằng C++ + LVGL hiển thị giao diện và điều khiển chính.
- Driver nhận diện khuôn mặt `face_driver.py` (Python) — hỗ trợ ONNX/YOLOv5 và fallback `face_recognition`.
- Driver RFID `rfid_driver.py` (Python) — đọc thẻ MFRC522.
- Các tài nguyên: thư mục `face_models/` cho mô hình AI, `messages/` lưu video tin nhắn, file dữ liệu face `dataset.pkl`.

Thiết kế giao tiếp giữa các thành phần là nhẹ: UI khởi chạy driver Python dưới dạng tiến trình con và đọc stdout để nhận các sự kiện; UI và driver Python cũng dùng các file trigger trong `/tmp` và RAM disk `/dev/shm` để trao đổi dữ liệu ảnh/preview.

## Thành phần chính
- `src/` : mã nguồn C++ (UI, main application, logic). Giao diện và nút chức năng chính nằm trong `src/ui/ui_app.cpp`.
- `src/main.cpp` : điều khiển phần cứng, đọc sự kiện RFID/face và kích hoạt relay.
- `face_driver.py` : driver camera & AI. Tìm và nạp mô hình ONNX trong `face_models/`, chạy vòng lặp chờ trigger (`/tmp/enroll_face`, `/tmp/scan_face`, `/tmp/record_start`, `/tmp/play_video`).
- `rfid_driver.py` : driver đọc thẻ (MFRC522). Hiện có phiên bản đọc liên tục.
- `face_models/` : để đặt tệp mô hình YOLO (khuyến nghị `yolov5-face.onnx`). Nếu chỉ có `.pt`, repo có script trong `yolov5-face-master` để export sang ONNX.

## GPIO lock mapping
- `GPIO 26` → Khóa cổng chính (MAIN DOOR)
- `GPIO 27` → Khóa thùng đồ Shipper (DELIVERY BOX)

Hàm `trigger_main_door()` và `trigger_delivery_box()` trong `src/main.cpp` gọi `trigger_lock()` với các GPIO này để bật relay trong 5 giây. `trigger_lock()` hiện dùng:
- `pinctrl set <gpio> op pn dh` / `dl` để điều khiển relay
- Nếu `pinctrl` không hoạt động, có thêm fallback sang `raspi-gpio` và `gpio -g`
- `reset_all_locks()` được gọi khi ứng dụng khởi động để đưa cả khóa về trạng thái đóng nếu chương trình trước đó để lại trạng thái bất thường
- Cả hai relay hiện được cấu hình active-low: mức thấp sẽ mở, mức cao sẽ đóng

`messages/` : chứa các tệp video do người gửi để lại (được ghi bởi `face_driver.py`).

## Luồng hoạt động tổng quát
1. Ứng dụng C++ (`smart_door_app`) khởi động, tạo giao diện LVGL và spawn hai tiến trình Python: `face_driver.py` và `rfid_driver.py`.
2. `face_driver.py` kiểm tra/ nạp mô hình (ONNX); nếu không có ONNX tìm `.pt` và cố export; nếu không có cả hai dùng `face_recognition` nếu có sẵn.
3. UI dùng các file trigger để báo cho `face_driver.py` hành động (ví dụ tạo `/tmp/enroll_face` để enroll khuôn mặt, `/tmp/record_start` để quay video, `/tmp/play_video` để phát file video).
4. `rfid_driver.py` in ra STDOUT dạng `SCAN:<UID>` khi quét được thẻ; UI lắng nghe stdout này để xử lý đăng ký thẻ hoặc mở cửa.
5. Khi face/RFID event xảy ra, các driver in ra dòng dạng `FACE:...` hoặc `SCAN:...` → UI đọc và thực hiện hành động (mở cửa, hiển thị thông báo, lưu dữ liệu...).

## Trigger files & IPC
- `/tmp/enroll_face` : tạo bởi UI (khi nhấn `SETUP FACE`) để `face_driver.py` enroll.
- `/tmp/scan_face` : tạo bởi UI (khi nhấn `FACE ID`) để `face_driver.py` quét và so sánh với `dataset.pkl`.
- `/tmp/record_start` : khi UI muốn bắt đầu ghi video tin nhắn.
- `/tmp/play_video` : UI ghi đường dẫn file vào đây để `face_driver.py` stream video và âm thanh.
- RAM disk preview: `/dev/shm/cam_frame.raw` hoặc file tương tự — driver ghi ảnh preview RGBA, UI đọc để hiển thị.

> Lưu ý: giao tiếp hiện tại dựa trên file-system (file-trigger + stdout). Đây là cách đơn giản, dễ debug nhưng không phải là IPC có độ tin cậy/độ trễ thấp nhất cho production.

## UI — Các chế độ (mode) và hành vi
Thông tin chính từ `src/ui/ui_app.cpp`:

- MODE_TENANT (mặc định) — nút `TENANT`:
  - Ô nhập hiển thị placeholder `Enter PIN...`, ở chế độ password (ẩn ký tự).
  - PIN tenant mặc định (hardcoded): `123456`. Nhập đúng sẽ gọi `trigger_main_door()` để kích hoạt relay mở cửa chính.

- MODE_SHIPPER — nút `SHIPPER`:
  - Ô nhập placeholder `Order code...` (không ẩn ký tự).
  - So sánh với `registered_order_code` (được set qua popup cấu hình). Nếu trùng sẽ gọi `trigger_delivery_box()`.

- SETTINGS / CONFIG — nút `SETTINGS`:
  - Mở popup xác thực. Popup có 2 bước (`auth_step`):
    - Bước 0: nhập Admin PIN để truy cập menu bí mật. Admin PIN mặc định: `190104`.
    - Bước 1: khi ở bước đăng ký, cho phép nhập `registered_order_code` (mã giao hàng) hoặc bấm `SETUP CARD` / `SETUP FACE` để ghi thẻ hoặc enroll mặt.
  - `SETUP CARD` kích hoạt chế độ cài thẻ (UI đặt `rfid_mode = 1` trong thời gian ngắn để nhận thẻ tiếp theo và lưu UID vào biến `registered_card_uid`).

- FACE ID — nút `FACE ID`:
  - UI tạo trigger `/tmp/scan_face` và mở popup camera; `face_driver.py` quét, nếu khớp sẽ in `FACE:<name>`.
  - Nếu `face_driver.py` in `ENROLL:SUCCESS` thì UI sẽ thông báo "Tenant face registered!".

- VIDEO MSG — nút `VIDEO MSG`:
  - Cho phép người bên ngoài ghi tin nhắn video (~15s). UI tạo `/tmp/record_start`; `face_driver.py` thu hình và âm thanh, ghép audio bằng `ffmpeg` và lưu vào `messages/`.
  - Xem tin nhắn: UI đặt tên file vào `/tmp/play_video` và driver stream file đó, UI nhúng preview.

## Mật khẩu / mã mặc định
- Tenant PIN: `123456` (mở cửa chính)
- Admin PIN: `190104` (mở menu settings/secret)
- `registered_card_uid`: khởi tạo mặc định `NONE` (cần cài thẻ để sử dụng)
- `registered_order_code`: rỗng ban đầu, set bằng popup SHIPPER CONFIG

**Ghi chú bảo mật:** những giá trị này hiện được hardcode/giữ trong bộ nhớ chương trình. Bạn nên thay đổi/ lưu persistent vào file/DB và mã hóa nếu dùng trong môi trường thực tế.

## Chi tiết `face_driver.py`
- Tìm mô hình ONNX trong `face_models/` (tên khuyến nghị `yolov5-face.onnx`). Nếu không tìm thấy, tìm file `.pt` và gọi script export trong `yolov5-face-master/export.py`.
- Nếu `onnxruntime` không có hoặc mô hình không nạp được, driver sẽ fallback dùng `face_recognition` (nếu cài).
- Hàm chính:
  - `load_yolo_face_detector()` — nạp mô hình ONNX
  - `open_camera_and_scan(mode)` — dùng cho `ENROLL` hoặc `SCAN` (trả về tên hoặc `TIMEOUT`/`FAILED`)
  - `record_video()` — quay video, ghi preview cho UI, ghép audio bằng `ffmpeg`
  - `play_video_stream()` — đọc file video, ghi preview vào RAM disk, gọi `ffplay` để phát âm thanh

## Chi tiết `rfid_driver.py`
- Dùng thư viện `mfrc522` (Python SimpleMFRC522). Hiện code mặc định đọc liên tục và in `SCAN:<UID>` khi có thẻ.
- `src/main.cpp` spawn tiến trình `python3 ../rfid_driver.py` và đọc stdout để nhận `SCAN:` events.
- UI có cơ chế "setup card" (gán vào `registered_card_uid`) khi nhấn `SETUP CARD` trong popup cài đặt.

## Build & chạy
Môi trường mặc định dùng CMake để build app C++ và Python scripts chạy độc lập.

Ví dụ build & chạy từ thư mục gốc:

```bash
mkdir -p build
cd build
cmake ..
make -j
./smart_door_app
```

Lưu ý: trước khi chạy, cài Python env cần thiết cho `face_driver.py` và `rfid_driver.py` (`onnxruntime`, `opencv-python`, `face_recognition`, `mfrc522`...). Có sẵn `yolov5_env/` trong repo dùng để tham khảo môi trường Python.

## Cách enroll face và cài thẻ
- Enroll face: vào UI → `SETTINGS` → `SETUP FACE` (hoặc nút tương tự). UI sẽ tạo `/tmp/enroll_face` và driver thực hiện enroll, in `ENROLL:SUCCESS` khi thành công.
- Enroll thẻ: vào UI → `SETTINGS` → `SETUP CARD` → trong khoảng thời gian chờ (UI hiển thị) quẹt thẻ vào đầu đọc; main app sẽ lưu UID vào `registered_card_uid`.

## Gợi ý cải tiến (đề xuất)
- Lưu `registered_card_uid` và `registered_order_code` persistent (file JSON hoặc simple DB) để không mất sau reboot.
- Thay giao tiếp file-trigger bằng socket/Unix domain socket để IPC tin cậy hơn.
- Thay hardcoded PIN bằng cấu hình được mã hóa; thêm audit/log khi mở cửa.
- Cho phép chọn chế độ RFID: auto-scan liên tục hoặc on-demand (UI tạo trigger `/tmp/scan_card`) để tránh quét không mong muốn.

## Khắc phục sự cố nhanh
- Nếu không thấy preview camera: kiểm tra `face_driver.py` có chạy, và `/dev/shm` có file preview.
- Nếu RFID không phát hiện: kiểm tra kết nối MFRC522, quyền truy cập SPI, và log stdout của `rfid_driver.py`.
- Nếu ONNX load lỗi: kiểm tra `onnxruntime` phiên bản tương thích và file mô hình.

---


