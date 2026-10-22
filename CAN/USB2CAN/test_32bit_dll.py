#coding:utf-8
import ctypes
import os
import sys
import platform

# 尝试使用32位的USB2XXX.dll
try:
    # 加载kernel32.dll
    kernel32 = ctypes.windll.kernel32
    
    # 尝试加载32位的USB2XXX.dll
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = os.path.join(script_dir, "libs", "windows", "x86", "USB2XXX.dll")
    
    print(f"尝试加载: {dll_path}")
    print(f"文件存在: {os.path.exists(dll_path)}")
    
    # 尝试使用LoadLibrary加载DLL
    LoadLibrary = kernel32.LoadLibraryW
    LoadLibrary.restype = ctypes.c_void_p
    LoadLibrary.argtypes = [ctypes.c_wchar_p]
    
    module_handle = LoadLibrary(dll_path)
    print(f"LoadLibrary返回: {module_handle}")
    
    if module_handle != 0:
        print(f"DLL加载成功！")
        
        # 尝试获取USB_ScanDevice函数
        GetProcAddress = kernel32.GetProcAddress
        GetProcAddress.restype = ctypes.c_void_p
        GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        
        function_name = b"USB_ScanDevice"
        function_address = GetProcAddress(module_handle, function_name)
        print(f"GetProcAddress('{function_name.decode()}')返回: {function_address}")
        
        if function_address is not None and function_address != 0:
            print(f"{function_name.decode()}函数存在！")
            
            # 尝试调用USB_ScanDevice函数
            USB_ScanDevice = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_uint))(function_address)
            
            # 扫描设备
            DevHandles = (ctypes.c_uint * 20)()
            ret = USB_ScanDevice(DevHandles)
            print(f"USB_ScanDevice返回: {ret}")
            if ret > 0:
                print(f"找到 {ret} 个设备！")
                for i in range(ret):
                    print(f"设备 {i}: {DevHandles[i]}")
        else:
            print(f"{function_name.decode()}函数不存在！")
            
            # 尝试获取其他可能的函数
            function_names = [b"USB_OpenDevice", b"USB_CloseDevice", b"DEV_GetDeviceInfo", b"CAN_Init", b"CAN_SendMsg", b"CAN_GetMsg"]
            for name in function_names:
                address = GetProcAddress(module_handle, name)
                print(f"GetProcAddress('{name.decode()}')返回: {address}")
                if address is not None and address != 0:
                    print(f"{name.decode()}函数存在！")
        
        # 尝试释放DLL
        FreeLibrary = kernel32.FreeLibrary
        FreeLibrary.restype = ctypes.c_bool
        FreeLibrary.argtypes = [ctypes.c_void_p]
        result = FreeLibrary(module_handle)
        print(f"FreeLibrary返回: {result}")
    else:
        print(f"DLL加载失败。")
        
        # 获取错误信息
        GetLastError = kernel32.GetLastError
        GetLastError.restype = ctypes.c_uint
        error_code = GetLastError()
        print(f"GetLastError返回: {error_code}")
        
        # 尝试使用FormatMessage获取错误信息
        FormatMessage = kernel32.FormatMessageW
        FormatMessage.restype = ctypes.c_uint
        FormatMessage.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        
        buffer = ctypes.create_unicode_buffer(1024)
        length = FormatMessage(0x1200, None, error_code, 0, buffer, ctypes.sizeof(buffer), None)
        print(f"FormatMessage返回: {length}")
        print(f"错误信息: {buffer.value}")
    
    # 尝试检查32位USB2XXX.dll的文件头
    print("\n=== 检查32位USB2XXX.dll的文件头 ===")
    if os.path.exists(dll_path):
        with open(dll_path, "rb") as f:
            # 读取DOS头
            dos_header = f.read(64)
            print(f"DOS头标识: {dos_header[:2].decode('ascii')}")
            
            # 读取PE头偏移
            pe_offset = int.from_bytes(dos_header[60:64], byteorder="little")
            print(f"PE头偏移: {pe_offset}")
            
            # 读取PE头
            f.seek(pe_offset)
            pe_header = f.read(24)
            print(f"PE头标识: {pe_header[:4].decode('ascii')}")
            
            # 读取机器类型
            machine_type = int.from_bytes(pe_header[4:6], byteorder="little")
            print(f"机器类型: {machine_type}")
            if machine_type == 0x8664:
                print("机器类型: x64 (64位)")
            elif machine_type == 0x14c:
                print("机器类型: x86 (32位)")
            else:
                print(f"机器类型: 未知 ({machine_type})")
    
    # 尝试检查当前Python进程的位数
    print("\n=== 检查当前Python进程的位数 ===")
    print(f"Python架构: {platform.architecture()[0]}")
    print(f"Python版本: {platform.python_version()}")
    print(f"系统架构: {platform.machine()}")
    
    # 尝试检查32位USB2XXX.dll的位数
    print("\n=== 检查32位USB2XXX.dll的位数 ===")
    if os.path.exists(dll_path):
        with open(dll_path, "rb") as f:
            # 读取DOS头
            dos_header = f.read(64)
            pe_offset = int.from_bytes(dos_header[60:64], byteorder="little")
            
            # 读取PE头
            f.seek(pe_offset)
            pe_header = f.read(24)
            machine_type = int.from_bytes(pe_header[4:6], byteorder="little")
            
            print(f"32位USB2XXX.dll的机器类型: {machine_type}")
            if machine_type == 0x8664:
                print("32位USB2XXX.dll是64位的。")
            elif machine_type == 0x14c:
                print("32位USB2XXX.dll是32位的。")
            else:
                print(f"32位USB2XXX.dll的机器类型未知: {machine_type}")
            
            # 检查当前Python进程的位数
            print(f"当前Python进程的位数: {platform.architecture()[0]}")
            if platform.architecture()[0] == "64bit" and machine_type == 0x8664:
                print("架构匹配: 64位Python运行64位DLL")
            elif platform.architecture()[0] == "32bit" and machine_type == 0x14c:
                print("架构匹配: 32位Python运行32位DLL")
            else:
                print("架构不匹配！")
                print(f"Python架构: {platform.architecture()[0]}")
                print(f"DLL架构: {'64位' if machine_type == 0x8664 else '32位' if machine_type == 0x14c else '未知'}")
    
    # 尝试使用Python的subprocess模块运行32位的Python（如果存在）
    print("\n=== 尝试使用32位的Python ===")
    try:
        import subprocess
        # 尝试在系统目录中查找32位的Python
        system_dir = os.environ.get("SystemRoot", "C:\Windows")
        python_paths = [
            os.path.join(system_dir, "SysWOW64", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python313", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python312", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python311", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python310", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python39", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python38", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python37", "python.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)"), "Python36", "python.exe"),
        ]
        
        python_exe = None
        for path in python_paths:
            if os.path.exists(path):
                python_exe = path
                break
        
        if python_exe is not None:
            print(f"找到32位的Python: {python_exe}")
            # 尝试运行32位的Python，执行一个简单的脚本
            test_script = """
import ctypes
import os

# 尝试加载32位的USB2XXX.dll
script_dir = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(script_dir, "libs", "windows", "x86", "USB2XXX.dll")

print(f"尝试加载: {dll_path}")
print(f"文件存在: {os.path.exists(dll_path)}")

try:
    # 尝试加载DLL
    dll = ctypes.windll.LoadLibrary(dll_path)
    print("DLL加载成功！")
    
    # 尝试获取USB_ScanDevice函数
    USB_ScanDevice = dll.USB_ScanDevice
    print("获取USB_ScanDevice函数成功！")
    
    # 扫描设备
    DevHandles = (ctypes.c_uint * 20)()
    ret = USB_ScanDevice(DevHandles)
    print(f"USB_ScanDevice返回: {ret}")
    if ret > 0:
        print(f"找到 {ret} 个设备！")
        for i in range(ret):
            print(f"设备 {i}: {DevHandles[i]}")
except Exception as e:
    print(f"错误: {str(e)}")
    import traceback
    traceback.print_exc()
"""
            
            # 写入临时测试脚本
            temp_script_path = os.path.join(script_dir, "temp_32bit_test.py")
            with open(temp_script_path, "w", encoding="utf-8") as f:
                f.write(test_script)
            
            # 运行32位的Python
            result = subprocess.run([python_exe, temp_script_path], 
                                  capture_output=True, text=True, cwd=script_dir)
            print("\n32位Python输出:")
            print(result.stdout)
            if result.stderr:
                print("\n32位Python错误:")
                print(result.stderr)
            
            # 删除临时测试脚本
            os.remove(temp_script_path)
        else:
            print("未找到32位的Python。")
    except Exception as e:
        print(f"运行32位Python失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用Python的subprocess模块运行cmd.exe，执行dir命令查看32位USB2XXX.dll的属性
    print("\n=== 尝试查看32位USB2XXX.dll的属性 ===")
    try:
        import subprocess
        result = subprocess.run(["cmd.exe", "/c", "dir", dll_path], 
                              capture_output=True, text=True, cwd=os.path.dirname(dll_path))
        print("\ndir命令输出:")
        print(result.stdout)
        if result.stderr:
            print("\ndir命令错误:")
            print(result.stderr)
    except Exception as e:
        print(f"运行dir命令失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用Python的subprocess模块运行cmd.exe，执行attrib命令查看32位USB2XXX.dll的属性
    print("\n=== 尝试查看32位USB2XXX.dll的属性 ===")
    try:
        import subprocess
        result = subprocess.run(["cmd.exe", "/c", "attrib", dll_path], 
                              capture_output=True, text=True, cwd=os.path.dirname(dll_path))
        print("\nattrib命令输出:")
        print(result.stdout)
        if result.stderr:
            print("\nattrib命令错误:")
            print(result.stderr)
    except Exception as e:
        print(f"运行attrib命令失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用Python的subprocess模块运行cmd.exe，执行type命令查看32位USB2XXX.dll的类型
    print("\n=== 尝试查看32位USB2XXX.dll的类型 ===")
    try:
        import subprocess
        result = subprocess.run(["cmd.exe", "/c", "type", dll_path], 
                              capture_output=True, text=True, cwd=os.path.dirname(dll_path))
        print("\ntype命令输出:")
        print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
        if result.stderr:
            print("\ntype命令错误:")
            print(result.stderr)
    except Exception as e:
        print(f"运行type命令失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
except Exception as e:
    print(f"错误: {str(e)}")
    import traceback
    traceback.print_exc()
