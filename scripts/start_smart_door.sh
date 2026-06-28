#!/bin/bash
# =============================================================================
# start_smart_door.sh — Wrapper khởi động Smart Door App
# Được gọi bởi systemd service, KHÔNG chạy trực tiếp
# =============================================================================

APP_DIR="/home/lckien/smart_door_pi"
APP_BIN="$APP_DIR/build/smart_door_app"
LOG_FILE="$APP_DIR/data/smart_door.log"

export SDL_MOUSE_TOUCH_EVENTS=1

# Tự động detect touch device
TOUCH_DEV=$(grep -l "touch\|Touch\|FT5406\|goodix" /sys/class/input/event*/device/name 2>/dev/null | head -1 | grep -oP 'event\d+')
if [ -n "$TOUCH_DEV" ]; then
    export SDL_TOUCH_DEVICE="/dev/input/$TOUCH_DEV"
    echo "[TOUCH] Detected: /dev/input/$TOUCH_DEV"
fi

# --- Cleanup: Kill các process cũ nếu còn sót ---
pkill -f smart_door_app 2>/dev/null || true
pkill -f face_engine.py 2>/dev/null || true
pkill -f rfid_driver.py 2>/dev/null || true
pkill -f sensor_driver.py 2>/dev/null || true
pkill -f server.py 2>/dev/null || true
pkill -f event_bridge.py 2>/dev/null || true
sleep 1

echo "[BOOT] Chờ hardware khởi tạo..."
sleep 3

# --- Khởi chạy app chính (app này sẽ tự bật web_server qua ProcessManager) ---
cd "$APP_DIR/build"
echo "[START] $(date) — Khởi động Smart Door App..."
exec "$APP_BIN" 2>&1
