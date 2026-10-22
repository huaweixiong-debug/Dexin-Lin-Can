"""
文件说明：USB2XXX设备操作相关函数集合
更多帮助：www.toomoss.com
使用说明：程序正常运行，需要将sdk/libs目录复制到程序目录下
"""

from ctypes import *
import platform
import os
import shutil

# Device info define
USB2XXXLib_available = False

class DEVICE_INFO(Structure):
    _fields_ = [
        ("FirmwareName", c_char*32),   # firmware name string
        ("BuildDate", c_char*32),      # firmware build date and time string
        ("HardwareVersion", c_uint),   # hardware version
        ("FirmwareVersion",c_uint),    # firmware version
        ("SerialNumber",c_uint*3),     # USB2XXX serial number
        ("Functions",c_uint)           # USB2XXX functions
    ]

# 定义电压输出值
POWER_LEVEL_NONE    = 0 # 不输出
POWER_LEVEL_1V8     = 1 # 输出1.8V
POWER_LEVEL_2V5     = 2 # 输出2.5V
POWER_LEVEL_3V3     = 3 # 输出3.3V
POWER_LEVEL_5V0     = 4 # 输出5.0V

# 检查libs目录是否存在，使用绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(current_dir, "libs")

if(not os.path.exists(libs_dir)):
    # 尝试从LGV2目录复制libs
    lgv2_libs_path = os.path.join(current_dir, "..", "LGV2", "CANLINSW例子", "usb2can_lin_pwm_example-master", "sdk", "libs")
    
    if(os.path.exists(lgv2_libs_path)):
        print(f"从LGV2目录复制libs到: {libs_dir}")
        shutil.copytree(lgv2_libs_path, libs_dir)
    else:
        print(f"libs目录不存在: {libs_dir}")
        print("请确保libs目录在USB2CAN目录下")
        exit()

#根据系统自动导入对应的库文件，若没能识别到正确的系统，可以修改下面的源码
if(platform.system()=="Windows"):
    # 尝试多种架构的DLL文件
    libs_dir = os.path.join(current_dir, "libs", "windows")
    
    # 尝试1: 64位DLL with cdll
    print("\n=== 尝试1: 64位DLL (cdll) ===")
    try:
        from ctypes import cdll
        libusb_path = os.path.join(libs_dir, "x86_64", "libusb-1.0.dll")
        usb2xxx_path = os.path.join(libs_dir, "x86_64", "USB2XXX.dll")
        print(f"libusb-1.0.dll: {libusb_path}")
        print(f"USB2XXX.dll: {usb2xxx_path}")
        
        # 检查文件是否存在
        if not os.path.exists(libusb_path):
            print(f"错误: libusb-1.0.dll 文件不存在: {libusb_path}")
            raise FileNotFoundError(f"libusb-1.0.dll not found")
        
        if not os.path.exists(usb2xxx_path):
            print(f"错误: USB2XXX.dll 文件不存在: {usb2xxx_path}")
            raise FileNotFoundError(f"USB2XXX.dll not found")
        
        cdll.LoadLibrary(libusb_path)
        USB2XXXLib = cdll.LoadLibrary(usb2xxx_path)
        USB2XXXLib_available = True
        print("64位DLL加载成功！")
    except Exception as e:
        print(f"64位DLL加载失败: {str(e)}")
        
        # 尝试2: 64位DLL with windll (可能在某些系统上有效)
        print("\n=== 尝试2: 64位DLL (windll) ===")
        try:
            from ctypes import windll
            windll.LoadLibrary(libusb_path)
            USB2XXXLib = windll.LoadLibrary(usb2xxx_path)
            USB2XXXLib_available = True
            print("64位DLL加载成功！")
        except Exception as e:
            print(f"64位DLL加载失败: {str(e)}")
            
            # 尝试3: 32位DLL with windll
            print("\n=== 尝试3: 32位DLL (windll) ===")
            try:
                libusb_path = os.path.join(libs_dir, "x86", "libusb-1.0.dll")
                usb2xxx_path = os.path.join(libs_dir, "x86", "USB2XXX.dll")
                print(f"libusb-1.0.dll: {libusb_path}")
                print(f"USB2XXX.dll: {usb2xxx_path}")
                
                # 检查文件是否存在
                if not os.path.exists(libusb_path):
                    print(f"错误: libusb-1.0.dll 文件不存在: {libusb_path}")
                    raise FileNotFoundError(f"libusb-1.0.dll not found")
                
                if not os.path.exists(usb2xxx_path):
                    print(f"错误: USB2XXX.dll 文件不存在: {usb2xxx_path}")
                    raise FileNotFoundError(f"USB2XXX.dll not found")
                
                windll.LoadLibrary(libusb_path)
                USB2XXXLib = windll.LoadLibrary(usb2xxx_path)
                USB2XXXLib_available = True
                print("32位DLL加载成功！")
            except Exception as e:
                print(f"32位DLL加载失败: {str(e)}")
                
                # 尝试4: 32位DLL with cdll
                print("\n=== 尝试4: 32位DLL (cdll) ===")
                try:
                    from ctypes import cdll
                    cdll.LoadLibrary(libusb_path)
                    USB2XXXLib = cdll.LoadLibrary(usb2xxx_path)
                    USB2XXXLib_available = True
                    print("32位DLL加载成功！")
                except Exception as e:
                    print(f"32位DLL加载失败: {str(e)}")
                    
                    # 所有尝试都失败
                    print("\n=== 错误: 无法加载DLL文件 ===")
                    print("请确保：")
                    print("1. Python环境与DLL架构匹配")
                    print("2. libs/windows目录下有正确架构的DLL文件")
                    print("3. DLL文件未损坏且可访问")
                    exit(1)
elif(platform.system()=="Darwin"):
    cdll.LoadLibrary(os.getcwd()+"/libs/mac_os/libusb-1.0.dylib" )
    USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/libs/mac_os/libUSB2XXX.dylib" )
elif(platform.system()=="Linux"):
    if 'armv7' in platform.machine():
        cdll.LoadLibrary(os.getcwd()+"/libs/linux/armv7/libusb-1.0.so" )
        USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/libs/linux/armv7/libUSB2XXX.so" )
    elif 'mips64' in platform.machine():
        cdll.LoadLibrary(os.getcwd()+"/libs/linux/mips64/libusb-1.0.so" )
        USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/libs/linux/mips64/libUSB2XXX.so" )
    elif 'aarch64' in platform.machine():
        cdll.LoadLibrary(os.getcwd()+"/libs/linux/aarch64/libusb-1.0.so" )
        USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/libs/linux/aarch64/libUSB2XXX.so" )
    elif 'arm64' in platform.machine():
        cdll.LoadLibrary(os.getcwd()+"/libs/linux/arm64/libusb-1.0.so" )
        USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/libs/linux/arm64/libUSB2XXX.so" )
    else:
        if "64bit" in platform.architecture():
            cdll.LoadLibrary(os.getcwd()+"/libs/linux/x86_64/libusb-1.0.so" )
            USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/lib/linux/x86_64/libUSB2XXX.so" )
        else:
            cdll.LoadLibrary(os.getcwd()+"/libs/linux/x86/libusb-1.0.so" )
            USB2XXXLib = cdll.LoadLibrary(os.getcwd()+"/libs/linux/x86/libUSB2XXX.so" )
else:
    print("unsupported system")
    exit()

# Scan device
def USB_ScanDevice(pDevHandle):
    return USB2XXXLib.USB_ScanDevice(pDevHandle)

# Open device
def USB_OpenDevice(DevHandle):
    return USB2XXXLib.USB_OpenDevice(DevHandle)

# Reset device
def USB_ResetDevice(DevHandle):
    return USB2XXXLib.USB_ResetDevice(DevHandle)

# Get USB2XXX infomation
def DEV_GetDeviceInfo(DevHandle, pDevInfo, pFunctionStr):
    return USB2XXXLib.DEV_GetDeviceInfo(DevHandle, pDevInfo, pFunctionStr)

# Close device
def USB_CloseDevice(DevHandle):
    return USB2XXXLib.USB_CloseDevice(DevHandle)

def DEV_EraseUserData(DevHandle):
    return USB2XXXLib.DEV_EraseUserData(DevHandle)

def DEV_WriteUserData(DevHandle,OffsetAddr,pWriteData,DataLen):
    return USB2XXXLib.DEV_WriteUserData(DevHandle,OffsetAddr,pWriteData,DataLen)

def DEV_ReadUserData(DevHandle,OffsetAddr,pReadData,DataLen):
    return USB2XXXLib.DEV_ReadUserData(DevHandle,OffsetAddr,pReadData,DataLen)

def DEV_SetPowerLevel(DevHandle,PowerLevel):
    return USB2XXXLib.DEV_SetPowerLevel(DevHandle,PowerLevel)

def DEV_GetTimestamp(DevHandle,BusType,pTimestamp):
    return USB2XXXLib.DEV_GetTimestamp(DevHandle,BusType,pTimestamp)


