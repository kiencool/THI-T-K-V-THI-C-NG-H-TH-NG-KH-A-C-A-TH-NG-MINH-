import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    script = """
import sys
try:
    with open('/home/lckien/smart_door_pi/server.py', 'r') as f:
        code = f.read()
    compile(code, 'server.py', 'exec')
    print("OK")
except Exception as e:
    import traceback
    traceback.print_exc()
"""
    sftp = ssh.open_sftp()
    with sftp.file('/tmp/check.py', 'w') as f:
        f.write(script)
    sftp.close()
    
    stdin, stdout, stderr = ssh.exec_command('python3 /tmp/check.py')
    print("Output:", stdout.read().decode())
    
    # Also fetch the log!
    stdin, stdout, stderr = ssh.exec_command('cat /home/lckien/smart_door_pi/web_server.log')
    print("Log:", stdout.read().decode())
    
    ssh.close()
except Exception as e:
    print("Failed:", e)
