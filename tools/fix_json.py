import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    sftp = ssh.open_sftp()
    
    print("Downloading server.py...")
    sftp.get("/home/lckien/smart_door_pi/server.py", "server_final.py")
    
    with open("server_final.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    if "import json" not in code:
        code = "import json\\n" + code
        
    with open("server_final.py", "w", encoding="utf-8") as f:
        f.write(code)
        
    print("Uploading server.py...")
    sftp.put("server_final.py", "/home/lckien/smart_door_pi/server.py")
    sftp.close()
    
    print("Restarting server.py...")
    ssh.exec_command("sudo pkill -f server.py && cd /home/lckien/smart_door_pi && nohup python3 server.py > web_server.log 2>&1 &")
    ssh.close()
    
    print("Done")
except Exception as e:
    print("Failed:", e)
