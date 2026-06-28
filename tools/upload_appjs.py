import paramiko
import os

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    sftp = ssh.open_sftp()
    
    base_dir = r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi"
    print("Uploading app.js...")
    sftp.put(os.path.join(base_dir, "web", "app.js"), "/home/lckien/smart_door_pi/web/app.js")
    sftp.close()
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
