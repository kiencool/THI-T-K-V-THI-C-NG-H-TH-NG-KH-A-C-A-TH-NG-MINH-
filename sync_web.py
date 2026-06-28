import paramiko
import os

host = '192.168.1.190'
user = 'lckien'
pwd = '123456789'
local_dir = r"c:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi\web"
remote_dir = "/home/lckien/smart_door_pi/web"

files_to_sync = ["server.py", "index.html", "app.js"]

transport = paramiko.Transport((host, 22))
transport.connect(username=user, password=pwd)
sftp = paramiko.SFTPClient.from_transport(transport)

for f in files_to_sync:
    local_path = os.path.join(local_dir, f)
    remote_path = f"{remote_dir}/{f}"
    print(f"Uploading {local_path} to {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()
transport.close()
print("Upload complete!")
