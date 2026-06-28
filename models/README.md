
# Face Models

Place a YOLO face detection model in this directory or any of its subdirectories.
Recommended model file name:
- `yolov5-face.onnx`

Example sources:
- https://github.com/deepcam-cn/YOLOv5-Face
The Python face driver will search recursively in `face_models/` for any `.onnx` model and load it automatically.
If no ONNX model is found, it will also search for a PyTorch `.pt` weight file and attempt to export it to ONNX.
If neither model file exists, the driver will continue using the existing `face_recognition` fallback.
If you have a `.pt` file, place it in `face_models/` and run the driver normally.
If you want to export a `.pt` manually, use the repo export script like:

```bash
cd face_models/yolov5-face-master
python3 export.py --weights /full/path/to/model.pt --img_size 640 --batch_size 1
```

This will produce a `.onnx` file alongside the `.pt` file.

Tổng quan các hành vi quan trọng của hệ thống (tương tác giữa UI C++ và driver Python):
- `face_driver.py` khởi động và cố gắng nạp mô hình ONNX bằng ONNX Runtime.
- Nếu không có file ONNX, nó tìm file `.pt` trong `face_models/` và gọi script export để tạo ONNX.
- UI (LVGL, C++) và driver Python giao tiếp qua các file trigger trên `/tmp` và qua RAM disk `/dev/shm/cam_frame.raw` để gửi khung ảnh preview.

Luồng chính (tóm tắt):
1. Khi khởi động, `face_driver.py` gọi `load_yolo_face_detector()` — tìm và nạp mô hình ONNX (hoặc export `.pt` -> `.onnx`).
2. `face_driver.py` chạy vòng lặp, kiểm tra các file trigger trong `/tmp`:
	 - `/tmp/play_video` → phát video (stream vào RAM disk, dùng `ffplay` để phát âm thanh)
	 - `/tmp/record_start` → tiến hành quay video (preview gửi về UI), lưu file vào `messages/`
	 - `/tmp/enroll_face` → mở camera ở chế độ ENROLL (ghi encoding vào `dataset.pkl`)
	 - `/tmp/scan_face` → mở camera ở chế độ SCAN (so sánh với `dataset.pkl` để xác thực)
3. UI (C++ / LVGL) hiển thị ô nhập PIN / mã, gửi trigger file để điều khiển hành vi camera/video của driver Python.

Các trigger và đường dẫn quan trọng:
- Trigger files: `/tmp/scan_face`, `/tmp/enroll_face`, `/tmp/play_video`, `/tmp/record_start`
- RAM disk preview: `/dev/shm/cam_frame.raw` (ghi ảnh RGBA để UI đọc)
- Face dataset: `dataset.pkl` (chứa `encodings` và `names` cho face_recognition)
- Video lưu tại: `messages/`

Chức năng theo UI / các chế độ (chi tiết từ `src/ui/ui_app.cpp`):
- SHIPPER (button "SHIPPER"):
	- Thiết lập `current_mode = MODE_SHIPPER`.
	- Placeholder trường nhập: "Order code...".
	- Trường nhập ở chế độ hiển thị (không ẩn ký tự) — người dùng nhập mã giao hàng nhìn thấy được.
	- Nếu mã nhập khớp `registered_order_code` thì gọi `trigger_delivery_box()` (mở hộp giao hàng).

- TENANT (button "TENANT"):
	- Mặc định hệ thống ở `MODE_TENANT` khi reset UI.
	- Placeholder: "Enter PIN...".
	- Trường nhập mật khẩu ở chế độ ẩn (password mode = true).
	- Mật khẩu Tenant mặc định (hardcoded trong UI): `123456` → nếu đúng gọi `trigger_main_door()` (mở cửa chính).

- SETTINGS / CONFIG (button "SETTINGS" → mở popup cấu hình):
	- Mở popup xác thực (popup_ta). Khi nhập ở popup:
		- Bước xác thực (auth_step == 0): nhập mã Admin để mở menu bí mật.
		- Mã Admin mặc định: `190104`.
		- Sau khi Admin được xác nhận, có thể chuyển sang bước đăng ký mã giao hàng (auth_step == 1) để lưu `registered_order_code` (lưu trong biến runtime của UI).
	- Popup còn có nút `SETUP CARD` (khi bấm sẽ bật chế độ scan RFID để ghi thẻ) và `SETUP FACE` (bấm sẽ tạo trigger `/tmp/enroll_face` để enroll face mới).

- FACE ID (button "FACE ID"):
	- Gọi `create_camera_popup("SCANNING FACE...")` và tạo file `/tmp/scan_face` để driver Python thực hiện quét.
	- Driver trả kết quả qua STDOUT (ví dụ `FACE:NAME` hoặc `FACE:TIMEOUT`) và UI sẽ hiển thị thông báo tương ứng.

- VIDEO MSG (button "VIDEO MSG"):
	- Cho phép người dùng ghi tin nhắn video (tối đa ~15 giây). UI tạo file `/tmp/record_start` để driver bắt đầu ghi.
	- Sau khi ghi xong, driver ghép audio + video (ffmpeg) và lưu vào `messages/`.
	- Xem tin nhắn: UI đặt đường dẫn vào `/tmp/play_video`, driver sẽ stream file đó và UI nhúng preview.

Mật khẩu và mã mặc định (ghi chú quan trọng):
- Tenant PIN (mở cửa chính): `123456`
- Admin PIN (mở menu cấu hình / secret menu): `190104`
- Registered order code: do người dùng nhập qua popup "SHIPPER CONFIG" — được lưu trong runtime (không được ghi ra file bởi UI mặc định)

Hướng dẫn đặt mô hình (như trước):
- Khuyến nghị tên file: `yolov5-face.onnx`.
- Nguồn tham khảo / scripts:
	- https://github.com/deepcam-cn/YOLOv5-Face
	- https://github.com/onnx/models/tree/main/vision/object_detection_segmentation/yolov5
- Nếu bạn có file `.pt`, đặt vào `face_models/` rồi khởi chạy driver; nếu có `yolov5-face-master/export.py` trong thư mục con thì driver sẽ gọi script để xuất ONNX tự động.

Ví dụ export thủ công:
```bash
cd face_models/yolov5-face-master
python3 export.py --weights /full/path/to/model.pt --img_size 640 --batch_size 1
```

Ghi chú vận hành & khắc phục:
- Nếu thiếu `onnxruntime`, driver sẽ in cảnh báo và tiếp tục (sẽ dùng `face_recognition` nếu có).
- Nếu thiếu `face_recognition`, hệ thống sẽ chỉ chạy YOLO (nếu ONNX được nạp) hoặc thông báo không có AI face.
- `registered_order_code` hiện được giữ trong bộ nhớ chương trình (khởi tạo rỗng) — khởi động lại ứng dụng sẽ xóa mã này.

