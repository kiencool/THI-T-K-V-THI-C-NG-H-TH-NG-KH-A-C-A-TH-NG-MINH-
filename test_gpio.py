import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print(f"MAIN (22): {GPIO.input(22)}")
print(f"DELIVERY (23): {GPIO.input(23)}")
GPIO.cleanup()
