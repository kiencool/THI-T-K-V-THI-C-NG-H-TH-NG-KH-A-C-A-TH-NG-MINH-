#!/bin/bash
# =============================================================================
# setup_touch.sh — Bật màn hình cảm ứng trên Raspberry Pi
# Chạy: sudo bash setup_touch.sh
# =============================================================================

set -e

CONFIG_FILE="/boot/firmware/config.txt"
# Fallback cho Pi cũ dùng /boot/config.txt
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="/boot/config.txt"
fi

echo "============================================"
echo "  SMART DOOR PI — Cài đặt màn hình cảm ứng"
echo "============================================"
echo ""
echo "[INFO] File cấu hình: $CONFIG_FILE"

# --- 1. Bật driver DSI touchscreen chính thức ---
if grep -q "^dtoverlay=vc4-kms-dsi-7inch" "$CONFIG_FILE" 2>/dev/null; then
    echo "[OK] dtoverlay=vc4-kms-dsi-7inch đã có sẵn."
else
    echo "[ADD] Thêm dtoverlay=vc4-kms-dsi-7inch..."
    echo "" >> "$CONFIG_FILE"
    echo "# --- Smart Door Pi: Touchscreen ---" >> "$CONFIG_FILE"
    echo "dtoverlay=vc4-kms-dsi-7inch" >> "$CONFIG_FILE"
fi

# --- 2. Bật I2C (cần cho một số màn hình cảm ứng) ---
if grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE" 2>/dev/null; then
    echo "[OK] dtparam=i2c_arm=on đã có sẵn."
else
    echo "[ADD] Thêm dtparam=i2c_arm=on..."
    echo "dtparam=i2c_arm=on" >> "$CONFIG_FILE"
fi

# --- 3. Bật SPI (cần cho RFID MFRC522) ---
if grep -q "^dtparam=spi=on" "$CONFIG_FILE" 2>/dev/null; then
    echo "[OK] dtparam=spi=on đã có sẵn."
else
    echo "[ADD] Thêm dtparam=spi=on..."
    echo "dtparam=spi=on" >> "$CONFIG_FILE"
fi

# --- 4. Đảm bảo không bị disable_touchscreen ---
if grep -q "^disable_touchscreen=1" "$CONFIG_FILE" 2>/dev/null; then
    echo "[FIX] Tìm thấy disable_touchscreen=1, đang tắt..."
    sed -i 's/^disable_touchscreen=1/#disable_touchscreen=1/' "$CONFIG_FILE"
fi

# --- 5. Cài đặt thư viện hỗ trợ input (libinput/evdev cho SDL2) ---
echo ""
echo "[INFO] Cài đặt các gói cần thiết cho touchscreen..."
apt-get update -qq
apt-get install -y -qq libinput-tools libts-bin evtest xdotool 2>/dev/null || true

# --- 6. Cấu hình SDL2 dùng libinput thay vì X11 mouse ---
# Tạo file udev rule để đảm bảo touchscreen có quyền truy cập
UDEV_RULE="/etc/udev/rules.d/99-touch.rules"
if [ ! -f "$UDEV_RULE" ]; then
    echo "[ADD] Tạo udev rule cho touchscreen..."
    cat > "$UDEV_RULE" << 'EOF'
# Cho phép group input truy cập touchscreen
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="*touch*", MODE="0666"
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="*Touch*", MODE="0666"
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="*FT5406*", MODE="0666"
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="*goodix*", MODE="0666"
EOF
    echo "[OK] Udev rule đã tạo: $UDEV_RULE"
fi

# --- 7. Thiết lập biến môi trường SDL2 cho touchscreen ---
SDL_ENV_FILE="/etc/profile.d/sdl_touch.sh"
cat > "$SDL_ENV_FILE" << 'EOF'
# SDL2 touchscreen configuration cho Smart Door Pi
export SDL_VIDEODRIVER=kmsdrm
export SDL_MOUSE_TOUCH_EVENTS=1

# Tự động detect touch device
TOUCH_DEV=$(grep -l "touch\|Touch\|FT5406\|goodix" /sys/class/input/event*/device/name 2>/dev/null | head -1 | grep -oP 'event\d+')
if [ -n "$TOUCH_DEV" ]; then
    export SDL_TOUCH_DEVICE="/dev/input/$TOUCH_DEV"
fi
EOF
chmod +x "$SDL_ENV_FILE"
echo "[OK] SDL2 touch env đã cấu hình: $SDL_ENV_FILE"

# --- 8. Xoay màn hình nếu cần (uncomment để dùng) ---
# Nếu màn hình bị ngược, bỏ comment dòng dưới:
# echo "lcd_rotate=2" >> "$CONFIG_FILE"

echo ""
echo "============================================"
echo "  CÀI ĐẶT HOÀN TẤT!"
echo "============================================"
echo ""
echo "  Khởi động lại Pi để áp dụng thay đổi:"
echo "    sudo reboot"
echo ""
echo "  Kiểm tra touchscreen sau khi reboot:"
echo "    evtest  (chọn device touch, chạm màn hình)"
echo ""
echo "  Nếu màn hình bị ngược, chỉnh trong $CONFIG_FILE:"
echo "    lcd_rotate=2"
echo ""
