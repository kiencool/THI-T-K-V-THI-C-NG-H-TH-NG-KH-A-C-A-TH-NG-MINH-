import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    script = """
import sys
import re

with open('/home/lckien/smart_door_pi/server.py', 'r') as f:
    code = f.read()

# Replace the history exception block to return the error!
code = code.replace(
    "except Exception:\\n            history = []",
    "except Exception as e:\\n            return jsonify({'status': 'error', 'message': str(e)})"
)

with open('/home/lckien/smart_door_pi/server.py', 'w') as f:
    f.write(code)
"""
    ssh.exec_command(f'python3 -c "{script}"')
    
    ssh.exec_command("sudo pkill -f server.py && cd /home/lckien/smart_door_pi && nohup python3 server.py > web_server.log 2>&1 &")
    
    ssh.close()
    print("Restarting server.py...")
except Exception as e:
    print("Failed:", e)
