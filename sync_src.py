import paramiko
import os

host = '192.168.1.190'
user = 'lckien'
pwd = '123456789'
local_dir = r"c:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi\src"
remote_dir = "/home/lckien/smart_door_pi/src"

files_to_sync = [
    "config/config.h",
    "services/auth_service.h",
    "services/auth_service.cpp",
    "ipc/ipc_bridge.h",
    "ipc/ipc_bridge.cpp",
    "main.cpp",
    "ui/ui_manager.cpp"
]

transport = paramiko.Transport((host, 22))
transport.connect(username=user, password=pwd)
sftp = paramiko.SFTPClient.from_transport(transport)

for f in files_to_sync:
    local_path = os.path.join(local_dir, f).replace('/', '\\')
    remote_path = f"{remote_dir}/{f}"
    print(f"Uploading {local_path} to {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()
transport.close()
print("Upload complete!")
