#coding:utf-8
import ctypes
import os

# 尝试列出当前进程加载的所有DLL模块
try:
    # 加载kernel32.dll
    kernel32 = ctypes.windll.kernel32
    
    # 获取当前进程ID
    GetCurrentProcessId = kernel32.GetCurrentProcessId
    GetCurrentProcessId.restype = ctypes.c_uint
    process_id = GetCurrentProcessId()
    print(f"当前进程ID: {process_id}")
    
    # 打开当前进程
    OpenProcess = kernel32.OpenProcess
    OpenProcess.restype = ctypes.c_void_p
    OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    process_handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, process_id)
    print(f"OpenProcess返回: {process_handle}")
    
    if process_handle != 0:
        # 枚举进程模块
        EnumProcessModules = kernel32.EnumProcessModules
        EnumProcessModules.restype = ctypes.c_bool
        EnumProcessModules.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
        
        # 获取模块文件名
        GetModuleFileNameEx = ctypes.windll.psapi.GetModuleFileNameExW
        GetModuleFileNameEx.restype = ctypes.c_uint
        GetModuleFileNameEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
        
        # 分配内存用于存储模块句柄
        modules = (ctypes.c_void_p * 1024)()
        bytes_needed = ctypes.c_ulong()
        
        if EnumProcessModules(process_handle, modules, ctypes.sizeof(modules), ctypes.byref(bytes_needed)):
            print(f"\n已加载的模块数量: {bytes_needed.value // ctypes.sizeof(ctypes.c_void_p)}")
            print("\n=== 已加载的DLL模块 ===")
            
            # 遍历所有模块
            for i in range(bytes_needed.value // ctypes.sizeof(ctypes.c_void_p)):
                module_handle = modules[i]
                if module_handle != 0:
                    # 获取模块文件名
                    buffer = ctypes.create_unicode_buffer(1024)
                    length = GetModuleFileNameEx(process_handle, module_handle, buffer, ctypes.sizeof(buffer))
                    if length > 0:
                        module_name = os.path.basename(buffer.value)
                        if "usb" in module_name.lower() or "can" in module_name.lower():
                            print(f"{module_name}: {buffer.value}")
            
            # 特别查找USB2XXX.dll
            print("\n=== 特别查找USB2XXX.dll ===")
            for i in range(bytes_needed.value // ctypes.sizeof(ctypes.c_void_p)):
                module_handle = modules[i]
                if module_handle != 0:
                    buffer = ctypes.create_unicode_buffer(1024)
                    length = GetModuleFileNameEx(process_handle, module_handle, buffer, ctypes.sizeof(buffer))
                    if length > 0 and "USB2XXX.dll" in buffer.value:
                        print(f"找到USB2XXX.dll: {buffer.value}")
        
        # 关闭进程句柄
        CloseHandle = kernel32.CloseHandle
        CloseHandle.restype = ctypes.c_bool
        CloseHandle.argtypes = [ctypes.c_void_p]
        CloseHandle(process_handle)
    
    # 尝试获取系统目录
    GetSystemDirectory = kernel32.GetSystemDirectoryW
    GetSystemDirectory.restype = ctypes.c_uint
    GetSystemDirectory.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    system_dir = ctypes.create_unicode_buffer(1024)
    length = GetSystemDirectory(system_dir, ctypes.sizeof(system_dir))
    print(f"\n系统目录: {system_dir.value}")
    
    # 检查系统目录中是否有USB2XXX.dll
    system_dll_path = os.path.join(system_dir.value, "USB2XXX.dll")
    print(f"系统目录中USB2XXX.dll存在: {os.path.exists(system_dll_path)}")
    
    # 检查PATH环境变量中的目录
    print("\n=== 检查PATH环境变量中的目录 ===")
    path_env = os.environ.get("PATH", "")
    for path in path_env.split(";"):
        if path and os.path.exists(path):
            dll_path = os.path.join(path, "USB2XXX.dll")
            if os.path.exists(dll_path):
                print(f"在PATH目录中找到USB2XXX.dll: {dll_path}")
    
    # 尝试使用GetModuleFileName获取已加载DLL的路径
    print("\n=== 尝试获取已加载USB2XXX.dll的路径 ===")
    GetModuleHandle = kernel32.GetModuleHandleW
    GetModuleHandle.restype = ctypes.c_void_p
    GetModuleHandle.argtypes = [ctypes.c_wchar_p]
    
    module_handle = GetModuleHandle("USB2XXX.dll")
    if module_handle != 0:
        buffer = ctypes.create_unicode_buffer(1024)
        length = GetModuleFileNameEx(kernel32.GetCurrentProcess(), module_handle, buffer, ctypes.sizeof(buffer))
        if length > 0:
            print(f"已加载的USB2XXX.dll路径: {buffer.value}")
        else:
            print("无法获取已加载USB2XXX.dll的路径")
    else:
        print("未找到已加载的USB2XXX.dll")
        
except Exception as e:
    print(f"错误: {str(e)}")
    import traceback
    traceback.print_exc()
