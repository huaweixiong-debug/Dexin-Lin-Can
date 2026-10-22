#coding:utf-8
import ctypes
import os
import sys

# 尝试使用Dumpbin.exe来检查DLL依赖项
def check_dependencies(dll_path):
    print(f"检查{dll_path}的依赖项...")
    
    # 尝试找到Dumpbin.exe
    dumpbin_paths = [
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC\14.29.30133\bin\Hostx64\x64\dumpbin.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\14.29.30133\bin\Hostx64\x64\dumpbin.exe",
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.34.31933\bin\Hostx64\x64\dumpbin.exe",
        r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.34.31933\bin\Hostx64\x64\dumpbin.exe",
    ]
    
    dumpbin_exe = None
    for path in dumpbin_paths:
        if os.path.exists(path):
            dumpbin_exe = path
            break
    
    if dumpbin_exe is None:
        print("找不到Dumpbin.exe，请安装Visual Studio或Build Tools")
        return
    
    print(f"使用Dumpbin.exe: {dumpbin_exe}")
    
    # 运行Dumpbin.exe
    import subprocess
    try:
        result = subprocess.run([dumpbin_exe, "/dependents", dll_path], 
                              capture_output=True, text=True, cwd=os.path.dirname(dll_path))
        print("\n依赖项:")
        print(result.stdout)
        if result.stderr:
            print("\n错误:")
            print(result.stderr)
    except Exception as e:
        print(f"运行Dumpbin.exe失败: {str(e)}")

# 检查USB2XXX.dll的依赖项
script_dir = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll")
check_dependencies(dll_path)
