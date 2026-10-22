#!/usr/bin/env python
"""Python wrapper script to handle Python interpreter selection for Trae IDE"""

import sys
import subprocess
import os

# Path to the actual Python interpreter
PYTHON_EXE = r"D:\miniconda3\python.exe"

def main():
    if len(sys.argv) < 2:
        print("Usage: python_wrapper.py <script.py> [args...]")
        sys.exit(1)
    
    # Get the script path and arguments
    script_path = sys.argv[1]
    args = sys.argv[2:]
    
    # Check if the script exists
    if not os.path.exists(script_path):
        print(f"Error: Script {script_path} does not exist")
        sys.exit(1)
    
    # Run the script using the actual Python interpreter
    try:
        result = subprocess.run([PYTHON_EXE, script_path] + args, 
                              capture_output=True, 
                              text=True)
        
        # Print the output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        # Exit with the same code as the script
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error running script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()