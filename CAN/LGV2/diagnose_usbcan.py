#!/usr/bin/env python3
"""
USB-CAN设备诊断脚本
用于诊断用户启动时找不到USB-CAN设备的问题
"""

import os
import sys
import platform
import ctypes
import json
import time
import traceback
from ctypes import *

def print_header(title):
    """打印标题"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def check_environment():
    """检查环境信息"""
    print_header("环境信息检查")
    
    # 操作系统信息
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"系统架构: {platform.architecture()[0]}")
    print(f"Python版本: {platform.python_version()}")
    print(f"Python可执行文件: {sys.executable}")
    
    # 当前用户
    try:
        import getpass
        print(f"当前用户: {getpass.getuser()}")
    except:
        print("当前用户: 无法获取")
    
    # 工作目录
    print(f"当前工作目录: {os.getcwd()}")
    print(f"脚本所在目录: {os.path.dirname(os.path.abspath(__file__))}")
    
    # 环境变量
    print(f"PATH环境变量长度: {len(os.environ.get('PATH', ''))} 字符")
    
    # 检查是否有管理员权限
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        print(f"管理员权限: {'是' if is_admin else '否'}")
    except:
        print("管理员权限: 无法检测")

def check_dll_files():
    """检查DLL文件"""
    print_header("DLL文件检查")
    
    # 获取USB2CAN目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    usb2can_dir = os.path.join(os.path.dirname(current_dir), 'USB2CAN')
    
    print(f"USB2CAN目录: {usb2can_dir}")
    print(f"USB2CAN目录是否存在: {os.path.exists(usb2can_dir)}")
    
    if os.path.exists(usb2can_dir):
        # 检查DLL文件
        dll_files = [
            ('libusb-1.0.dll', 'libusb-1.0.dll'),
            ('USB2XXX.dll', 'USB2XXX.dll'),
        ]
        
        for dll_name, dll_path in dll_files:
            full_path = os.path.join(usb2can_dir, dll_path)
            exists = os.path.exists(full_path)
            size = os.path.getsize(full_path) if exists else 0
            print(f"{dll_name}: 存在={exists}, 大小={size}字节, 路径={full_path}")
        
        # 检查libs目录
        windows_libs_dir = os.path.join(usb2can_dir, 'libs', 'windows')
        print(f"\nWindows库目录: {windows_libs_dir}")
        print(f"Windows库目录是否存在: {os.path.exists(windows_libs_dir)}")
        
        if os.path.exists(windows_libs_dir):
            # 检查64位DLL
            x86_64_dir = os.path.join(windows_libs_dir, 'x86_64')
            if os.path.exists(x86_64_dir):
                print(f"64位DLL目录: {x86_64_dir}")
                for dll_name in ['libusb-1.0.dll', 'USB2XXX.dll']:
                    dll_path = os.path.join(x86_64_dir, dll_name)
                    exists = os.path.exists(dll_path)
                    print(f"  {dll_name}: 存在={exists}")
            
            # 检查32位DLL
            x86_dir = os.path.join(windows_libs_dir, 'x86')
            if os.path.exists(x86_dir):
                print(f"32位DLL目录: {x86_dir}")
                for dll_name in ['libusb-1.0.dll', 'USB2XXX.dll']:
                    dll_path = os.path.join(x86_dir, dll_name)
                    exists = os.path.exists(dll_path)
                    print(f"  {dll_name}: 存在={exists}")

def check_path_environment():
    """检查PATH环境变量"""
    print_header("PATH环境变量检查")
    
    path = os.environ.get('PATH', '')
    path_dirs = path.split(';')
    
    print(f"PATH环境变量包含 {len(path_dirs)} 个目录")
    
    # 查找USB2CAN相关目录
    usb2can_dirs = []
    for i, dir_path in enumerate(path_dirs):
        if 'USB2CAN' in dir_path.upper():
            usb2can_dirs.append((i, dir_path))
    
    if usb2can_dirs:
        print("找到USB2CAN相关目录:")
        for idx, dir_path in usb2can_dirs:
            print(f"  [{idx}] {dir_path}")
    else:
        print("未找到USB2CAN相关目录")
    
    # 检查当前脚本是否在PATH中
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir in path_dirs:
        print(f"当前脚本目录在PATH中: {current_dir}")
    else:
        print(f"当前脚本目录不在PATH中: {current_dir}")

def test_dll_loading():
    """测试DLL加载"""
    print_header("DLL加载测试")
    
    # 获取USB2CAN目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    usb2can_dir = os.path.join(os.path.dirname(current_dir), 'USB2CAN')
    
    # 测试libusb-1.0.dll加载
    print("测试libusb-1.0.dll加载:")
    libusb_paths = [
        'libusb-1.0.dll',
        os.path.join(usb2can_dir, 'libusb-1.0.dll'),
    ]
    
    # 添加libs目录
    windows_libs_dir = os.path.join(usb2can_dir, 'libs', 'windows')
    if os.path.exists(windows_libs_dir):
        libusb_paths.append(os.path.join(windows_libs_dir, 'x86_64', 'libusb-1.0.dll'))
        libusb_paths.append(os.path.join(windows_libs_dir, 'x86', 'libusb-1.0.dll'))
    
    loaded = False
    for path in libusb_paths:
        try:
            print(f"  尝试加载: {path}")
            if os.path.exists(path):
                cdll.LoadLibrary(path)
                print(f"  成功加载: {path}")
                loaded = True
                break
            else:
                print(f"  文件不存在: {path}")
        except Exception as e:
            print(f"  加载失败: {e}")
    
    if not loaded:
        print("  libusb-1.0.dll加载失败")
    
    # 测试USB2XXX.dll加载
    print("\n测试USB2XXX.dll加载:")
    usb2xxx_paths = [
        'USB2XXX.dll',
        os.path.join(usb2can_dir, 'USB2XXX.dll'),
    ]
    
    # 添加libs目录
    if os.path.exists(windows_libs_dir):
        usb2xxx_paths.append(os.path.join(windows_libs_dir, 'x86_64', 'USB2XXX.dll'))
        usb2xxx_paths.append(os.path.join(windows_libs_dir, 'x86', 'USB2XXX.dll'))
    
    loaded = False
    for path in usb2xxx_paths:
        try:
            print(f"  尝试加载: {path}")
            if os.path.exists(path):
                cdll.LoadLibrary(path)
                print(f"  成功加载: {path}")
                loaded = True
                break
            else:
                print(f"  文件不存在: {path}")
        except Exception as e:
            print(f"  加载失败: {e}")
    
    if not loaded:
        print("  USB2XXX.dll加载失败")

def test_usb_scan():
    """测试USB设备扫描"""
    print_header("USB设备扫描测试")
    
    try:
        # 尝试导入USB设备模块
        print("尝试导入USB设备模块...")
        
        # 添加USB2CAN目录到Python路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        usb2can_dir = os.path.join(os.path.dirname(current_dir), 'USB2CAN')
        sys.path.append(usb2can_dir)
        
        # 添加USB2CAN目录到系统路径
        if os.path.exists(usb2can_dir):
            os.environ['PATH'] = usb2can_dir + ';' + os.environ['PATH']
            
            # 添加libs目录
            windows_libs_dir = os.path.join(usb2can_dir, 'libs', 'windows')
            if os.path.exists(windows_libs_dir):
                x86_64_dir = os.path.join(windows_libs_dir, 'x86_64')
                if os.path.exists(x86_64_dir):
                    os.environ['PATH'] = x86_64_dir + ';' + os.environ['PATH']
                
                x86_dir = os.path.join(windows_libs_dir, 'x86')
                if os.path.exists(x86_dir):
                    os.environ['PATH'] = x86_dir + ';' + os.environ['PATH']
        
        # 尝试导入
        try:
            # 注意：在函数内部不能使用import *，改为导入特定函数
            # 先尝试加载DLL
            try:
                usb_device_dll = cdll.LoadLibrary('USB2XXX.dll')
                print("成功加载USB2XXX.dll")
                
                # 定义函数原型
                # USB_ScanDevice接受一个c_uint数组的指针
                usb_device_dll.USB_ScanDevice.argtypes = [POINTER(c_uint * 20)]
                usb_device_dll.USB_ScanDevice.restype = c_int
                
                usb_device_dll.USB_OpenDevice.argtypes = [c_uint]
                usb_device_dll.USB_OpenDevice.restype = c_bool
                
                usb_device_dll.USB_CloseDevice.argtypes = [c_uint]
                usb_device_dll.USB_CloseDevice.restype = c_bool
                
                # 定义DEVICE_INFO结构体
                class DEVICE_INFO(Structure):
                    _fields_ = [
                        ("FirmwareVersion", c_uint),
                        ("HardwareVersion", c_uint),
                        ("BuildDate", c_uint * 3),
                        ("SerialNumber", c_uint * 3),
                        ("Functions", c_uint)
                    ]
                
                usb_device_dll.DEV_GetDeviceInfo.argtypes = [c_uint, POINTER(DEVICE_INFO), POINTER(c_char * 256)]
                usb_device_dll.DEV_GetDeviceInfo.restype = c_bool
                
                print("成功导入USB设备模块（通过直接加载DLL）")
                
                # 创建函数别名
                USB_ScanDevice = usb_device_dll.USB_ScanDevice
                USB_OpenDevice = usb_device_dll.USB_OpenDevice
                USB_CloseDevice = usb_device_dll.USB_CloseDevice
                DEV_GetDeviceInfo = usb_device_dll.DEV_GetDeviceInfo
                
            except Exception as dll_error:
                print(f"直接加载DLL失败: {dll_error}")
                # 尝试从模块导入
                import usb_device
                import usb2can
                print("成功导入USB设备模块（通过Python模块）")
                
                # 从模块获取函数
                USB_ScanDevice = usb_device.USB_ScanDevice
                USB_OpenDevice = usb_device.USB_OpenDevice
                USB_CloseDevice = usb_device.USB_CloseDevice
                DEV_GetDeviceInfo = usb_device.DEV_GetDeviceInfo
            
            # 测试设备扫描
            print("\n开始设备扫描...")
            DevHandles = (c_uint * 20)()
            
            # 尝试多次扫描
            for attempt in range(3):
                print(f"第 {attempt+1} 次扫描尝试...")
                ret = USB_ScanDevice(byref(DevHandles))
                print(f"扫描结果: 检测到 {ret} 个设备")
                
                if ret > 0:
                    print("设备句柄:")
                    for i in range(ret):
                        print(f"  设备{i}: 句柄={DevHandles[i]}")
                    
                    # 尝试打开第一个设备
                    if ret > 0:
                        print(f"\n尝试打开第一个设备 (句柄={DevHandles[0]})...")
                        ret_open = USB_OpenDevice(DevHandles[0])
                        print(f"打开设备结果: {bool(ret_open)}")
                        
                        if bool(ret_open):
                            # 获取设备信息
                            USB2XXXInfo = DEVICE_INFO()
                            USB2XXXFunctionString = (c_char * 256)()
                            ret_info = DEV_GetDeviceInfo(DevHandles[0], byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                            
                            if bool(ret_info):
                                # 构建序列号
                                serial_parts = []
                                for j in range(3):
                                    serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                                device_serial = ''.join(serial_parts)
                                
                                # 获取设备功能
                                function_string = bytes(USB2XXXFunctionString.value).decode('ascii')
                                
                                print(f"设备信息:")
                                print(f"  序列号: {device_serial}")
                                print(f"  功能: {function_string}")
                                print(f"  固件版本: {USB2XXXInfo.FirmwareVersion}")
                                print(f"  硬件版本: {USB2XXXInfo.HardwareVersion}")
                            else:
                                print("获取设备信息失败")
                            
                            # 关闭设备
                            USB_CloseDevice(DevHandles[0])
                            print("设备已关闭")
                        else:
                            print("打开设备失败")
                    
                    break  # 成功扫描到设备，跳出循环
                else:
                    print("未检测到设备")
                    if attempt < 2:
                        print("等待1秒后重试...")
                        time.sleep(1)
            
        except ImportError as e:
            print(f"导入USB设备模块失败: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"USB设备扫描测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_usb_drivers():
    """检查USB驱动"""
    print_header("USB驱动检查")
    
    if platform.system() != "Windows":
        print("当前不是Windows系统，跳过驱动检查")
        return
    
    try:
        import winreg
        
        # 检查USB设备驱动
        print("检查USB设备驱动注册表...")
        
        # USB设备相关注册表键
        usb_keys = [
            r"SYSTEM\CurrentControlSet\Services\usbccgp",
            r"SYSTEM\CurrentControlSet\Services\usbehci",
            r"SYSTEM\CurrentControlSet\Services\usbhub",
            r"SYSTEM\CurrentControlSet\Services\usbohci",
            r"SYSTEM\CurrentControlSet\Services\usbprint",
            r"SYSTEM\CurrentControlSet\Services\usbscan",
            r"SYSTEM\CurrentControlSet\Services\usbstor",
            r"SYSTEM\CurrentControlSet\Services\usbuhci",
        ]
        
        for key_path in usb_keys:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                print(f"  {key_path}: 存在")
                winreg.CloseKey(key)
            except WindowsError:
                print(f"  {key_path}: 不存在")
                
    except ImportError:
        print("无法导入winreg模块")
    except Exception as e:
        print(f"检查USB驱动失败: {e}")

def main():
    """主函数"""
    print("USB-CAN设备诊断脚本")
    print("版本: 1.0")
    print("日期: 2026-02-07")
    print("="*80)
    
    # 执行所有检查
    check_environment()
    check_dll_files()
    check_path_environment()
    test_dll_loading()
    check_usb_drivers()
    test_usb_scan()
    
    print_header("诊断完成")
    print("请将以上输出信息提供给开发人员进行分析")

if __name__ == "__main__":
    main()