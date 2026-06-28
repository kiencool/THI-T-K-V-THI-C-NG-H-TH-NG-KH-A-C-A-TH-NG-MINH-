import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.190', username='lckien', password='123456789')
cmd = "echo '{\"main_door\": false, \"delivery_box\": false}' > /tmp/door_status.json"
stdin, stdout, stderr = ssh.exec_command(cmd)
stdout.read() # Wait for completion!
print("Door status fixed AND WAITED")
