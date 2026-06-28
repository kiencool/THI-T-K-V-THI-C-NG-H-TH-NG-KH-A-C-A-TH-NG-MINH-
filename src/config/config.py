"""
Smart Door Pi — Centralized Configuration (Python)
Tập trung tất cả đường dẫn và hằng số, thay thế hardcode /home/lckien/
"""
import os

# === Base Directory (tự động detect từ vị trí file config.py trong src/config/) ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# === Data Paths ===
DATA_DIR = os.path.join(BASE_DIR, "data")
MESSAGES_DIR = os.path.join(BASE_DIR, "messages")
MODELS_DIR = os.path.join(BASE_DIR, "models")

DATASET_FILE = os.path.join(DATA_DIR, "dataset.pkl")
DELIVERY_CODES_FILE = os.path.join(DATA_DIR, "delivery_codes.txt")
CARDS_FILE = os.path.join(DATA_DIR, "rfid_cards.txt")
HISTORY_FILE = os.path.join(DATA_DIR, "access_history.json")
LOG_FILE = os.path.join(DATA_DIR, "smart_door.log") # Chuyển log file vào data/ luôn cho gọn

# === AI Model ===
YOLO_FACE_MODEL = os.path.join(MODELS_DIR, "yolov5n.onnx")
YOLO_INPUT_SIZE = 640
YOLO_CONF_THRESHOLD = 0.30
YOLO_NMS_THRESHOLD = 0.40
FACE_DISTANCE_THRESHOLD = 0.45

# === IPC Flag Files ===
EVENTS_FILE = "/tmp/smart_door_events.json"
WEB_COMMAND_FILE = "/tmp/web_command.txt"
DOOR_STATUS_FILE = "/tmp/door_status.json"

FLAG_SCAN_FACE = "/tmp/scan_face"
FLAG_ENROLL_FACE = "/tmp/enroll_face"
FLAG_RECORD_START = "/tmp/record_start"
FLAG_PLAY_VIDEO = "/tmp/play_video"

# === Camera / Display ===
CAM_FRAME_PATH = "/dev/shm/cam_frame.raw"
CAM_DISPLAY_SIZE = 240
VIDEO_MAX_DURATION = 15  # seconds
VIDEO_FPS = 20.0
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480

# === Audio ===
AUDIO_DEVICE = "plughw:2,0"
AUDIO_SAMPLE_RATE = "44100"

# Tạo thư mục data nếu chưa tồn tại
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MESSAGES_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
