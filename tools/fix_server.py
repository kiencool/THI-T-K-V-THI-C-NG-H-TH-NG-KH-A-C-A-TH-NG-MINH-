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
    sftp.get("/home/lckien/smart_door_pi/server.py", "server_fix.py")
    
    with open("server_fix.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    # Find the bad except block
    if "except Exception:" in code:
        code = code.replace(
            "        except Exception:\\n            history = []",
            "        except Exception as e:\\n            print('ERROR PARSING JSON:', e)\\n            history = [{'event': 'error', 'detail': str(e)}]"
        )
    else:
        # It's already corrupted by my previous regex, let's fix the indentation!
        import re
        code = re.sub(r'except Exception as e:\\s+print\\("JSON PARSE ERROR:", e\\)\\s+history = \\[\\]', '        except Exception as e:\\n            print("JSON PARSE ERROR:", e)\\n            history = [{"event": "error", "detail": str(e)}]', code)
        
    with open("server_fix.py", "w", encoding="utf-8") as f:
        f.write(code)
        
    print("Uploading server.py...")
    sftp.put("server_fix.py", "/home/lckien/smart_door_pi/server.py")
    sftp.close()
    
    print("Restarting server.py...")
    ssh.exec_command("sudo pkill -f server.py && cd /home/lckien/smart_door_pi && nohup python3 server.py > web_server.log 2>&1 &")
    ssh.close()
    
    print("Done")
except Exception as e:
    print("Failed:", e)
