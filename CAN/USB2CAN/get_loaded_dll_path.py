#coding:utf-8
import ctypes
import os
import sys
import platform

# 尝试获取已加载USB2XXX.dll的路径
try:
    # 加载kernel32.dll
    kernel32 = ctypes.windll.kernel32
    
    # 获取已加载的USB2XXX.dll模块句柄
    GetModuleHandle = kernel32.GetModuleHandleW
    GetModuleHandle.restype = ctypes.c_void_p
    GetModuleHandle.argtypes = [ctypes.c_wchar_p]
    
    module_handle = GetModuleHandle("USB2XXX.dll")
    print(f"USB2XXX.dll模块句柄: {module_handle}")
    
    if module_handle != 0:
        # 获取模块文件名
        GetModuleFileName = kernel32.GetModuleFileNameW
        GetModuleFileName.restype = ctypes.c_uint
        GetModuleFileName.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
        
        buffer = ctypes.create_unicode_buffer(1024)
        length = GetModuleFileName(module_handle, buffer, ctypes.sizeof(buffer))
        if length > 0:
            dll_path = buffer.value
            print(f"已加载USB2XXX.dll的路径: {dll_path}")
            print(f"文件存在: {os.path.exists(dll_path)}")
            print(f"文件大小: {os.path.getsize(dll_path)} bytes")
            
            # 尝试使用已加载DLL的路径来加载
            print("\n尝试使用已加载DLL的路径来加载...")
            try:
                # 尝试使用cdll加载
                dll = ctypes.cdll.LoadLibrary(dll_path)
                print("使用cdll加载成功！")
                
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
                print(f"使用cdll加载失败: {str(e)}")
                
            try:
                # 尝试使用windll加载
                dll = ctypes.windll.LoadLibrary(dll_path)
                print("使用windll加载成功！")
                
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
                print(f"使用windll加载失败: {str(e)}")
        else:
            print("无法获取模块文件名。")
    else:
        print("未找到USB2XXX.dll模块。")
        
    # 尝试使用LoadLibraryEx加载USB2XXX.dll
    print("\n尝试使用LoadLibraryEx加载USB2XXX.dll...")
    LoadLibraryEx = kernel32.LoadLibraryExW
    LoadLibraryEx.restype = ctypes.c_void_p
    LoadLibraryEx.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint]
    
    # 尝试使用不同的标志
    LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008
    LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x00000800
    LOAD_LIBRARY_SEARCH_APPLICATION_DIR = 0x00000200
    LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000
    
    # 尝试加载64位DLL
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll")
    
    for flag in [0, LOAD_WITH_ALTERED_SEARCH_PATH, LOAD_LIBRARY_SEARCH_SYSTEM32, LOAD_LIBRARY_SEARCH_APPLICATION_DIR, LOAD_LIBRARY_SEARCH_DEFAULT_DIRS]:
        module_handle = LoadLibraryEx(dll_path, None, flag)
        print(f"LoadLibraryEx(flag={flag})返回: {module_handle}")
        if module_handle != 0:
            print(f"加载成功！")
            # 尝试释放DLL
            FreeLibrary = kernel32.FreeLibrary
            FreeLibrary.restype = ctypes.c_bool
            FreeLibrary.argtypes = [ctypes.c_void_p]
            result = FreeLibrary(module_handle)
            print(f"FreeLibrary返回: {result}")
            break
    
    # 尝试检查环境变量
    print("\n=== 检查环境变量 ===")
    for key, value in os.environ.items():
        if "PATH" in key or "DLL" in key:
            print(f"{key}: {value}")
    
    # 尝试检查当前工作目录
    print(f"\n当前工作目录: {os.getcwd()}")
    
    # 尝试检查Python路径
    print(f"Python路径: {os.path.dirname(sys.executable)}")
    
    # 尝试检查系统类型
    print(f"系统类型: {platform.system()} {platform.architecture()[0]}")
    
    # 尝试检查Python版本
    print(f"Python版本: {platform.python_version()}")
    
    # 尝试使用ctypes的find_library函数
    print("\n尝试使用find_library查找USB2XXX...")
    try:
        import ctypes.util
        dll_path = ctypes.util.find_library("USB2XXX")
        print(f"find_library返回: {dll_path}")
        if dll_path:
            print(f"文件存在: {os.path.exists(dll_path)}")
    except Exception as e:
        print(f"find_library失败: {str(e)}")
        
    # 尝试使用os.startfile打开USB2XXX.dll所在的目录
    print("\n尝试打开USB2XXX.dll所在的目录...")
    try:
        dll_dir = os.path.dirname(dll_path)
        os.startfile(dll_dir)
        print(f"已打开目录: {dll_dir}")
    except Exception as e:
        print(f"打开目录失败: {str(e)}")
    
    # 尝试使用subprocess运行cmd.exe，执行dir命令查看目录内容
    print("\n尝试运行dir命令查看目录内容...")
    try:
        import subprocess
        result = subprocess.run(["cmd.exe", "/c", "dir", dll_dir], capture_output=True, text=True)
        print(f"dir命令输出: {result.stdout}")
        if result.stderr:
            print(f"dir命令错误: {result.stderr}")
    except Exception as e:
        print(f"运行dir命令失败: {str(e)}")
        
except Exception as e:
    print(f"错误: {str(e)}")
    import traceback
    traceback.print_exc()
