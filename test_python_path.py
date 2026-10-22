import os

python_path = "D:\miniconda3\python.exe"
print(f"Python path: {python_path}")
print(f"Path exists: {os.path.exists(python_path)}")
print(f"Is file: {os.path.isfile(python_path)}")
print(f"Is executable: {os.access(python_path, os.X_OK)}")

# Try to run it
import subprocess
try:
    result = subprocess.run([python_path, "--version"], capture_output=True, text=True)
    print(f"Command output: {result.stdout}")
    print(f"Command error: {result.stderr}")
    print(f"Command return code: {result.returncode}")
except Exception as e:
    print(f"Error running Python: {e}")