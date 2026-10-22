#coding:utf-8
import ctypes
import os

# 尝试直接加载USB2XXX.dll
script_dir = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll")

print(f"尝试加载: {dll_path}")
print(f"文件存在: {os.path.exists(dll_path)}")
print(f"文件大小: {os.path.getsize(dll_path)} bytes")

try:
    # 尝试使用cdll加载
    print("\n使用cdll加载...")
    dll = ctypes.cdll.LoadLibrary(dll_path)
    print("DLL加载成功！")
except Exception as e:
    print(f"cdll加载失败: {str(e)}")

try:
    # 尝试使用windll加载
    print("\n使用windll加载...")
    dll = ctypes.windll.LoadLibrary(dll_path)
    print("DLL加载成功！")
except Exception as e:
    print(f"windll加载失败: {str(e)}")

# 尝试加载libusb-1.0.dll
libusb_path = os.path.join(script_dir, "libs", "windows", "x86_64", "libusb-1.0.dll")
print(f"\n尝试加载libusb-1.0.dll: {libusb_path}")
print(f"文件存在: {os.path.exists(libusb_path)}")

try:
    libusb = ctypes.cdll.LoadLibrary(libusb_path)
    print("libusb-1.0.dll加载成功！")
except Exception as e:
    print(f"libusb-1.0.dll加载失败: {str(e)}")
