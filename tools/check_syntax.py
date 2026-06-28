import paramiko

host = "192.168.1.190"
username = "lckien"
password = "123456789"

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    
    script = """
try:
    with open('/home/lckien/smart_door_pi/server.py', 'r') as f:
        code = f.read()
    compile(code, 'server.py', 'exec')
    print("Syntax OK")
except Exception as e:
    import traceback
    traceback.print_exc()
"""
    stdin, stdout, stderr = ssh.exec_command(f'python3 -c "{script}"')
    print(stdout.read().decode())
    print(stderr.read().decode())
    ssh.close()
    print("Done")
except Exception as e:
    print("Failed:", e)
