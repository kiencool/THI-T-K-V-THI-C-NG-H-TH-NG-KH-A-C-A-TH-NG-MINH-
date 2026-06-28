import paramiko
import os

host = '192.168.1.190'
user = 'lckien'
pwd = '123456789'
local_path = r"c:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi\data\passwords.txt"
remote_path = "/home/lckien/smart_door_pi/data/passwords.txt"

transport = paramiko.Transport((host, 22))
transport.connect(username=user, password=pwd)
sftp = paramiko.SFTPClient.from_transport(transport)

print(f"Uploading {local_path} to {remote_path}...")
sftp.put(local_path, remote_path)

sftp.close()
transport.close()
print("Upload complete!")
