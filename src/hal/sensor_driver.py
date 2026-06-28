"""
Smart Door Pi — Magnetic Sensor Driver (HAL Layer)
Đọc trạng thái cảm biến từ (Reed Switch) trên GPIO 22, 23.
Output: SENSOR:MAIN_DOOR:OPEN/CLOSED và SENSOR:DELIVERY_BOX:OPEN/CLOSED
"""
import time
import sys

# Thử import RPi.GPIO, nếu không có (giả lập trên Windows/Mac) thì dùng mock
try:
    import RPi.GPIO as GPIO
    IS_RPI = True
except ImportError:
    IS_RPI = False

MAIN_DOOR_SENSOR = 22
DELIVERY_BOX_SENSOR = 23


def main():
    if IS_RPI:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Bật điện trở kéo lên nội bộ (Pull-Up)
        # Khi cửa đóng (nam châm gần), mạch chập GND => Đọc giá trị 0
        # Khi cửa mở (nam châm xa), mạch hở => Pull-up kéo lên 3.3V => Đọc giá trị 1
        GPIO.setup(MAIN_DOOR_SENSOR, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(DELIVERY_BOX_SENSOR, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print("SENSOR_DRIVER_STARTED", flush=True)

    last_main = None
    last_delivery = None
    
    # Debounce counters
    main_consecutive = 0
    delivery_consecutive = 0
    DEBOUNCE_THRESHOLD = 5 # 5 * 20ms = 100ms

    try:
        while True:
            if IS_RPI:
                main_state = GPIO.input(MAIN_DOOR_SENSOR)
                delivery_state = GPIO.input(DELIVERY_BOX_SENSOR)
            else:
                main_state = 0
                delivery_state = 0

            # Xử lý Cửa chính (có Debounce)
            if last_main is None:
                last_main = main_state
            elif main_state != last_main:
                main_consecutive += 1
                if main_consecutive >= DEBOUNCE_THRESHOLD:
                    state_str = "OPEN" if main_state == 1 else "CLOSED"
                    print(f"SENSOR:MAIN_DOOR:{state_str}", flush=True)
                    last_main = main_state
                    main_consecutive = 0
            else:
                main_consecutive = 0

            # Xử lý Tủ đồ (có Debounce)
            if last_delivery is None:
                last_delivery = delivery_state
            elif delivery_state != last_delivery:
                delivery_consecutive += 1
                if delivery_consecutive >= DEBOUNCE_THRESHOLD:
                    state_str = "OPEN" if delivery_state == 1 else "CLOSED"
                    print(f"SENSOR:DELIVERY_BOX:{state_str}", flush=True)
                    last_delivery = delivery_state
                    delivery_consecutive = 0
            else:
                delivery_consecutive = 0

            # Poll mỗi 20ms
            time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        if IS_RPI:
            GPIO.cleanup()
        sys.exit(0)


if __name__ == "__main__":
    main()
