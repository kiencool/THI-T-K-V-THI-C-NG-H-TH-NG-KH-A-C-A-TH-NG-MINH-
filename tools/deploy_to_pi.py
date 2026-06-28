import paramiko
import os
import sys

host = "192.168.1.190"
username = "lckien"
password = "123456789"
base_dir = r"C:\Users\ADMIN\OneDrive - MSFT\Desktop\smart_door_pi"
zip_file = os.path.join(base_dir, "update_unix.zip")

def run_cmd(ssh, cmd):
    print(f"[Pi] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    for line in iter(stdout.readline, ""):
        print(line, end="")
    err = stderr.read().decode()
    if err:
        print("STDERR:", err)
    
    status = stdout.channel.recv_exit_status()
    if status != 0:
        print(f"Command failed with status {status}")
        sys.exit(1)

try:
    print("Connecting to Pi...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    print("Uploading update_unix.zip...")
    sftp = ssh.open_sftp()
    sftp.put(zip_file, "/home/lckien/smart_door_pi/update_unix.zip")
    sftp.close()
    print("Upload complete!")

    print("Cleaning up old garbage files...")
    ssh.exec_command("cd /home/lckien/smart_door_pi && rm -f *\\\\*")

    print("Unzipping on Pi (using sudo)...")
    run_cmd(ssh, f"cd /home/lckien/smart_door_pi && echo {password} | sudo -S unzip -o update_unix.zip")
    run_cmd(ssh, f"cd /home/lckien/smart_door_pi && echo {password} | sudo -S chown -R lckien:lckien .")
    
    print("Ensuring scripts are executable...")
    run_cmd(ssh, "cd /home/lckien/smart_door_pi && chmod +x scripts/*.sh")
    
    print("Compiling C++ Project...")
    run_cmd(ssh, "cd /home/lckien/smart_door_pi && mkdir -p build && cd build && rm -rf * && cmake .. && make -j4")
    
    print("Restarting systemd service...")
    # Because it requires sudo, we will pass the password
    stdin, stdout, stderr = ssh.exec_command("sudo -S systemctl restart smart-door")
    stdin.write(password + "\n")
    stdin.flush()
    print("System restarted successfully!")
    
    ssh.close()
    print("Deploy finished successfully.")
except Exception as e:
    print("Failed:", e)
