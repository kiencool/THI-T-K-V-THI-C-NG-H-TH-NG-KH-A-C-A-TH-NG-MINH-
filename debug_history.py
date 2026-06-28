import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    script = """
import os
import json
fpath = '/home/lckien/smart_door_pi/access_history.json'
try:
    print('Size:', os.path.getsize(fpath))
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print('Len:', len(data))
except Exception as e:
    print('Error:', e)
"""
    stdin, stdout, stderr = ssh.exec_command(f'python3 -c "{script}"')
    print("Output:", stdout.read().decode())
    print("Error:", stderr.read().decode())
    ssh.close()
except Exception as e:
    print("Failed:", e)
