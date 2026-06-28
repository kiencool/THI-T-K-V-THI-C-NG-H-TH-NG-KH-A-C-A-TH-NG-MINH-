import os
import time
import json

class EventBridge:
    def __init__(self, socketio, log_file, events_file, history_file=None):
        self.socketio = socketio
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
        """Main loop to monitor files."""
        # Initialize file sizes/mtimes so we don't read old data
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
        """Check for new lines in the log file and emit them."""
        if not os.path.exists(self.log_file):
            return

        current_size = os.path.getsize(self.log_file)
        if current_size < self.last_log_size:
            # File was truncated/rotated
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
                            self.socketio.emit('new_log', {"raw": line})
                        except Exception:
                            pass

    def check_events(self):
        """Check for updates in the events JSON file line by line."""
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
                    if not line:
                        continue
                    try:
                        event_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                        
                    event_type = event_data.get("event")
                    if event_type:
                        detail_str = event_data.get("detail", "unknown")
                        door_name = detail_str.split(",")[0]
                        door_target = "DELIVERY BOX" if event_type == "shipper_unlock" else door_name
                        
                        # Filter out sensor bounces
                        if event_type == "door_lock" or event_type == "physical_door_close":
                            self.last_lock_time[door_target] = time.time()
                        elif event_type == "physical_door_open":
                            if time.time() - self.last_lock_time.get(door_target, 0) <= 2:
                                continue # Ignore bounce
                                
                        try:
                            self.socketio.emit('system_event', event_data)
                        except Exception:
                            pass
                        
                        # Save to history file
                        if self.history_file:
                            try:
                                history = []
                                if os.path.exists(self.history_file):
                                    with open(self.history_file, 'r', encoding='utf-8') as hf:
                                        try:
                                            history = json.load(hf)
                                        except:
                                            history = []
                                
                                # Add timestamp if missing
                                if "timestamp" not in event_data:
                                    event_data["timestamp"] = int(time.time())
                                    
                                history.append(event_data)
                                
                                # Keep only last 1000 events
                                if len(history) > 1000:
                                    history = history[-1000:]
                                    
                                with open(self.history_file, 'w', encoding='utf-8') as hf:
                                    json.dump(history, hf, ensure_ascii=False, indent=2)
                            except Exception as e:
                                print(f"Error saving history: {e}")
                        
                        # Update state tracker
                        if event_type == "physical_door_open":
                            self.door_states[door_target]["physical"] = "open"
                        elif event_type == "physical_door_close":
                            self.door_states[door_target]["physical"] = "closed"
                        elif event_type == "door_unlock" or event_type == "shipper_unlock":
                            self.door_states[door_target]["lock"] = "unlocked"
                        elif event_type == "door_lock":
                            self.door_states[door_target]["lock"] = "locked"

                        # Also emit specific events for easier frontend handling
                        try:
                            if event_type in ["door_unlock", "physical_door_open", "shipper_unlock", "door_lock", "physical_door_close"]:
                                is_open = (self.door_states[door_target]["physical"] == "open" or self.door_states[door_target]["lock"] == "unlocked")
                                self.socketio.emit('door_status', {"door": door_target, "status": "unlocked" if is_open else "locked"})
                                
                            if event_type.startswith("rfid_"):
                                self.socketio.emit('rfid_event', event_data)
                            elif event_type.startswith("face_"):
                                self.socketio.emit('face_event', event_data)
                        except Exception:
                            pass

import socketio

if __name__ == '__main__':
    # Wait for server_final_fix.py to start
    time.sleep(2)
    sio = socketio.Client()
    try:
        sio.connect('http://localhost:5000')
    except Exception as e:
        print(f"Socket.IO connection failed: {e}")
        # Continue without emitting real-time events, but still process history
        pass

    bridge = EventBridge(
        socketio=sio,
        log_file='../smart_door.log',
        events_file='/tmp/smart_door_events.json',
        history_file='/tmp/smart_door_history.json'
    )
    bridge.start_monitoring()
