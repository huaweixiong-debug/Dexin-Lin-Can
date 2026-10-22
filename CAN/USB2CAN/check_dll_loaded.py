#coding:utf-8
import ctypes
import os

# 尝试使用kernel32.dll的GetModuleHandle函数检查DLL是否已加载
try:
    # 加载kernel32.dll
    kernel32 = ctypes.windll.kernel32
    
    # 定义GetModuleHandle函数
    GetModuleHandle = kernel32.GetModuleHandleW
    GetModuleHandle.restype = ctypes.c_void_p
    GetModuleHandle.argtypes = [ctypes.c_wchar_p]
    
    # 尝试获取USB2XXX.dll的模块句柄
    dll_name = "USB2XXX.dll"
    module_handle = GetModuleHandle(dll_name)
    print(f"GetModuleHandle('{dll_name}')返回: {module_handle}")
    if module_handle != 0:
        print(f"{dll_name}已加载到内存中！")
    else:
        print(f"{dll_name}未加载到内存中。")
    
    # 尝试使用LoadLibrary加载USB2XXX.dll
    LoadLibrary = kernel32.LoadLibraryW
    LoadLibrary.restype = ctypes.c_void_p
    LoadLibrary.argtypes = [ctypes.c_wchar_p]
    
    # 尝试加载64位DLL
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll")
    print(f"\n尝试使用LoadLibrary加载: {dll_path}")
    module_handle = LoadLibrary(dll_path)
    print(f"LoadLibrary返回: {module_handle}")
    if module_handle != 0:
        print(f"{dll_path}加载成功！")
        # 尝试释放DLL
        FreeLibrary = kernel32.FreeLibrary
        FreeLibrary.restype = ctypes.c_bool
        FreeLibrary.argtypes = [ctypes.c_void_p]
        result = FreeLibrary(module_handle)
        print(f"FreeLibrary返回: {result}")
    else:
        print(f"{dll_path}加载失败。")
        # 获取错误信息
        GetLastError = kernel32.GetLastError
        GetLastError.restype = ctypes.c_uint
        error_code = GetLastError()
        print(f"GetLastError返回: {error_code}")
        
        # 尝试获取错误信息的字符串描述
        FormatMessage = kernel32.FormatMessageW
        FormatMessage.restype = ctypes.c_uint
        FormatMessage.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        
        buffer = ctypes.create_unicode_buffer(256)
        length = FormatMessage(0x1200, None, error_code, 0, buffer, 256, None)
        print(f"FormatMessage返回: {length}")
        print(f"错误信息: {buffer.value}")
        
except Exception as e:
    print(f"错误: {str(e)}")
