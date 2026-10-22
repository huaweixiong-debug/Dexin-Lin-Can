#coding:utf-8
import ctypes
import os
import sys
import platform

# 尝试检查USB2XXX.dll的导出函数
try:
    # 加载kernel32.dll
    kernel32 = ctypes.windll.kernel32
    
    # 尝试加载USB2XXX.dll
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll")
    
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
    
    # 尝试检查USB2XXX.dll的文件头
    print("\n=== 检查USB2XXX.dll的文件头 ===")
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
    
    # 尝试使用Python的subprocess模块运行dumpbin.exe（如果存在）
    print("\n=== 尝试运行dumpbin.exe ===")
    try:
        import subprocess
        # 尝试在系统目录中查找dumpbin.exe
        system_dir = os.environ.get("SystemRoot", "C:\Windows")
        dumpbin_paths = [
            os.path.join(system_dir, "System32", "dumpbin.exe"),
            os.path.join(system_dir, "SysWOW64", "dumpbin.exe"),
        ]
        
        dumpbin_exe = None
        for path in dumpbin_paths:
            if os.path.exists(path):
                dumpbin_exe = path
                break
        
        if dumpbin_exe is not None:
            print(f"找到dumpbin.exe: {dumpbin_exe}")
            # 尝试运行dumpbin.exe /exports USB2XXX.dll
            result = subprocess.run([dumpbin_exe, "/exports", dll_path], 
                                  capture_output=True, text=True, cwd=os.path.dirname(dll_path))
            print("\ndumpbin.exe输出:")
            print(result.stdout)
            if result.stderr:
                print("\ndumpbin.exe错误:")
                print(result.stderr)
        else:
            print("未找到dumpbin.exe。")
    except Exception as e:
        print(f"运行dumpbin.exe失败: {str(e)}")
    
    # 尝试使用Python的ctypes来检查USB2XXX.dll的依赖项
    print("\n=== 尝试检查USB2XXX.dll的依赖项 ===")
    try:
        # 加载imagehlp.dll
        imagehlp = ctypes.windll.imagehlp
        
        # 定义LOADED_IMAGE结构
        class LOADED_IMAGE(ctypes.Structure):
            _fields_ = [
                ("ModuleName", ctypes.c_char_p),
                ("hFile", ctypes.c_void_p),
                ("MappedAddress", ctypes.c_void_p),
                ("FileHeader", ctypes.c_void_p),
                ("LastRvaSection", ctypes.c_void_p),
                ("NumberOfSections", ctypes.c_uint),
                ("Sections", ctypes.c_void_p),
                ("Characteristics", ctypes.c_uint),
                ("fSystemImage", ctypes.c_bool),
                ("fDOSImage", ctypes.c_bool),
                ("fReadOnly", ctypes.c_bool),
                ("fLoadedImage", ctypes.c_bool),
                ("Version", ctypes.c_ushort),
                ("Links", ctypes.c_uint),
                ("SizeOfImage", ctypes.c_uint),
            ]
        
        # 尝试使用MapAndLoad函数加载USB2XXX.dll
        MapAndLoad = imagehlp.MapAndLoad
        MapAndLoad.restype = ctypes.c_bool
        MapAndLoad.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(LOADED_IMAGE), ctypes.c_bool, ctypes.c_bool]
        
        loaded_image = LOADED_IMAGE()
        result = MapAndLoad(dll_path.encode('utf-8'), None, ctypes.byref(loaded_image), True, True)
        print(f"MapAndLoad返回: {result}")
        
        if result:
            print(f"DLL映射成功！")
            print(f"模块名称: {loaded_image.ModuleName.decode('utf-8')}")
            print(f"映像大小: {loaded_image.SizeOfImage}")
            
            # 尝试使用UnMapAndLoad函数释放USB2XXX.dll
            UnMapAndLoad = imagehlp.UnMapAndLoad
            UnMapAndLoad.restype = ctypes.c_bool
            UnMapAndLoad.argtypes = [ctypes.POINTER(LOADED_IMAGE)]
            result = UnMapAndLoad(ctypes.byref(loaded_image))
            print(f"UnMapAndLoad返回: {result}")
        else:
            print(f"DLL映射失败。")
            # 获取错误信息
            error_code = kernel32.GetLastError()
            print(f"GetLastError返回: {error_code}")
    except Exception as e:
        print(f"检查DLL依赖项失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用Python的ctypes来检查当前Python进程的位数
    print("\n=== 检查当前Python进程的位数 ===")
    print(f"Python架构: {platform.architecture()[0]}")
    print(f"Python版本: {platform.python_version()}")
    print(f"系统架构: {platform.machine()}")
    
    # 尝试使用Python的ctypes来检查USB2XXX.dll的位数
    print("\n=== 检查USB2XXX.dll的位数 ===")
    if os.path.exists(dll_path):
        with open(dll_path, "rb") as f:
            # 读取DOS头
            dos_header = f.read(64)
            pe_offset = int.from_bytes(dos_header[60:64], byteorder="little")
            
            # 读取PE头
            f.seek(pe_offset)
            pe_header = f.read(24)
            machine_type = int.from_bytes(pe_header[4:6], byteorder="little")
            
            print(f"USB2XXX.dll的机器类型: {machine_type}")
            if machine_type == 0x8664:
                print("USB2XXX.dll是64位的。")
            elif machine_type == 0x14c:
                print("USB2XXX.dll是32位的。")
            else:
                print(f"USB2XXX.dll的机器类型未知: {machine_type}")
            
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
    
    # 尝试使用Python的ctypes来加载USB2XXX.dll并获取其导出函数列表
    print("\n=== 尝试获取USB2XXX.dll的导出函数列表 ===")
    try:
        # 加载kernel32.dll
        kernel32 = ctypes.windll.kernel32
        
        # 加载USB2XXX.dll
        dll = ctypes.CDLL(dll_path)
        print("USB2XXX.dll加载成功！")
        
        # 尝试获取DLL的导出函数列表
        # 注意：这只是一个尝试，实际上ctypes没有直接的方法来获取DLL的导出函数列表
        print("注意：ctypes没有直接的方法来获取DLL的导出函数列表。")
        print("请使用dumpbin.exe或Dependency Walker等工具来检查DLL的导出函数。")
    except Exception as e:
        print(f"加载USB2XXX.dll失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用Python的subprocess模块运行regsvr32.exe（如果存在）
    print("\n=== 尝试运行regsvr32.exe ===")
    try:
        import subprocess
        # 尝试在系统目录中查找regsvr32.exe
        system_dir = os.environ.get("SystemRoot", "C:\Windows")
        regsvr32_path = os.path.join(system_dir, "System32", "regsvr32.exe")
        
        if os.path.exists(regsvr32_path):
            print(f"找到regsvr32.exe: {regsvr32_path}")
            # 尝试运行regsvr32.exe /u USB2XXX.dll（卸载）
            result = subprocess.run([regsvr32_path, "/u", "/s", dll_path], 
                                  capture_output=True, text=True, cwd=os.path.dirname(dll_path))
            print(f"regsvr32.exe /u返回: {result.returncode}")
            
            # 尝试运行regsvr32.exe USB2XXX.dll（注册）
            result = subprocess.run([regsvr32_path, "/s", dll_path], 
                                  capture_output=True, text=True, cwd=os.path.dirname(dll_path))
            print(f"regsvr32.exe返回: {result.returncode}")
        else:
            print("未找到regsvr32.exe。")
    except Exception as e:
        print(f"运行regsvr32.exe失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"错误: {str(e)}")
    import traceback
    traceback.print_exc()
