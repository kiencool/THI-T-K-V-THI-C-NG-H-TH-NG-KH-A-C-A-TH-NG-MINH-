import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    sftp = ssh.open_sftp()
    sftp.get("/home/lckien/smart_door_pi/web_server.log", "web_server_crash.log")
    sftp.close()
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
