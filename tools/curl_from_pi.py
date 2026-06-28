import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=20)
    
    script = """
import urllib.request
import json
try:
    response = urllib.request.urlopen('http://127.0.0.1:5000/api/history', timeout=5)
    print("API RESPONSE:", response.read().decode())
except Exception as e:
    print("API ERROR:", e)
"""
    stdin, stdout, stderr = ssh.exec_command(f'python3 -c "{script}"')
    print("Output:", stdout.read().decode())
    print("Error:", stderr.read().decode())
    ssh.close()
except Exception as e:
    print("Failed:", e)
