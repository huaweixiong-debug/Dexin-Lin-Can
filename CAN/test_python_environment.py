import sys
import os

# Test Python environment
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path}")

# Test if we can import modules
try:
    import socket
    print("✓ socket module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import socket module: {e}")

try:
    import threading
    print("✓ threading module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import threading module: {e}")

try:
    import queue
    print("✓ queue module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import queue module: {e}")

# Test environment variables
print("\nEnvironment variables:")
for key, value in os.environ.items():
    if "PYTHON" in key or "CONDA" in key:
        print(f"{key}: {value}")

# Test writing to a file
try:
    with open("test_output.txt", "w") as f:
        f.write("Python environment test passed!")
    print("\n✓ Successfully wrote to test_output.txt")
    with open("test_output.txt", "r") as f:
        content = f.read()
    print(f"✓ Successfully read from test_output.txt: {content}")
except Exception as e:
    print(f"\n✗ Failed to write/read file: {e}")

print("\nPython environment test completed!")