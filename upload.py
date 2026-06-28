import paramiko
import time
import sys

host = "192.168.1.190"
username = "lckien"
password = "123456789"

files_to_upload = [
    (r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi\event_bridge.py", "/home/lckien/smart_door_pi/event_bridge.py"),
    (r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi\web\app.js", "/home/lckien/smart_door_pi/web/app.js"),
    (r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi\src\main.cpp", "/home/lckien/smart_door_pi/src/main.cpp")
]

try:
    print("Connecting to SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    print("Opening SFTP...")
    sftp = ssh.open_sftp()
    for local_file, remote_file in files_to_upload:
        print(f"Uploading {local_file} to {remote_file}...")
        sftp.put(local_file, remote_file)
    sftp.close()
    
    print("Rebuilding C++ code...")
    stdin, stdout, stderr = ssh.exec_command("cd ~/smart_door_pi/build && make")
    print("Make output:", stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("Make errors:", err)
    
    print("Rebooting the Pi...")
    stdin, stdout, stderr = ssh.exec_command("echo 123456789 | sudo -S reboot")
    time.sleep(1) # wait for command to send
    
    ssh.close()
    print("Done! The Pi is rebooting.")
except Exception as e:
    print("Failed:", e)
