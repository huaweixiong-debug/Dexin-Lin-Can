#coding:utf-8
import os
import subprocess

# 尝试使用subprocess调用一个简单的命令，设置PATH环境变量
try:
    # 设置PATH环境变量，包含DLL所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_dir = os.path.join(script_dir, "libs", "windows", "x86_64")
    
    # 保存原始PATH
    original_path = os.environ.get("PATH", "")
    
    # 添加DLL目录到PATH
    os.environ["PATH"] = dll_dir + ";" + original_path
    
    print(f"Added to PATH: {dll_dir}")
    print(f"New PATH: {os.environ['PATH']}")
    
    # 尝试运行Python命令，导入ctypes并加载DLL
    # 使用原始字符串避免Unicode转义错误
    dll_path_str = dll_dir.replace('\\', '\\\\') + '\\\\USB2XXX.dll'
    python_code = f'''
#coding:utf-8
import ctypes
import os

try:
    # 尝试加载USB2XXX.dll
    dll_path = "{dll_path_str}"
    print(f"Attempting to load: {{dll_path}}")
    print(f"File exists: {{os.path.exists(dll_path)}}")
    dll = ctypes.cdll.LoadLibrary(dll_path)
    print("USB2XXX.dll loaded successfully!")
    
    # 尝试获取USB_ScanDevice函数
    USB_ScanDevice = dll.USB_ScanDevice
    print("Got USB_ScanDevice function successfully!")
    
    # 扫描设备
    DevHandles = (ctypes.c_uint * 20)()
    ret = USB_ScanDevice(DevHandles)
    print(f"USB_ScanDevice returned: {{ret}}")
    if ret > 0:
        print(f"Found {{ret}} devices!")
        for i in range(ret):
            print(f"Device {{i}}: {{DevHandles[i]}}")
except Exception as e:
    print(f"Error: {{str(e)}}")
'''
    
    # 写入临时Python文件
    temp_file = os.path.join(script_dir, "temp_test.py")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(python_code)
    
    # 运行临时Python文件
    print("\nRunning temporary Python script...")
    result = subprocess.run(["python", temp_file], capture_output=True, text=True)
    print("\nOutput:")
    print(result.stdout)
    if result.stderr:
        print("\nError:")
        print(result.stderr)
    
    # 恢复原始PATH
    os.environ["PATH"] = original_path
    
    # 删除临时文件
    os.remove(temp_file)
    
except Exception as e:
    print(f"Error: {str(e)}")
    # 恢复原始PATH
    if 'original_path' in locals():
        os.environ["PATH"] = original_path
