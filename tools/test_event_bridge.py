import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    stdin, stdout, stderr = ssh.exec_command("cd /home/lckien/smart_door_pi && python3 event_bridge.py & sleep 1; kill $!")
    print("STDOUT:", stdout.read().decode())
    print("STDERR:", stderr.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
