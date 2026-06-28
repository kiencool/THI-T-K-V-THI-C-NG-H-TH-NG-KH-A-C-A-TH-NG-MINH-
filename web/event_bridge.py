"""
Smart Door Pi — Web Event Bridge
Lắng nghe file log và file sự kiện (từ C++) để push lên web qua Socket.IO.
Chạy ngầm dưới dạng background process do main.cpp gọi.
"""
import os
import sys
import time
import json
import socketio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.config import LOG_FILE, EVENTS_FILE, HISTORY_FILE

class EventBridge:
    def __init__(self, sio, log_file, events_file, history_file):
        self.sio = sio
        self.log_file = log_file
        self.events_file = events_file
        self.history_file = history_file
        self.last_log_size = 0
        self.last_event_size = 0
        self.last_lock_time = {"MAIN DOOR": 0, "DELIVERY BOX": 0}
        self.door_states = {
            "MAIN DOOR": {"physical": "closed", "lock": "locked"},
            "DELIVERY BOX": {"physical": "closed", "lock": "locked"}
        }

    def start_monitoring(self):
        if os.path.exists(self.log_file):
            self.last_log_size = os.path.getsize(self.log_file)
        if os.path.exists(self.events_file):
            self.last_event_size = os.path.getsize(self.events_file)
            
        while True:
            try:
                self.check_logs()
            except Exception as e:
                print(f"Error in check_logs: {e}")
                
            try:
                self.check_events()
            except Exception as e:
                print(f"Error in check_events: {e}")
                
            time.sleep(0.5)

    def check_logs(self):
        if not os.path.exists(self.log_file):
            return

        current_size = os.path.getsize(self.log_file)
        if current_size < self.last_log_size:
            self.last_log_size = 0
            
        if current_size > self.last_log_size:
            with open(self.log_file, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(self.last_log_size)
                new_lines = f.readlines()
                self.last_log_size = current_size
                
                for line in new_lines:
                    line = line.strip()
                    if line:
                        try:
                            self.sio.emit('new_log', {"raw": line})
                        except Exception:
                            pass

    def check_events(self):
        if not os.path.exists(self.events_file):
            return

        current_size = os.path.getsize(self.events_file)
        if current_size < self.last_event_size:
            self.last_event_size = 0
            
        if current_size > self.last_event_size:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                f.seek(self.last_event_size)
                new_lines = f.readlines()
                self.last_event_size = current_size
                
                for line in new_lines:
                    line = line.strip()
                    if not line: continue
                    try:
                        event_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                        
                    event_type = event_data.get("event")
                    if event_type:
                        detail_str = event_data.get("detail", "unknown")
                        door_name = detail_str.split(",")[0]
                        door_target = "DELIVERY BOX" if event_type == "shipper_unlock" else door_name
                        
                        if event_type == "door_lock" or event_type == "physical_door_close":
                            self.last_lock_time[door_target] = time.time()
                        elif event_type == "physical_door_open":
                            if time.time() - self.last_lock_time.get(door_target, 0) <= 2:
                                continue # Bounce
                                
                        try:
                            self.sio.emit('system_event', event_data)
                        except Exception:
                            pass
                        
                        if self.history_file:
                            try:
                                history = []
                                if os.path.exists(self.history_file):
                                    with open(self.history_file, 'r', encoding='utf-8') as hf:
                                        try: history = json.load(hf)
                                        except: pass
                                
                                if "timestamp" not in event_data:
                                    event_data["timestamp"] = int(time.time())
                                    
                                history.append(event_data)
                                if len(history) > 1000:
                                    history = history[-1000:]
                                    
                                with open(self.history_file, 'w', encoding='utf-8') as hf:
                                    json.dump(history, hf, ensure_ascii=False, indent=2)
                            except Exception as e:
                                print(f"Error saving history: {e}")
                        
                        if event_type == "physical_door_open":
                            self.door_states[door_target]["physical"] = "open"
                        elif event_type == "physical_door_close":
                            self.door_states[door_target]["physical"] = "closed"
                        elif event_type in ["door_unlock", "shipper_unlock"]:
                            self.door_states[door_target]["lock"] = "unlocked"
                        elif event_type == "door_lock":
                            self.door_states[door_target]["lock"] = "locked"

                        try:
                            if event_type in ["door_unlock", "physical_door_open", "shipper_unlock", "door_lock", "physical_door_close"]:
                                is_open = (self.door_states[door_target]["physical"] == "open" or self.door_states[door_target]["lock"] == "unlocked")
                                self.sio.emit('door_status', {"door": door_target, "status": "unlocked" if is_open else "locked"})
                                
                            if event_type.startswith("rfid_"):
                                self.sio.emit('rfid_event', event_data)
                            elif event_type.startswith("face_"):
                                self.sio.emit('face_event', event_data)
                        except Exception:
                            pass


if __name__ == '__main__':
    time.sleep(2)
    sio = socketio.Client()
    try:
        sio.connect('http://localhost:5000')
    except Exception as e:
        print(f"Socket.IO connection failed: {e}")
        pass

    bridge = EventBridge(
        sio=sio,
        log_file=LOG_FILE,
        events_file=EVENTS_FILE,
        history_file=HISTORY_FILE
    )
    bridge.start_monitoring()
