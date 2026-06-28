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
    HISTORY_FILE, WEB_COMMAND_FILE, DOOR_STATUS_FILE
)

app = Flask(__name__, static_folder='.')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

ADMIN_PASSWORD = "1"
TENANT_PASSWORD = "1"

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
    
    if role == "admin" and password == ADMIN_PASSWORD:
        return jsonify({"status": "success", "token": "admin_token"})
    elif role == "tenant" and password == TENANT_PASSWORD:
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
                    c_uid, c_name = line.split('|', 1)
                    if c_uid.strip().upper() == uid:
                        found = True
                        new_lines.append(f"{uid}|{new_name}\n")
                    else:
                        new_lines.append(line + "\n")
                        
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
        if os.path.exists(DOOR_STATUS_FILE):
            with open(DOOR_STATUS_FILE, "r") as f:
                data = json.load(f)
                main_door = "open" if data.get("main_door", False) else "locked"
                delivery_box = "open" if data.get("delivery_box", False) else "locked"
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
                    uid, time_added = line.split('|', 1)
                    cards.append({"uid": uid.strip(), "time": time_added.strip()})
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
                    c_uid, c_name = line.split('|', 1)
                    if c_uid.strip().upper() == uid:
                        return jsonify({"status": "error", "message": "Thẻ này đã tồn tại"}), 400
                    
    with open(CARDS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{uid}|{name}\n")
        
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
                    c_uid, c_name = line.split('|', 1)
                    if c_uid.strip().upper() == uid:
                        found = True
                        continue
                    new_lines.append(line + "\n")
                    
    if found:
        with open(CARDS_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        send_web_command("RELOAD_CARDS")
        return jsonify({"status": "success", "message": "Đã xóa thẻ"})
    else:
        return jsonify({"status": "error", "message": "Không tìm thấy thẻ"}), 404

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
