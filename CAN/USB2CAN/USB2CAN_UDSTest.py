#coding:utf-8
from ctypes import *
import platform
from time import sleep
from usb_device import *
from usb2can import *
from can_uds import *


if __name__ == '__main__': 
    libBuildData = (c_char * 32)()
    # 获取库编译日期
    DEV_GetDllBuildTime(byref(libBuildData))
    print("lib build date time: %s"%bytes(libBuildData).decode('ascii'))
    CAN1 = 0
    DevHandles = (c_uint * 20)()
    # 扫描设备并将设备号存放到设备号数组中
    ret = USB_ScanDevice(byref(DevHandles))
    if(ret == 0):
        print("No device connected!")
        exit()
    else:
        print("Have %d device connected!"%ret)
    # 打开设备
    ret = USB_OpenDevice(DevHandles[0])
    if(bool(ret)):
        print("Open device success!")
    else:
        print("Open device faild!")
        exit()
    # 获取设备固件信息
    USB2XXXInfo = DEVICE_INFO()
    USB2XXXFunctionString = (c_char * 256)()
    ret = DEV_GetDeviceInfo(DevHandles[0],byref(USB2XXXInfo),byref(USB2XXXFunctionString))
    if(bool(ret)):
        print("USB2XXX device infomation:")
        print("--Firmware Name: %s"%bytes(USB2XXXInfo.FirmwareName).decode('ascii'))
        print("--Firmware Version: v%d.%d.%d"%((USB2XXXInfo.FirmwareVersion>>24)&0xFF,(USB2XXXInfo.FirmwareVersion>>16)&0xFF,USB2XXXInfo.FirmwareVersion&0xFFFF))
        print("--Hardware Version: v%d.%d.%d"%((USB2XXXInfo.HardwareVersion>>24)&0xFF,(USB2XXXInfo.HardwareVersion>>16)&0xFF,USB2XXXInfo.HardwareVersion&0xFFFF))
        print("--Build Date: %s"%bytes(USB2XXXInfo.BuildDate).decode('ascii'))
        print("--Serial Number: ",end='')
        for i in range(0, len(USB2XXXInfo.SerialNumber)):
            print("%08X"%USB2XXXInfo.SerialNumber[i],end='')
        print("")
        print("--Function String: %s"%bytes(USB2XXXFunctionString.value).decode('ascii'))
    else:
        print("Get device infomation faild!")
        exit()
    # 初始化CAN
    CANConfig = CAN_INIT_CONFIG()
    # 获取波特率参数
    ret = CAN_GetCANSpeedArg(DevHandles[0],byref(CANConfig),500000)
    if(ret != CAN_SUCCESS):
        print("Get CAN speed failed!")
        exit()
    else:
        print("Get CAN speed Success!")
    ret = CAN_Init(DevHandles[0],CAN1,byref(CANConfig))
    if(ret != CAN_SUCCESS):
        print("Config CAN failed!")
        exit()
    else:
        print("Config CAN Success!")
    # 请求数据
    CANUdsAddr = CAN_UDS_ADDR()
    CANUdsAddr.Flag = 0 #使用标准帧
    CANUdsAddr.AddrFormats = 0
    CANUdsAddr.ReqID = 0x733 #请求数据ID
    CANUdsAddr.ResID = 0x73B #响应数据ID
    CANUdsAddr.MaxDLC = 8 #单帧最大字节数
    req_data = (c_char * 3)()
    req_data[0] = 0x22
    req_data[1] = 0xF1
    req_data[2] = 0x13
    req_data = (c_char * 3)()
    res_data = (c_char * 4096)()
    ret = CAN_UDS_Request(DevHandles[0],CAN1,byref(CANUdsAddr),req_data,3)
    if(ret != CAN_UDS_OK):
        print("UDS Request failed!")
        exit()
    else:
        print("UDS Request Success!")
    ret = CAN_UDS_Response(DevHandles[0],CAN1,byref(CANUdsAddr),res_data,1000)
    if(ret > 0):
        for i in range(0,ret):
            print("%02X "%res_data[i],end='')
        print("")
    else:
        print("UDS Response failed!")
    # Close device
    ret = USB_CloseDevice(DevHandles[0])
    if(bool(ret)):
        print("Close device success!")
    else:
        print("Close device faild!")
        exit()
