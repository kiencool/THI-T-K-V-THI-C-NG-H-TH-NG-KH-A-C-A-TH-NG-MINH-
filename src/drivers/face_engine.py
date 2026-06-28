"""
Smart Door Pi — Face Recognition Engine (Driver Layer)
Xử lý camera, AI nhận diện khuôn mặt (YOLOv5-Face + ResNet),
ghi video lời nhắn, và phát video.
Giao tiếp với C++ app qua flag files và RAM disk.
"""
import cv2
import os
import sys
import time
import pickle
import subprocess
import numpy as np

# Thêm thư mục gốc vào sys.path để import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import (
    FLAG_SCAN_FACE, FLAG_ENROLL_FACE, FLAG_RECORD_START, FLAG_PLAY_VIDEO,
    DATASET_FILE, CAM_FRAME_PATH, MESSAGES_DIR, MODELS_DIR,
    YOLO_FACE_MODEL, YOLO_INPUT_SIZE, YOLO_CONF_THRESHOLD, YOLO_NMS_THRESHOLD,
    FACE_DISTANCE_THRESHOLD, CAM_DISPLAY_SIZE, VIDEO_MAX_DURATION,
    VIDEO_FPS, VIDEO_WIDTH, VIDEO_HEIGHT, AUDIO_DEVICE, AUDIO_SAMPLE_RATE
)

try:
    import face_recognition
    face_recognition_available = True
except ImportError:
    face_recognition_available = False
    print("[FACE_AI] face_recognition not available, YOLO-only mode", flush=True)

try:
    import onnxruntime as ort
    ort_available = True
except ImportError:
    ort_available = False
    print("[FACE_AI] ONNX Runtime not available, using face_recognition only", flush=True)

# === YOLO Face Detector ===
yolo_session = None
yolo_available = False


def find_model_file(root_dir, ext):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(ext):
                return os.path.join(dirpath, filename)
    return None


def export_pt_to_onnx(pt_path):
    script = os.path.join(MODELS_DIR, "yolov5-face-master", "export.py")
    if not os.path.exists(script):
        print(f"[FACE_AI] Export script missing: {script}", flush=True)
        return None
    output_path = pt_path.replace('.pt', '.onnx')
    cmd = ["python3", script, "--weights", pt_path, "--img_size", "640", "--batch_size", "1"]
    try:
        print(f"[FACE_AI] Exporting PT to ONNX: {pt_path}", flush=True)
        result = subprocess.run(cmd, cwd=os.path.dirname(script), capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"[FACE_AI] ONNX export failed:\n{result.stderr}", flush=True)
            return None
        if os.path.exists(output_path):
            print(f"[FACE_AI] ONNX export succeeded: {output_path}", flush=True)
            return output_path
        print(f"[FACE_AI] Export finished but ONNX not found: {output_path}", flush=True)
    except Exception as e:
        print(f"[FACE_AI] Export error: {e}", flush=True)
    return None


def load_yolo_face_detector():
    global yolo_session, yolo_available
    if not ort_available:
        print("[FACE_AI] ONNX Runtime not available", flush=True)
        return False

    model_path = YOLO_FACE_MODEL
    if not os.path.exists(model_path):
        found = find_model_file(MODELS_DIR, ".onnx")
        if found:
            model_path = found
            print(f"[FACE_AI] Found YOLO model at: {model_path}", flush=True)
        else:
            pt_found = find_model_file(MODELS_DIR, ".pt")
            if pt_found:
                print(f"[FACE_AI] Found PyTorch weights: {pt_found}", flush=True)
                model_path = export_pt_to_onnx(pt_found)
                if not model_path:
                    print("[FACE_AI] Could not export ONNX from PT weight.", flush=True)
                    return False
            else:
                print(f"[FACE_AI] YOLO model missing: {YOLO_FACE_MODEL}", flush=True)
                return False
    try:
        yolo_session = ort.InferenceSession(model_path)
        yolo_available = True
        print(f"[FACE_AI] YOLO face detector loaded from {model_path}", flush=True)
        return True
    except Exception as e:
        print(f"[FACE_AI] Cannot load YOLO model: {e}", flush=True)
        yolo_available = False
        return False


def yolo_detect_faces(frame):
    if not yolo_available or yolo_session is None:
        return []
    height, width = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (YOLO_INPUT_SIZE, YOLO_INPUT_SIZE), swapRB=True, crop=False)
    input_name = yolo_session.get_inputs()[0].name
    output_names = [o.name for o in yolo_session.get_outputs()]
    ort_outs = yolo_session.run(output_names, {input_name: blob})
    outputs = ort_outs[0]
    if outputs is None:
        return []
    predictions = outputs.reshape(-1, outputs.shape[-1])
    boxes = []
    confidences = []
    for det in predictions:
        if det.size < 5:
            continue
        confidence = float(det[4])
        if confidence < YOLO_CONF_THRESHOLD:
            continue
        if det.size > 6:
            scores = det[5:]
            class_id = int(np.argmax(scores))
            confidence *= float(scores[class_id])
            if confidence < YOLO_CONF_THRESHOLD:
                continue
        cx, cy, w, h = det[0:4]
        left = int((cx - w / 2.0) * width / YOLO_INPUT_SIZE)
        top = int((cy - h / 2.0) * height / YOLO_INPUT_SIZE)
        right = int((cx + w / 2.0) * width / YOLO_INPUT_SIZE)
        bottom = int((cy + h / 2.0) * height / YOLO_INPUT_SIZE)
        left = max(0, min(width - 1, left))
        top = max(0, min(height - 1, top))
        right = max(0, min(width - 1, right))
        bottom = max(0, min(height - 1, bottom))
        boxes.append([left, top, right - left, bottom - top])
        confidences.append(confidence)
    indices = cv2.dnn.NMSBoxes(boxes, confidences, YOLO_CONF_THRESHOLD, YOLO_NMS_THRESHOLD)
    results = []
    if len(indices) > 0:
        for i in indices.flatten():
            x, y, w, h = boxes[i]
            results.append((y, x + w, y + h, x))
    return results


def detect_face_locations(frame, rgb_small_frame):
    if yolo_available:
        faces = yolo_detect_faces(frame)
        if faces:
            return faces
    if face_recognition_available:
        small_locations = face_recognition.face_locations(rgb_small_frame)
        return [(top * 4, right * 4, bottom * 4, left * 4) for (top, right, bottom, left) in small_locations]
    return []


def write_frame_atomic(rgba_frame):
    """Ghi file nháp rồi đổi tên để tránh C++ đọc file dở dang gây giật/lệch hình"""
    try:
        tmp_file = CAM_FRAME_PATH + ".tmp"
        with open(tmp_file, "wb") as f:
            f.write(rgba_frame.tobytes())
        os.rename(tmp_file, CAM_FRAME_PATH)
    except Exception:
        pass


def load_data():
    if os.path.exists(DATASET_FILE):
        with open(DATASET_FILE, 'rb') as f:
            return pickle.load(f)
    return {"encodings": [], "names": []}


def save_data(encodings, names):
    with open(DATASET_FILE, 'wb') as f:
        pickle.dump({"encodings": encodings, "names": names}, f)


def _prepare_display_frame(frame, border_color=(0, 255, 0)):
    """Cắt vuông và resize frame để gửi preview cho LVGL"""
    h, w, _ = frame.shape
    min_dim = min(h, w)
    cropped = frame[h//2 - min_dim//2: h//2 + min_dim//2, w//2 - min_dim//2: w//2 + min_dim//2]
    display_frame = cv2.resize(cropped, (CAM_DISPLAY_SIZE, CAM_DISPLAY_SIZE), interpolation=cv2.INTER_AREA)
    cv2.rectangle(display_frame, (5, 5), (CAM_DISPLAY_SIZE - 5, CAM_DISPLAY_SIZE - 5), border_color, 3)
    return cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGBA)


def record_video():
    """Hàm quay phim, thu âm rời và đồng thời gửi ảnh preview về cho giao diện LVGL"""
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')

    # Đọc bỏ 5 khung hình đầu tiên
    for _ in range(5):
        cap.read()

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    temp_video = os.path.join(MESSAGES_DIR, f"temp_vid_{timestamp}.avi")
    temp_audio = os.path.join(MESSAGES_DIR, f"temp_aud_{timestamp}.wav")
    
    recipient = "Msg"
    try:
        with open(FLAG_RECORD_START, "r") as f:
            content = f.read().strip()
            if content:
                import re
                safe_recipient = re.sub(r'[^a-zA-Z0-9_\-]', '', content)
                if safe_recipient:
                    recipient = safe_recipient
    except:
        pass
        
    final_video = os.path.join(MESSAGES_DIR, f"{recipient}_{timestamp}.mp4")

    out = cv2.VideoWriter(temp_video, fourcc, VIDEO_FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))

    # --- BẮT ĐẦU THU ÂM NGẦM ---
    audio_proc = subprocess.Popen(
        ["arecord", "-D", AUDIO_DEVICE, "-f", "S16_LE", "-r", AUDIO_SAMPLE_RATE, "-c", "1", temp_audio],
        stderr=subprocess.DEVNULL
    )

    print(f"[VIDEO] Start recording: {final_video}", flush=True)
    start_time = time.time()

    # Ghi hình tối đa VIDEO_MAX_DURATION giây hoặc đến khi C++ xóa file trigger
    while os.path.exists(FLAG_RECORD_START) and (time.time() - start_time < VIDEO_MAX_DURATION):
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        rgba_frame = _prepare_display_frame(frame, border_color=(0, 0, 255))
        write_frame_atomic(rgba_frame)

    cap.release()
    out.release()

    # --- DỪNG THU ÂM ---
    audio_proc.terminate()
    audio_proc.wait()

    # --- GHÉP HÌNH VÀ TIẾNG SANG MP4 ---
    print("[VIDEO] Encoding to MP4...", flush=True)
    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
        merge_cmd = f"ffmpeg -y -i {temp_video} -i {temp_audio} -c:v libx264 -preset fast -pix_fmt yuv420p -c:a aac {final_video} > /dev/null 2>&1"
        subprocess.run(merge_cmd, shell=True)

    # KIỂM TRA BẢO VỆ: Nếu ghép thất bại -> Lưu không tiếng
    if not os.path.exists(final_video):
        print("[VIDEO] Audio/Merge failed! Saving raw video without sound...", flush=True)
        if os.path.exists(temp_video):
            subprocess.run(f"ffmpeg -y -i {temp_video} -c:v libx264 -preset fast -pix_fmt yuv420p {final_video} > /dev/null 2>&1", shell=True)
            if not os.path.exists(final_video):
                os.rename(temp_video, final_video.replace('.mp4', '.avi'))

    # Dọn dẹp file nháp
    if os.path.exists(temp_video):
        os.remove(temp_video)
    if os.path.exists(temp_audio):
        os.remove(temp_audio)
    print(f"[VIDEO] Saved: {final_video}", flush=True)


def open_camera_and_scan(mode="SCAN", timeout=10):
    """Hàm quét mặt (Enroll hoặc Scan)"""
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)

    # Đọc bỏ 5 khung hình đầu tiên để cảm biến làm nóng
    for _ in range(5):
        cap.read()

    start_time = time.time()
    result = None
    known_data = load_data() if mode == "SCAN" else None

    while time.time() - start_time < timeout:
        ret, frame = cap.read()
        if not ret:
            continue

        # --- Gửi ảnh Preview cho C++ ---
        color = (0, 255, 0) if mode == "SCAN" else (0, 165, 255)
        rgba_frame = _prepare_display_frame(frame, border_color=color)
        write_frame_atomic(rgba_frame)

        # --- Xử lý AI nhận diện ---
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = detect_face_locations(frame, rgb_small_frame)

        if face_locations:
            if face_recognition_available:
                face_encodings = face_recognition.face_encodings(frame, face_locations)
            else:
                continue
                
            if not face_encodings:
                continue

            if mode == "ENROLL":
                data = load_data()
                data["encodings"].append(face_encodings[0])
                data["names"].append("Tenant_1")
                save_data(data["encodings"], data["names"])
                result = "SUCCESS"
                break
            elif mode == "SCAN" and known_data["encodings"]:
                matches = face_recognition.compare_faces(
                    known_data["encodings"], face_encodings[0],
                    tolerance=FACE_DISTANCE_THRESHOLD
                )
                if True in matches:
                    result = known_data["names"][matches.index(True)]
                    break

    cap.release()
    if os.path.exists(CAM_FRAME_PATH):
        os.remove(CAM_FRAME_PATH)
    return result


def play_video_stream():
    """Hàm đọc file video, stream hình vào RAM Disk và chạy ffplay ngầm để phát tiếng"""
    try:
        with open(FLAG_PLAY_VIDEO, "r") as f:
            video_path = f.read().strip()
    except Exception:
        return

    if not os.path.exists(video_path):
        return

    print(f"[VIDEO] Playing: {video_path}", flush=True)

    # --- PHÁT TIẾNG BẰNG FFPLAY ---
    audio_player = None
    try:
        audio_player = subprocess.Popen(
            ["sudo", "-u", "lckien", "env", "XDG_RUNTIME_DIR=/run/user/1000",
             "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", video_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    cap = cv2.VideoCapture(video_path)

    while cap.isOpened() and os.path.exists(FLAG_PLAY_VIDEO):
        ret, frame = cap.read()
        if not ret:
            break

        rgba_frame = _prepare_display_frame(frame, border_color=(255, 255, 255))
        write_frame_atomic(rgba_frame)
        time.sleep(0.045)  # ~20 FPS

    cap.release()
    if audio_player:
        try:
            audio_player.terminate()
        except Exception:
            pass

    if os.path.exists(CAM_FRAME_PATH):
        os.remove(CAM_FRAME_PATH)
    if os.path.exists(FLAG_PLAY_VIDEO):
        os.remove(FLAG_PLAY_VIDEO)
    print("[VIDEO] Playback stopped.", flush=True)


def main():
    print("[FACE_AI] Engine Ready.", flush=True)
    load_yolo_face_detector()
    while True:
        try:
            # Kiểm tra lệnh Phát Video
            if os.path.exists(FLAG_PLAY_VIDEO):
                play_video_stream()

            # Kiểm tra lệnh Record
            if os.path.exists(FLAG_RECORD_START):
                record_video()
                if os.path.exists(FLAG_RECORD_START):
                    os.remove(FLAG_RECORD_START)

            # Kiểm tra lệnh Enroll (Đăng ký mặt)
            if os.path.exists(FLAG_ENROLL_FACE):
                res = open_camera_and_scan(mode="ENROLL")
                if os.path.exists(FLAG_ENROLL_FACE):
                    os.remove(FLAG_ENROLL_FACE)
                print(f"ENROLL:{res if res else 'FAILED'}", flush=True)

            # Kiểm tra lệnh Scan (Mở cửa)
            elif os.path.exists(FLAG_SCAN_FACE):
                res = open_camera_and_scan(mode="SCAN")
                if os.path.exists(FLAG_SCAN_FACE):
                    os.remove(FLAG_SCAN_FACE)
                print(f"FACE:{res if res else 'TIMEOUT'}", flush=True)

        except Exception as e:
            print(f"[FACE_AI] Error in main loop: {e}", flush=True)
            
        time.sleep(0.2)


if __name__ == "__main__":
    main()
