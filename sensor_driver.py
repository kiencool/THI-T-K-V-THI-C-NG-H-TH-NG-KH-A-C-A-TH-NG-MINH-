import time
import sys

# Thử import RPi.GPIO, nếu không có (chạy giả lập trên Windows/Mac) thì dùng mock
try:
    import RPi.GPIO as GPIO
    IS_RPI = True
except ImportError:
    IS_RPI = False

MAIN_DOOR_SENSOR = 22
DELIVERY_BOX_SENSOR = 23

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

try:
    while True:
        if IS_RPI:
            main_state = GPIO.input(MAIN_DOOR_SENSOR)
            delivery_state = GPIO.input(DELIVERY_BOX_SENSOR)
        else:
            # Mock data cho môi trường dev
            main_state = 0
            delivery_state = 0

        # Nếu trạng thái cửa chính thay đổi
        if main_state != last_main:
            # Mạch NC (Normally Closed): Khi đóng -> 1 (Hở mạch do từ trường), Khi mở -> 0 (Chập mạch)
            state_str = "CLOSED" if main_state == 1 else "OPEN"
            print(f"SENSOR:MAIN_DOOR:{state_str}", flush=True)
            last_main = main_state
            
        # Nếu trạng thái tủ đồ thay đổi
        if delivery_state != last_delivery:
            state_str = "CLOSED" if delivery_state == 1 else "OPEN"
            print(f"SENSOR:DELIVERY_BOX:{state_str}", flush=True)
            last_delivery = delivery_state
            
        # Poll mỗi 100ms
        time.sleep(0.1)

except KeyboardInterrupt:
    if IS_RPI:
        GPIO.cleanup()
    sys.exit(0)
