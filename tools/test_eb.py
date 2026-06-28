import paramiko
import time

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    print("Injecting event...")
    cmd = 'echo \'{"event":"door_unlock","detail":"MAIN DOOR,gpio=26","timestamp":1781455500}\' >> /tmp/smart_door_events.json'
    ssh.exec_command(cmd)
    
    time.sleep(2)
    
    print("Reading access_history.json...")
    stdin, stdout, stderr = ssh.exec_command('cat /home/lckien/smart_door_pi/access_history.json')
    print(stdout.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
