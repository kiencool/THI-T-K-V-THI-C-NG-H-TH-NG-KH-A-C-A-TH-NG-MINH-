import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    ssh.exec_command("sudo pkill -f server.py")
    import time
    time.sleep(2)
    
    # Run it directly and wait for output
    stdin, stdout, stderr = ssh.exec_command("cd /home/lckien/smart_door_pi && python3 server.py")
    
    # Wait for 3 seconds of output
    time.sleep(3)
    
    print("STDOUT:")
    print(stdout.read().decode())
    print("STDERR:")
    print(stderr.read().decode())
    
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
