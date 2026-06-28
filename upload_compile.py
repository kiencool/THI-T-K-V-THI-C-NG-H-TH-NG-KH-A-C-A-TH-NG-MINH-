import paramiko
import os
import time

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    sftp = ssh.open_sftp()
    
    print("Uploading main.cpp...")
    base_dir = r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi"
    sftp.put(os.path.join(base_dir, "src", "main.cpp"), "/home/lckien/smart_door_pi/src/main.cpp")
    sftp.put(os.path.join(base_dir, "src", "ui", "ui_app.cpp"), "/home/lckien/smart_door_pi/src/ui/ui_app.cpp")
    
    # We should also make sure event_bridge.py on the Pi is updated in case I edited it locally.
    # Ah, I edited event_bridge.py earlier (adding physical_door_open logic).
    print("Uploading event_bridge.py...")
    sftp.put(os.path.join(base_dir, "event_bridge.py"), "/home/lckien/smart_door_pi/event_bridge.py")
    
    print("Uploading setup_autostart.sh...")
    sftp.put(os.path.join(base_dir, "setup_autostart.sh"), "/home/lckien/smart_door_pi/setup_autostart.sh")
    
    sftp.close()
    
    print("Compiling main.cpp...")
    stdin, stdout, stderr = ssh.exec_command("cd /home/lckien/smart_door_pi/build && make")
    print(stdout.read().decode())
    
    print("Restarting smart_door_app and services...")
    ssh.exec_command("sudo pkill -f smart_door_app")
    ssh.exec_command("sudo pkill -f event_bridge.py")
    ssh.exec_command("sudo pkill -f server_final_fix.py")
    time.sleep(1)
    
    # Update autostart script
    ssh.exec_command("cd /home/lckien/smart_door_pi && sudo bash setup_autostart.sh")
    
    # Run it cleanly using systemctl instead of nohup to avoid detaching issues
    ssh.exec_command("sudo systemctl restart smart-door")
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
