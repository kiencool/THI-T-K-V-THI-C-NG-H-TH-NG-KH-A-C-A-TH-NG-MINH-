import paramiko
import time

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    print("Killing existing server...")
    ssh.exec_command("sudo pkill -f server.py")
    time.sleep(1)
    
    print("Running server directly...")
    # By running with a timeout command, we force it to exit after 5 seconds so stdout.read() doesn't block forever!
    stdin, stdout, stderr = ssh.exec_command("cd /home/lckien/smart_door_pi && timeout 5 python3 server.py")
    
    print("STDOUT:")
    print(stdout.read().decode())
    print("STDERR:")
    print(stderr.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
