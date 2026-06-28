"""
Smart Door Pi — Web Server (Flask)
Phục vụ giao diện web, xử lý REST API, Socket.IO
Chạy ngầm bằng main.cpp
"""
import json
import os
import sys
import uuid
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.config import (
    LOG_FILE, EVENTS_FILE, CARDS_FILE, DELIVERY_CODES_FILE,
    HISTORY_FILE, WEB_COMMAND_FILE, DOOR_STATUS_FILE, DATASET_FILE, MESSAGES_DIR
)

app = Flask(__name__, static_folder='.')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

PASSWORDS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'passwords.txt')

def load_passwords():
    pwds = {
        "WEB_ADMIN": "1",
        "WEB_TENANT": "1",
        "DOOR_MAIN": "123456",
        "DOOR_ADMIN": "190104"
    }
    if os.path.exists(PASSWORDS_FILE):
        try:
            with open(PASSWORDS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '|' in line:
                        k, v = line.split('|', 1)
                        pwds[k.strip()] = v.strip()
        except Exception:
            pass
    return pwds

def send_web_command(cmd):
    try:
        tmp_name = WEB_COMMAND_FILE + "_" + str(uuid.uuid4())
        with open(tmp_name, "w") as f:
            f.write(cmd)
        os.rename(tmp_name, WEB_COMMAND_FILE)
    except Exception as e:
        print(f"Failed to send command {cmd}: {e}")

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    password = data.get("password", "")
    role = data.get("role", "admin")
    
    pwds = load_passwords()
    
    if role == "admin" and password == pwds.get("WEB_ADMIN", "1"):
        return jsonify({"status": "success", "token": "admin_token"})
    elif role == "tenant" and password == pwds.get("WEB_TENANT", "1"):
        return jsonify({"status": "success", "token": "tenant_token"})
    return jsonify({"status": "error", "message": "Sai mật khẩu"}), 401

@app.route('/api/cards/<uid>', methods=['PUT'])
def edit_card(uid):
    uid = uid.strip().upper()
    data = request.json
    new_name = data.get("name", "").strip()
    
    if not new_name:
        return jsonify({"status": "error", "message": "Tên không được để trống"}), 400
        
    found = False
    new_lines = []
    if os.path.exists(CARDS_FILE):
        with open(CARDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line:
                    parts = line.split('|')
                    c_uid = parts[0].strip()
                    c_time = parts[1].strip() if len(parts) > 1 else ""
                    # if c_time is not a date (e.g. legacy data), move it to name
                    if c_time and "-" not in c_time:
                        c_name = c_time
                        c_time = "2026-06-28 00:00:00"
                    else:
                        c_name = parts[2].strip() if len(parts) > 2 else ""

                    if c_uid.upper() == uid:
                        found = True
                        new_lines.append(f"{uid}|{c_time}|{new_name}\n")
                    else:
                        new_lines.append(f"{c_uid}|{c_time}|{c_name}\n")
                        
    if found:
        with open(CARDS_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        send_web_command("RELOAD_CARDS")
        return jsonify({"status": "success", "message": "Đã đổi tên thẻ"})
    else:
        return jsonify({"status": "error", "message": "Không tìm thấy thẻ"}), 404

@app.route('/api/delivery_codes', methods=['GET'])
def get_delivery_codes():
    codes = []
    if os.path.exists(DELIVERY_CODES_FILE):
        with open(DELIVERY_CODES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split('|', 1)
                    code = parts[0]
                    creator = parts[1] if len(parts) > 1 else "Không rõ"
                    codes.append({"code": code, "creator": creator})
    return jsonify({"status": "success", "codes": codes})

@app.route('/api/delivery_codes', methods=['POST'])
def create_delivery_code():
    data = request.json
    code = data.get("code", "").strip()
    creator = data.get("creator", "").strip()
    
    if not code or not code.isdigit() or len(code) < 4:
        return jsonify({"status": "error", "message": "Mã phải là số và có ít nhất 4 chữ số"}), 400
    if not creator:
        creator = "Không rõ"
        
    with open(DELIVERY_CODES_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{code}|{creator}\n")
        
    return jsonify({"status": "success", "message": "Đã tạo mã đơn hàng thành công", "code": code})

@app.route('/api/delivery_codes/<code>', methods=['DELETE'])
def delete_delivery_code(code):
    code = code.strip()
    found = False
    new_lines = []
    
    if os.path.exists(DELIVERY_CODES_FILE):
        with open(DELIVERY_CODES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split('|', 1)
                    if parts[0] == code:
                        found = True
                        continue
                    new_lines.append(line + "\n")
                
    if found:
        with open(DELIVERY_CODES_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return jsonify({"status": "success", "message": "Đã xóa mã"})
    else:
        return jsonify({"status": "error", "message": "Không tìm thấy mã"}), 404

@app.route('/api/settings/password', methods=['PUT'])
def change_password():
    data = request.json
    pwd_type = data.get("type", "")
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")
    
    if not pwd_type or not new_pwd:
        return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ"}), 400
        
    pwds = load_passwords()
    
    # Map from UI type to File Key
    key_map = {
        "web_admin": "WEB_ADMIN",
        "web_tenant": "WEB_TENANT",
        "door_main": "DOOR_MAIN",
        "door_admin": "DOOR_ADMIN"
    }
    
    if pwd_type not in key_map:
        return jsonify({"status": "error", "message": "Loại mật khẩu không đúng"}), 400
        
    file_key = key_map[pwd_type]
    
    if pwds.get(file_key) != old_pwd:
        return jsonify({"status": "error", "message": "Mật khẩu cũ không chính xác!"}), 401
        
    # Update dictionary
    pwds[file_key] = new_pwd
    
    # Save back to file
    try:
        with open(PASSWORDS_FILE, 'w', encoding='utf-8') as f:
            for k, v in pwds.items():
                f.write(f"{k}|{v}\n")
        
        # Signal C++ app to reload if door passwords changed
        if file_key.startswith("DOOR_"):
            send_web_command("RELOAD_PASSWORDS")
            
        return jsonify({"status": "success", "message": "Đã cập nhật mật khẩu thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500

@app.route('/api/history', methods=['GET', 'DELETE'])
def get_history():
    if request.method == 'DELETE':
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                return jsonify({"status": "success", "message": "Đã xóa toàn bộ lịch sử"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        return jsonify({"status": "success", "message": "Lịch sử đã trống"})
        
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            pass
    return jsonify({"status": "success", "history": list(reversed(history))[:100]})

@app.route('/api/door/control', methods=['POST'])
def control_door():
    data = request.json
    door = data.get("door", "")
    action = data.get("action", "")
    
    cmd_map = {
        "unlock": {"main": "TRIGGER_MAIN_DOOR", "delivery": "TRIGGER_DELIVERY_BOX", "all": "UNLOCK_ALL"},
        "lock": {"main": "LOCK_MAIN_DOOR", "delivery": "LOCK_DELIVERY_BOX", "all": "LOCK_ALL"}
    }
    
    if action in cmd_map and door in cmd_map[action]:
        send_web_command(cmd_map[action][door])
        return jsonify({"status": "success", "message": "Đã gửi lệnh " + action})
            
    return jsonify({"status": "error", "message": "Invalid parameters"}), 400

@app.route('/api/status')
def get_status():
    main_door = "locked"
    delivery_box = "locked"
    try:
        if os.path.exists("/tmp/door_status_web.json"):
            with open("/tmp/door_status_web.json", "r") as f:
                data = json.load(f)
                main_door = data.get("main_door", "locked")
                delivery_box = data.get("delivery_box", "locked")
    except Exception:
        pass

    return jsonify({
        "status": "online",
        "main_door": main_door,
        "delivery_box": delivery_box,
        "uptime": "running"
    })

@app.route('/api/cards', methods=['GET'])
def get_cards():
    cards = []
    if os.path.exists(CARDS_FILE):
        with open(CARDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line:
                    parts = line.split('|')
                    uid = parts[0].strip()
                    time_added = parts[1].strip() if len(parts) > 1 else ""
                    # Data migration for legacy
                    if time_added and "-" not in time_added:
                        name = time_added
                        time_added = "Unknown"
                    else:
                        name = parts[2].strip() if len(parts) > 2 else ""
                        
                    cards.append({"uid": uid, "time": time_added, "name": name})
    return jsonify({"status": "success", "cards": cards})

@app.route('/api/cards', methods=['POST'])
def add_card():
    data = request.json
    uid = data.get("uid", "").strip().upper()
    name = data.get("name", "").strip()
    
    if not uid or not name:
        return jsonify({"status": "error", "message": "UID và Tên không được để trống"}), 400
        
    if os.path.exists(CARDS_FILE):
        with open(CARDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line:
                    parts = line.split('|')
                    c_uid = parts[0].strip()
                    if c_uid.upper() == uid:
                        return jsonify({"status": "error", "message": "Thẻ này đã tồn tại"}), 400
                    
    from datetime import datetime
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CARDS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{uid}|{time_str}|{name}\n")
        
    send_web_command("RELOAD_CARDS")
    return jsonify({"status": "success", "message": "Đã thêm thẻ thành công"})

@app.route('/api/cards/<uid>', methods=['DELETE'])
def delete_card(uid):
    uid = uid.strip().upper()
    found = False
    new_lines = []
    
    if os.path.exists(CARDS_FILE):
        with open(CARDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line:
                    parts = line.split('|')
                    c_uid = parts[0].strip()
                    if c_uid.upper() == uid:
                        found = True
                    else:
                        new_lines.append(line + "\n")
                    
    if found:
        with open(CARDS_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        send_web_command("RELOAD_CARDS")
        return jsonify({"status": "success", "message": "Đã xóa thẻ"})
    else:
        return jsonify({"status": "error", "message": "Không tìm thấy thẻ"}), 404

@app.route('/api/faces', methods=['GET'])
def get_faces():
    faces = []
    if os.path.exists(DATASET_FILE):
        try:
            import pickle
            with open(DATASET_FILE, 'rb') as f:
                data = pickle.load(f)
                names = data.get("names", [])
                for i, name in enumerate(names):
                    faces.append({"id": i, "name": name})
        except Exception as e:
            print("Error loading faces:", e)
    return jsonify({"status": "success", "faces": faces})

@app.route('/api/faces/<int:face_id>', methods=['PUT'])
def edit_face(face_id):
    data_payload = request.json
    new_name = data_payload.get("name", "").strip()
    
    if not new_name:
        return jsonify({"status": "error", "message": "Tên không được để trống"}), 400
        
    if os.path.exists(DATASET_FILE):
        try:
            import pickle
            with open(DATASET_FILE, 'rb') as f:
                data = pickle.load(f)
            
            if 0 <= face_id < len(data.get("names", [])):
                data["names"][face_id] = new_name
                with open(DATASET_FILE, 'wb') as f:
                    pickle.dump(data, f)
                return jsonify({"status": "success", "message": "Đã đổi tên khuôn mặt"})
            else:
                return jsonify({"status": "error", "message": "Không tìm thấy khuôn mặt"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi hệ thống: {e}"}), 500
    return jsonify({"status": "error", "message": "Dữ liệu chưa khởi tạo"}), 404

@app.route('/api/faces/<int:face_id>', methods=['DELETE'])
def delete_face(face_id):
    if os.path.exists(DATASET_FILE):
        try:
            import pickle
            with open(DATASET_FILE, 'rb') as f:
                data = pickle.load(f)
            
            names = data.get("names", [])
            encodings = data.get("encodings", [])
            
            if 0 <= face_id < len(names):
                del names[face_id]
                if face_id < len(encodings):
                    del encodings[face_id]
                
                with open(DATASET_FILE, 'wb') as f:
                    pickle.dump({"names": names, "encodings": encodings}, f)
                return jsonify({"status": "success", "message": "Đã xóa khuôn mặt"})
            else:
                return jsonify({"status": "error", "message": "Không tìm thấy khuôn mặt"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi hệ thống: {e}"}), 500
    return jsonify({"status": "error", "message": "Dữ liệu chưa khởi tạo"}), 404

@app.route('/messages/<path:filename>')
def serve_message_file(filename):
    return send_from_directory(MESSAGES_DIR, filename)

@app.route('/api/messages', methods=['GET'])
def get_messages():
    messages = []
    if os.path.exists(MESSAGES_DIR):
        for f in os.listdir(MESSAGES_DIR):
            if f.endswith('.avi') or f.endswith('.mp4'):
                path = os.path.join(MESSAGES_DIR, f)
                stat = os.stat(path)
                messages.append({
                    "filename": f,
                    "size": stat.st_size,
                    "time": stat.st_mtime
                })
        messages.sort(key=lambda x: x['time'], reverse=True)
    return jsonify({"status": "success", "messages": messages})

@app.route('/api/messages/<filename>', methods=['DELETE'])
def delete_message(filename):
    path = os.path.join(MESSAGES_DIR, filename)
    if os.path.exists(path) and path.startswith(MESSAGES_DIR):
        try:
            os.remove(path)
            return jsonify({"status": "success", "message": "Đã xóa lời nhắn"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error", "message": "Không tìm thấy file"}), 404

@app.route('/api/logs')
def get_logs():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            for line in reversed(lines[-50:]):
                logs.append({"raw": line.strip()})
    return jsonify({"logs": logs})


if __name__ == '__main__':
    print("Starting Smart Door Web Server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
