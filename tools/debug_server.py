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
with open('/home/lckien/smart_door_pi/server.py', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '@app.route(\\'/api/history\\')' in line:
        print("FOUND at", i)
        print("".join(lines[i:i+15]))
        break
"""
    stdin, stdout, stderr = ssh.exec_command("python3 -c \"{}\"".format(script.replace('\n', '\\n').replace('"', '\\"')))
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print("Failed:", e)
