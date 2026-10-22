#coding:utf-8
import ctypes

# 尝试加载系统DLL文件
try:
    print("尝试加载kernel32.dll...")
    kernel32 = ctypes.windll.kernel32
    print("kernel32.dll加载成功！")
    
    # 尝试获取系统时间
    class SYSTEMTIME(ctypes.Structure):
        _fields_ = [
            ("wYear", ctypes.c_ushort),
            ("wMonth", ctypes.c_ushort),
            ("wDayOfWeek", ctypes.c_ushort),
            ("wDay", ctypes.c_ushort),
            ("wHour", ctypes.c_ushort),
            ("wMinute", ctypes.c_ushort),
            ("wSecond", ctypes.c_ushort),
            ("wMilliseconds", ctypes.c_ushort)
        ]
    
    st = SYSTEMTIME()
    kernel32.GetLocalTime(ctypes.byref(st))
    print(f"当前系统时间: {st.wYear}-{st.wMonth:02d}-{st.wDay:02d} {st.wHour:02d}:{st.wMinute:02d}:{st.wSecond:02d}")
    print("ctypes功能正常！")
except Exception as e:
    print(f"加载kernel32.dll失败: {str(e)}")

# 尝试使用cdll加载
print("\n尝试使用cdll加载kernel32.dll...")
try:
    kernel32_cdll = ctypes.cdll.kernel32
    print("kernel32.dll (cdll)加载成功！")
    
    st = SYSTEMTIME()
    kernel32_cdll.GetLocalTime(ctypes.byref(st))
    print(f"当前系统时间: {st.wYear}-{st.wMonth:02d}-{st.wDay:02d} {st.wHour:02d}:{st.wMinute:02d}:{st.wSecond:02d}")
    print("cdll功能正常！")
except Exception as e:
    print(f"加载kernel32.dll (cdll)失败: {str(e)}")
