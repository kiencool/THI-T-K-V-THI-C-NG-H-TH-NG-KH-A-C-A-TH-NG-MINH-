import paramiko
import os

host = "192.168.1.190"
username = "lckien"
password = "123456789"

files_to_download = [
    ("/home/lckien/smart_door_pi/web_server.log", "web_server.log"),
    ("/home/lckien/smart_door_pi/smart_door.log", "smart_door.log"),
    ("/tmp/smart_door_events.json", "smart_door_events.json"),
    ("/home/lckien/smart_door_pi/access_history.json", "access_history.json")
]

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    sftp = ssh.open_sftp()
    for remote_file, local_file in files_to_download:
        try:
            print(f"Downloading {remote_file}...")
            sftp.get(remote_file, local_file)
        except Exception as e:
            print(f"Failed to download {remote_file}: {e}")
            with open(local_file, "w") as f:
                f.write(f"FILE NOT FOUND OR ERROR: {e}")
    sftp.close()
    
    # Let's also check if event_bridge.py is actually running!
    stdin, stdout, stderr = ssh.exec_command("ps aux | grep server.py")
    with open("ps_output.txt", "w") as f:
        f.write(stdout.read().decode())
        
    ssh.close()
    print("Done downloading logs.")
except Exception as e:
    print("Failed:", e)
