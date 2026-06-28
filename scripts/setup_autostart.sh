#!/bin/bash
# =============================================================================
# setup_autostart.sh — Cài đặt tự động chạy Smart Door App khi khởi động Pi
# Chạy: sudo bash setup_autostart.sh
# =============================================================================

set -e

# --- CẤU HÌNH (Tự detect user và đường dẫn) ---
RUN_USER="${SUDO_USER:-$(whoami)}"     # Tự detect user thật (không phải root)
RUN_HOME=$(eval echo ~$RUN_USER)
APP_DIR="$RUN_HOME/smart_door_pi"      # Thư mục project trên Pi
APP_BIN="$APP_DIR/build/smart_door_app" # File thực thi sau khi build
SERVICE_NAME="smart-door"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "============================================"
echo "  SMART DOOR PI — Cài đặt Auto-Start"
echo "============================================"
echo ""

# --- 1. Kiểm tra file thực thi ---
if [ ! -f "$APP_BIN" ]; then
    echo "[WARN] Chưa tìm thấy $APP_BIN"
    echo "[INFO] Đang build app..."
    
    mkdir -p "$APP_DIR/build"
    cd "$APP_DIR/build"
    cmake ..
    make -j$(nproc)
    
    if [ ! -f "$APP_BIN" ]; then
        echo "[ERROR] Build thất bại! Kiểm tra lại source code."
        exit 1
    fi
    echo "[OK] Build thành công: $APP_BIN"
fi

# --- 2. Tạo wrapper script (xử lý env vars, cleanup) ---
WRAPPER_SCRIPT="$APP_DIR/start_smart_door.sh"
cat > "$WRAPPER_SCRIPT" << WRAPPER_EOF
#!/bin/bash
# =============================================================================
# start_smart_door.sh — Wrapper khởi động Smart Door App
# Được gọi bởi systemd service, KHÔNG chạy trực tiếp
# =============================================================================

APP_DIR="${APP_DIR}"
APP_BIN="\$APP_DIR/build/smart_door_app"
LOG_FILE="\$APP_DIR/smart_door.log"

# --- Cấu hình SDL2 cho hiển thị trên Desktop (X11) ---
export DISPLAY=:0
export XAUTHORITY=/home/lckien/.Xauthority
# export SDL_VIDEODRIVER=kmsdrm # Bỏ kmsdrm vì Pi đang chạy LXDE Desktop
export SDL_MOUSE_TOUCH_EVENTS=1

# Tự động detect touch device
TOUCH_DEV=\$(grep -l "touch\|Touch\|FT5406\|goodix" /sys/class/input/event*/device/name 2>/dev/null | head -1 | grep -oP 'event\d+')
if [ -n "\$TOUCH_DEV" ]; then
    export SDL_TOUCH_DEVICE="/dev/input/\$TOUCH_DEV"
    echo "[TOUCH] Detected: /dev/input/\$TOUCH_DEV"
fi

# --- Cleanup: Kill các process cũ nếu còn sót ---
pkill -f smart_door_app 2>/dev/null || true
pkill -f face_driver.py 2>/dev/null || true
pkill -f rfid_driver.py 2>/dev/null || true
pkill -f sensor_driver.py 2>/dev/null || true
pkill -f server_final_fix.py 2>/dev/null || true
pkill -f server.py 2>/dev/null || true
sleep 1

# --- Chờ hardware sẵn sàng (camera, SPI, display) ---
echo "[BOOT] Chờ hardware khởi tạo..."
sleep 3

# --- Chạy app ---
cd "\$APP_DIR/build"
echo "[START] \$(date) — Khởi động Smart Door App..."
exec "\$APP_BIN" 2>&1
WRAPPER_EOF

chmod +x "$WRAPPER_SCRIPT"
echo "[OK] Wrapper script: $WRAPPER_SCRIPT"

# --- 3. Tạo systemd service ---
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Smart Door Pi — Khóa cửa thông minh
After=graphical.target systemd-logind.service
Wants=graphical.target network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${APP_DIR}/build
ExecStart=${WRAPPER_SCRIPT}
Restart=on-failure
RestartSec=5

# Cho phép truy cập GPIO, SPI, I2C, camera, display
SupplementaryGroups=gpio spi i2c video input render

# Logging
StandardOutput=append:${APP_DIR}/smart_door.log
StandardError=append:${APP_DIR}/smart_door.log

# Tăng giới hạn file descriptors (cần cho camera/video)
LimitNOFILE=4096

# Tự động tạo /dev/shm nếu cần
ReadWritePaths=/dev/shm /tmp ${APP_DIR}

[Install]
WantedBy=multi-user.target
EOF

echo "[OK] Service file: $SERVICE_FILE"

# --- 4. Kích hoạt service ---
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

echo ""
echo "============================================"
echo "  CÀI ĐẶT HOÀN TẤT!"
echo "============================================"
echo ""
echo "  Các lệnh quản lý service:"
echo ""
echo "    Khởi động ngay:    sudo systemctl start $SERVICE_NAME"
echo "    Dừng:              sudo systemctl stop $SERVICE_NAME"
echo "    Xem trạng thái:    sudo systemctl status $SERVICE_NAME"
echo "    Xem log:           tail -f $APP_DIR/smart_door.log"
echo "    Tắt auto-start:    sudo systemctl disable $SERVICE_NAME"
echo ""
echo "  App sẽ TỰ ĐỘNG chạy khi Pi khởi động!"
echo "  Nếu app crash, systemd sẽ tự restart sau 5 giây."
echo ""
echo "  Để test ngay:"
echo "    sudo systemctl start $SERVICE_NAME"
echo "    sudo systemctl status $SERVICE_NAME"
echo ""
