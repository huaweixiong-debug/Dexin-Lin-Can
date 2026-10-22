#coding:utf-8
import os
import ctypes
import platform

# 检查LGV2目录下的USB2XXX.dll文件的架构
def check_dll_architecture(dll_path):
    print(f"\n=== 检查DLL文件: {dll_path} ===")
    if not os.path.exists(dll_path):
        print(f"文件不存在: {dll_path}")
        return False
    
    print(f"文件存在: {os.path.exists(dll_path)}")
    print(f"文件大小: {os.path.getsize(dll_path)} bytes")
    
    try:
        # 尝试使用cdll加载（64位）
        print("使用cdll加载...")
        dll = ctypes.cdll.LoadLibrary(dll_path)
        print("cdll加载成功！")
        print("DLL架构: 64位")
        return True
    except Exception as e:
        print(f"cdll加载失败: {str(e)}")
    
    try:
        # 尝试使用windll加载（32位）
        print("使用windll加载...")
        dll = ctypes.windll.LoadLibrary(dll_path)
        print("windll加载成功！")
        print("DLL架构: 32位")
        return True
    except Exception as e:
        print(f"windll加载失败: {str(e)}")
    
    return False

# 检查Python架构
print(f"Python架构: {platform.architecture()[0]}")
print(f"Python版本: {platform.python_version()}")
print(f"系统架构: {platform.machine()}")

# 定义要检查的DLL文件路径
lgv2_dir = "d:\\老化CAN通讯\\LGV2"

# 检查USB2LIN目录下的USB2XXX.dll
usb2lin_dll_path = os.path.join(lgv2_dir, "CANLINSW例子", "USB2LIN", "USB2XXX.dll")
check_dll_architecture(usb2lin_dll_path)

# 检查Labview/USB2LIN目录下的USB2XXX.dll和libusb-1.0.dll
labview_usb2lin_dir = os.path.join(lgv2_dir, "CANLINSW例子", "usb2can_lin_pwm_example-master", "examples", "Labview", "USB2LIN")
labview_usb2xxx_dll_path = os.path.join(labview_usb2lin_dir, "USB2XXX.dll")
labview_libusb_dll_path = os.path.join(labview_usb2lin_dir, "libusb-1.0.dll")

check_dll_architecture(labview_usb2xxx_dll_path)
check_dll_architecture(labview_libusb_dll_path)

# 检查是否有其他USB2XXX.dll文件
print("\n=== 搜索其他USB2XXX.dll文件 ===")
for root, dirs, files in os.walk(lgv2_dir):
    for file in files:
        if file.lower() == "usb2xxx.dll":
            dll_path = os.path.join(root, file)
            print(f"找到: {dll_path}")
            check_dll_architecture(dll_path)
