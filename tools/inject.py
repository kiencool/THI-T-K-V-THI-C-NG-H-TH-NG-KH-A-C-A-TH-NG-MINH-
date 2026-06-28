import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.190', username='lckien', password='123456789')
cmd = "echo '{\"event\":\"door_lock\",\"detail\":\"MAIN DOOR\",\"timestamp\":1781555555}' | sudo tee -a /tmp/smart_door_events.json"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
