#coding:utf-8
import ctypes
import ctypes.util
import os

# 尝试使用find_library查找USB2XXX
print("尝试使用find_library查找USB2XXX...")
dll_path = ctypes.util.find_library("USB2XXX")
print(f"find_library返回: {dll_path}")

# 尝试使用绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))

# 尝试所有可能的DLL路径
dll_paths = [
    os.path.join(script_dir, "USB2XXX.dll"),
    os.path.join(script_dir, "libs", "USB2XXX.dll"),
    os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll"),
    os.path.join(script_dir, "libs", "windows", "x86", "USB2XXX.dll"),
]

for path in dll_paths:
    print(f"\n尝试: {path}")
    print(f"文件存在: {os.path.exists(path)}")
    if os.path.exists(path):
        print(f"文件大小: {os.path.getsize(path)} bytes")
        try:
            dll = ctypes.cdll.LoadLibrary(path)
            print("DLL加载成功！")
            break
        except Exception as e:
            print(f"加载失败: {str(e)}")

print("\n测试完成。")
