import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    print("Checking if server.py is running...")
    stdin, stdout, stderr = ssh.exec_command("ps aux | grep server.py")
    print(stdout.read().decode())
    
    # If not running, start it
    ssh.exec_command("cd /home/lckien/smart_door_pi && nohup python3 server.py > web_server.log 2>&1 &")
    import time
    time.sleep(3)
    
    print("Curling API...")
    script = """
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:5000/api/history', timeout=5)
    print(r.read().decode())
except Exception as e:
    print(e)
"""
    stdin, stdout, stderr = ssh.exec_command(f"python3 -c \\\"{script}\\\"")
    print("API RESPONSE:", stdout.read().decode())
    print("API ERROR:", stderr.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
