#!/usr/bin/env python
"""Simple Python environment test script"""

import sys
import os
import socket
import threading
import queue

def main():
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"sys.path: {sys.path}")
    
    # Test module imports
    try:
        import socket
        print("socket module imported successfully")
    except ImportError as e:
        print(f"Error importing socket: {e}")
    
    try:
        import threading
        print("threading module imported successfully")
    except ImportError as e:
        print(f"Error importing threading: {e}")
    
    try:
        import queue
        print("queue module imported successfully")
    except ImportError as e:
        print(f"Error importing queue: {e}")
    
    # Test file I/O
    try:
        with open("test_output.txt", "w") as f:
            f.write("Python environment test passed!")
        print("Successfully wrote to test_output.txt")
        
        with open("test_output.txt", "r") as f:
            content = f.read()
        print(f"Successfully read from test_output.txt: {content}")
        
        os.remove("test_output.txt")
    except Exception as e:
        print(f"Error with file I/O: {e}")
    
    print("Python environment test completed!")

if __name__ == "__main__":
    main()