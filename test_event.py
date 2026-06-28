import paramiko
import time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.190', username='lckien', password='123456789')
cmd = f"echo '{{\"event\":\"door_unlock\",\"detail\":\"SYSTEM TEST\",\"timestamp\":{int(time.time())}}}' >> /tmp/smart_door_events.json"
ssh.exec_command(cmd)
print("Event injected")
