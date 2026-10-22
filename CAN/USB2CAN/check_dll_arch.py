#coding:utf-8
import ctypes
import os

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(script_dir, "libs", "windows")

print("=== 检查DLL文件架构 ===")
print(f"脚本目录: {script_dir}")
print(f"libs目录: {libs_dir}")

# 尝试加载64位DLL
try:
    print("\n尝试加载64位DLL:")
    libusb_64 = os.path.join(libs_dir, "x86_64", "libusb-1.0.dll")
    usb2xxx_64 = os.path.join(libs_dir, "x86_64", "USB2XXX.dll")
    
    print(f"libusb-1.0.dll (64位): {libusb_64}")
    print(f"USB2XXX.dll (64位): {usb2xxx_64}")
    
    # 尝试加载64位DLL
    ctypes.cdll.LoadLibrary(libusb_64)
    ctypes.cdll.LoadLibrary(usb2xxx_64)
    print("64位DLL加载成功！")
except Exception as e:
    print(f"64位DLL加载失败: {str(e)}")

# 尝试加载32位DLL
try:
    print("\n尝试加载32位DLL:")
    libusb_32 = os.path.join(libs_dir, "x86", "libusb-1.0.dll")
    usb2xxx_32 = os.path.join(libs_dir, "x86", "USB2XXX.dll")
    
    print(f"libusb-1.0.dll (32位): {libusb_32}")
    print(f"USB2XXX.dll (32位): {usb2xxx_32}")
    
    # 尝试加载32位DLL
    ctypes.windll.LoadLibrary(libusb_32)
    ctypes.windll.LoadLibrary(usb2xxx_32)
    print("32位DLL加载成功！")
except Exception as e:
    print(f"32位DLL加载失败: {str(e)}")

print("\n=== 检查完成 ===")
