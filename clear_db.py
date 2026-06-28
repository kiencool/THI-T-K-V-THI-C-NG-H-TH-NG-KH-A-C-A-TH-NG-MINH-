import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.190', username='lckien', password='123456789')
stdin, stdout, stderr = ssh.exec_command("echo '[]' > /home/lckien/smart_door_pi/data/access_history.json")
print("Error:", stderr.read().decode())
print("Output:", stdout.read().decode())
