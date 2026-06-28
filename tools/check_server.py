import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    script = """
import traceback
try:
    with open('/home/lckien/smart_door_pi/server.py', 'r') as f:
        code = f.read()
    compile(code, 'server.py', 'exec')
    print("OK")
except Exception as e:
    traceback.print_exc()
"""
    sftp = ssh.open_sftp()
    with sftp.file('/tmp/check.py', 'w') as f:
        f.write(script)
    sftp.close()
    
    stdin, stdout, stderr = ssh.exec_command('python3 /tmp/check.py')
    print("Syntax check output:", stdout.read().decode())
    print("Syntax check error:", stderr.read().decode())
    
    # Try running the server for 2 seconds and capture output directly
    stdin, stdout, stderr = ssh.exec_command('python3 /home/lckien/smart_door_pi/server.py & sleep 2; kill $!')
    print("Server output:", stdout.read().decode())
    print("Server error:", stderr.read().decode())
    
    ssh.close()
except Exception as e:
    print("Failed:", e)
