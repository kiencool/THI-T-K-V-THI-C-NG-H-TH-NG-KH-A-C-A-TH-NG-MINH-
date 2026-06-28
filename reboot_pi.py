import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    ssh.exec_command("echo 123456789 | sudo -S reboot")
    ssh.close()
    print("Rebooting Pi")
except Exception as e:
    print("Failed:", e)
