import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time
import sys

# Tắt cảnh báo phiền phức của GPIO
GPIO.setwarnings(False)

reader = SimpleMFRC522()
print("RFID Driver Started", flush=True)

try:
    while True:
        id, text = reader.read()
        uid_hex = hex(id)[2:].upper()
        print(f"SCAN:{uid_hex}", flush=True)
        time.sleep(2)
        
except KeyboardInterrupt:
    pass
except Exception as e:
    print(f"Error: {e}", flush=True)
finally:
    # QUAN TRỌNG NHẤT: Luôn dọn dẹp phần cứng khi thoát
    GPIO.cleanup()
