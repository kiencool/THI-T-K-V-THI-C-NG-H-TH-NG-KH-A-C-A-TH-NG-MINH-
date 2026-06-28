#pragma once

// ============================================================
// Cấu hình tập trung cho hệ thống Smart Door Pi
// Tất cả hằng số được gom về đây thay vì rải rác trong mã nguồn
// ============================================================

// === GPIO Pin Configuration ===
static const int MAIN_DOOR_GPIO = 26;
static const int DELIVERY_BOX_GPIO = 27;
static const bool MAIN_DOOR_ACTIVE_HIGH = false;
static const bool DELIVERY_BOX_ACTIVE_HIGH = false;

// === Timing Constants ===
static const int LOCK_PULSE_SECONDS = 5;
static const int SCREENSAVER_TIMEOUT_MS = 30000;
static const int NOTIFICATION_DURATION_MS = 2500;
static const int CAM_REFRESH_MS = 30;
static const int MAIN_LOOP_SLEEP_US = 5000;
static const int RFID_ENROLL_TIMEOUT_SEC = 5;
static const int RELAY_SETTLE_MS = 200;
static const int RELAY_SOFT_RELEASE_MS = 50;
static const int DRIVER_CLEANUP_DELAY_US = 200000;

// === Display ===
static const int SCREEN_WIDTH = 800;
static const int SCREEN_HEIGHT = 480;
static const int CAM_W = 240;
static const int CAM_H = 240;

// === File Paths ===
static const char* EVENTS_FILE = "/tmp/smart_door_events.json";
static const char* DOOR_STATUS_FILE = "/tmp/door_status.json";
static const char* WEB_COMMAND_FILE = "/tmp/web_command.txt";
static const char* CAM_FRAME_PATH = "/dev/shm/cam_frame.raw";
static const char* RFID_CARDS_FILE = "../data/rfid_cards.txt";
static const char* DELIVERY_CODES_FILE = "../data/delivery_codes.txt";
static const char* MESSAGES_DIR = "../messages";

// === IPC Flag Files ===
static const char* FLAG_SCAN_FACE = "/tmp/scan_face";
static const char* FLAG_ENROLL_FACE = "/tmp/enroll_face";
static const char* FLAG_RECORD_START = "/tmp/record_start";
static const char* FLAG_PLAY_VIDEO = "/tmp/play_video";

// === Authentication ===
static const char* ADMIN_CARD_UID = "76 19 75 A6 BC";
static const char* PASSWORDS_FILE = "../data/passwords.txt";

// === Driver Paths ===
static const char* RFID_DRIVER_PATH = "python3 ../src/hal/rfid_driver.py";
static const char* FACE_ENGINE_PATH = "python3 ../src/drivers/face_engine.py";
static const char* SENSOR_DRIVER_PATH = "python3 ../src/hal/sensor_driver.py";
static const char* WEB_SERVER_PATH = "python3 ../web/server.py";
static const char* EVENT_BRIDGE_PATH = "python3 ../web/event_bridge.py";
