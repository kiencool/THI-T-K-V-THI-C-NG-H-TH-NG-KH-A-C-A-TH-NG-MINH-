import paramiko
import time

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    # Start the server properly
    print("Starting server.py...")
    ssh.exec_command("cd /home/lckien/smart_door_pi && nohup python3 server.py > web_server.log 2>&1 &")
    
    time.sleep(2)
    
    print("Checking if it's running...")
    stdin, stdout, stderr = ssh.exec_command("ps aux | grep server.py")
    print(stdout.read().decode())
    
    # Let's run a curl locally on the Pi using a pure bash command instead of python to avoid syntax issues!
    print("Curling from Pi...")
    stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:5000/api/history")
    print("CURL OUTPUT:")
    print(stdout.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
