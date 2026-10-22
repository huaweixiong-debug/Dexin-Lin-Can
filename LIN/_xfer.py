import paramiko, base64

with open(r'R:\老化LIN通讯\lin_device_manager.py', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.123.122.100', username='dell', password='0000', timeout=15)
print('Connected')

# Use a remote Python script approach with temp file
remote_script = (
    'import base64, sys; '
    'd = sys.stdin.buffer.read(); '
    'data = base64.b64decode(d); '
    r"open(r'D:\老化LIN通讯\lin_device_manager.py', 'wb').write(data); "
    'print(len(data))'
)

stdin, stdout, stderr = ssh.exec_command(f'python -c "{remote_script}"', timeout=30)
stdin.write(b64 + '\n')
stdin.flush()
stdin.channel.shutdown_write()
out = stdout.read()
err = stderr.read()
print('OUT:', out.decode('utf-8', errors='replace').strip())
if err:
    print('ERR:', err.decode('utf-8', errors='replace')[:300])
ssh.close()
