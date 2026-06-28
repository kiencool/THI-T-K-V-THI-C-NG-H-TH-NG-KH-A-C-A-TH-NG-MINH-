import cv2
import os
import time
import pickle
import subprocess
import numpy as np

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

# --- Cấu hình đường dẫn ---
FILE_SCAN = "/tmp/scan_face"
FILE_ENROLL = "/tmp/enroll_face"
FILE_RECORD = "/tmp/record_start"
DATA_FILE = "dataset.pkl"
RAM_DISK_FILE = "/dev/shm/cam_frame.raw" 
VIDEO_DIR = "/home/lckien/smart_door_pi/messages" # Đã sửa
YOLO_DIR = "face_models"
YOLO_FACE_MODEL = os.path.join(YOLO_DIR, "yolov5-face.onnx")
YOLO_INPUT_SIZE = 640
YOLO_CONF_THRESHOLD = 0.30
YOLO_NMS_THRESHOLD = 0.40

if not os.path.exists(VIDEO_DIR):
    os.makedirs(VIDEO_DIR)

if not os.path.exists(YOLO_DIR):
    os.makedirs(YOLO_DIR)

# --- YOLO Face Detector ---
yolo_session = None
yolo_available = False

def find_model_file(root_dir, ext):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(ext):
                return os.path.join(dirpath, filename)
    return None


def export_pt_to_onnx(pt_path):
    script = os.path.join(YOLO_DIR, "yolov5-face-master", "export.py")
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
        found = find_model_file(YOLO_DIR, ".onnx")
        if found:
            model_path = found
            print(f"[FACE_AI] Found YOLO model at: {model_path}", flush=True)
        else:
            pt_found = find_model_file(YOLO_DIR, ".pt")
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
            top = y
            left = x
            bottom = y + h
            right = x + w
            results.append((top, right, bottom, left))
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

# --- Hàm ghi file an toàn (MỚI BỔ SUNG) ---
def write_frame_atomic(rgba_frame):
    """Ghi file nháp rồi đổi tên để tránh C++ đọc file dở dang gây giật/lệch hình"""
    try:
        tmp_file = RAM_DISK_FILE + ".tmp"
        with open(tmp_file, "wb") as f:
            f.write(rgba_frame.tobytes())
        os.rename(tmp_file, RAM_DISK_FILE) # Lệnh rename là nguyên tử (tức thời)
    except Exception as e:
        pass

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'rb') as f:
            return pickle.load(f)
    return {"encodings": [], "names": []}

def save_data(encodings, names):
    with open(DATA_FILE, 'wb') as f:
        pickle.dump({"encodings": encodings, "names": names}, f)
        
def record_video():
    """Hàm quay phim, thu âm rời và đồng thời gửi ảnh preview về cho giao diện LVGL"""
    # 1. Thêm cv2.CAP_V4L2 
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    
    # 2. Đọc bỏ 5 khung hình đầu tiên
    for _ in range(5):
        cap.read()
        
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    temp_video = f"{VIDEO_DIR}/temp_vid_{timestamp}.avi"
    temp_audio = f"{VIDEO_DIR}/temp_aud_{timestamp}.wav"
    final_video = f"{VIDEO_DIR}/msg_{timestamp}.avi"
    
    out = cv2.VideoWriter(temp_video, fourcc, 20.0, (640, 480))

    # --- BẮT ĐẦU THU ÂM NGẦM ---
# --- BẮT ĐẦU THU ÂM NGẦM ---
    audio_proc = subprocess.Popen(
        ["arecord", "-D", "plughw:2,0", "-f", "S16_LE", "-r", "44100", "-c", "1", temp_audio],
        stderr=subprocess.DEVNULL
    )

    print(f"[VIDEO] Start recording: {final_video}", flush=True)
    start_time = time.time()

    # Ghi hình tối đa 15 giây hoặc đến khi C++ xóa file trigger
    while os.path.exists(FILE_RECORD) and (time.time() - start_time < 15):
        ret, frame = cap.read()
        if not ret:
            break
        
        # 1. Ghi vào file video tạm
        out.write(frame)

        # 2. Xử lý ảnh Preview gửi cho LVGL
        h, w, _ = frame.shape
        min_dim = min(h, w)
        cropped = frame[h//2 - min_dim//2: h//2 + min_dim//2, w//2 - min_dim//2: w//2 + min_dim//2]
        display_frame = cv2.resize(cropped, (240, 240), interpolation=cv2.INTER_AREA)
        
        cv2.rectangle(display_frame, (5, 5), (235, 235), (0, 0, 255), 3) 
        rgba_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGBA)
        
        write_frame_atomic(rgba_frame) # Đã tối ưu ghi file nguyên tử

    cap.release()
    out.release()
    
    # --- DỪNG THU ÂM ---
    audio_proc.terminate()
    audio_proc.wait()

    # --- GHÉP HÌNH VÀ TIẾNG (CÓ BẢO VỆ CHỐNG MẤT FILE) ---
    print("[VIDEO] Merging audio and video...", flush=True)
    
    # 1. Thử ghép hình và tiếng
    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
        merge_cmd = f"ffmpeg -y -i {temp_video} -i {temp_audio} -c:v copy -c:a aac {final_video} > /dev/null 2>&1"
        os.system(merge_cmd)

    # 2. KIỂM TRA BẢO VỆ: Nếu ghép thất bại hoặc mic hỏng -> Giữ lại video gốc
    if not os.path.exists(final_video):
        print("[VIDEO] Audio/Merge failed! Saving raw video without sound...", flush=True)
        if os.path.exists(temp_video):
            os.rename(temp_video, final_video)

    # 3. Dọn dẹp file nháp
    if os.path.exists(temp_video): os.remove(temp_video)
    if os.path.exists(temp_audio): os.remove(temp_audio)
    print(f"[VIDEO] Saved: {final_video}", flush=True)

def open_camera_and_scan(mode="SCAN", timeout=10):
    """Hàm quét mặt (Enroll hoặc Scan)"""
    # 1. Thêm cv2.CAP_V4L2 để ép dùng driver gốc của Linux (Mở camera xuyên tốc < 0.5s)
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # 2. Đọc bỏ 5 khung hình đầu tiên để cảm biến làm nóng và bắt sáng
    for _ in range(5):
        cap.read()
    
    start_time = time.time()
    result = None
    known_data = load_data() if mode == "SCAN" else None

    while time.time() - start_time < timeout:
        ret, frame = cap.read()
        if not ret: continue

        # --- Gửi ảnh Preview cho C++ ---
        h, w, _ = frame.shape
        min_dim = min(h, w)
        cropped = frame[h//2 - min_dim//2: h//2 + min_dim//2, w//2 - min_dim//2: w//2 + min_dim//2]
        display_frame = cv2.resize(cropped, (240, 240), interpolation=cv2.INTER_AREA)
        
        color = (0, 255, 0) if mode == "SCAN" else (0, 165, 255) 
        cv2.rectangle(display_frame, (5, 5), (235, 235), color, 3)
        rgba_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGBA)
        
        # [ĐÃ SỬA] Dùng hàm ghi file an toàn thay vì ghi đè trực tiếp
        write_frame_atomic(rgba_frame)

        # --- Xử lý AI nhận diện ---
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = detect_face_locations(frame, rgb_small_frame)
        
        if face_locations:
            face_encodings = face_recognition.face_encodings(frame, face_locations)
            
            if mode == "ENROLL":
                data = load_data()
                data["encodings"].append(face_encodings[0])
                data["names"].append("Tenant_1") 
                save_data(data["encodings"], data["names"])
                result = "SUCCESS"
                break
            elif mode == "SCAN" and known_data["encodings"]:
                matches = face_recognition.compare_faces(known_data["encodings"], face_encodings[0], tolerance=0.45)
                if True in matches:
                    result = known_data["names"][matches.index(True)]
                    break

    cap.release()
    if os.path.exists(RAM_DISK_FILE):
        os.remove(RAM_DISK_FILE)
    return result
    
def play_video_stream():
    """Hàm đọc file video, stream hình vào RAM Disk và chạy ffplay ngầm để phát tiếng"""
    try:
        with open("/tmp/play_video", "r") as f:
            video_path = f.read().strip()
    except:
        return

    if not os.path.exists(video_path):
        return

    print(f"[VIDEO] Playing: {video_path}", flush=True)
    
    # --- PHÁT TIẾNG BẰNG FFPLAY (KHÔNG SỢ QUYỀN ROOT) ---
    audio_player = None
    try:
        audio_player = subprocess.Popen(
            ["sudo", "-u", "lckien", "env", "XDG_RUNTIME_DIR=/run/user/1000", "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", video_path], 
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        pass

    cap = cv2.VideoCapture(video_path)

    while cap.isOpened() and os.path.exists("/tmp/play_video"):
        ret, frame = cap.read()
        if not ret:
            break 

        h, w, _ = frame.shape
        min_dim = min(h, w)
        cropped = frame[h//2 - min_dim//2: h//2 + min_dim//2, w//2 - min_dim//2: w//2 + min_dim//2]
        display_frame = cv2.resize(cropped, (240, 240), interpolation=cv2.INTER_AREA)
        
        rgba_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGBA)
        write_frame_atomic(rgba_frame)

        time.sleep(0.045) # Ép delay xấp xỉ 20 FPS để khớp với hình

    cap.release()
    if audio_player:
        try:
            audio_player.terminate() # Bấm EXIT sẽ ép tắt tiếng lập tức
        except:
            pass
    
    if os.path.exists(RAM_DISK_FILE):
        os.remove(RAM_DISK_FILE)
    if os.path.exists("/tmp/play_video"):
        os.remove("/tmp/play_video") 
    print("[VIDEO] Playback stopped.", flush=True)
    
def main():
    print("[FACE_AI] Engine Ready.", flush=True)
    load_yolo_face_detector()
    while True:
        # Kiểm tra lệnh Phát Video
        if os.path.exists("/tmp/play_video"):
            play_video_stream()

        # Kiểm tra lệnh Record (Tính năng 1)
        if os.path.exists(FILE_RECORD):
            record_video()
            if os.path.exists(FILE_RECORD):
                os.remove(FILE_RECORD)

        # Kiểm tra lệnh Enroll (Đăng ký mặt)
        if os.path.exists(FILE_ENROLL):
            res = open_camera_and_scan(mode="ENROLL")
            if os.path.exists(FILE_ENROLL):
                os.remove(FILE_ENROLL)
            print(f"ENROLL:{res if res else 'FAILED'}", flush=True)

        # Kiểm tra lệnh Scan (Mở cửa)
        elif os.path.exists(FILE_SCAN):
            res = open_camera_and_scan(mode="SCAN")
            if os.path.exists(FILE_SCAN):
                os.remove(FILE_SCAN)
            print(f"FACE:{res if res else 'TIMEOUT'}", flush=True)

        time.sleep(0.2)

if __name__ == "__main__":
    main()
