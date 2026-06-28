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
    
    # Upload web files
    base_dir = r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi"
    
    print("Uploading app.js...")
    sftp.put(os.path.join(base_dir, "web", "app.js"), "/home/lckien/smart_door_pi/web/app.js")
    
    print("Uploading index.html...")
    sftp.put(os.path.join(base_dir, "web", "index.html"), "/home/lckien/smart_door_pi/web/index.html")
    
    print("Uploading server.py...")
    sftp.put(os.path.join(base_dir, "server_final_fix.py"), "/home/lckien/smart_door_pi/server.py")
    
    sftp.close()
    
    print("Restarting server.py...")
    ssh.exec_command("sudo pkill -f server.py && cd /home/lckien/smart_door_pi && nohup python3 server.py > web_server.log 2>&1 &")
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
