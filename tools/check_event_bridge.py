import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    print("Checking running python processes...")
    stdin, stdout, stderr = ssh.exec_command("ps aux | grep python")
    print(stdout.read().decode())
    
    print("Checking event_bridge.log...")
    stdin, stdout, stderr = ssh.exec_command("cat /home/lckien/smart_door_pi/event_bridge.log | tail -n 20")
    print(stdout.read().decode())
    print("stderr:", stderr.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
