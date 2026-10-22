"""
文件说明：USB2XXX LIN相关函数测试程序
更多帮助：www.usbxyz.com
"""
from ctypes import *
import platform
from time import sleep
from usb_device import *
from usb2lin_ex import *
from lin_uds import *

if __name__ == '__main__': 
    LINMasterIndex = 0
    DevHandles = (c_uint * 20)()
    # Scan device
    ret = USB_ScanDevice(byref(DevHandles))
    if(ret == 0):
        print("No device connected!")
        exit()
    else:
        print("Have %d device connected!"%ret)
    # Open device
    ret = USB_OpenDevice(DevHandles[0])
    if(bool(ret)):
        print("Open device success!")
    else:
        print("Open device faild!")
        exit()
    # Get device infomation
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

    # 初始化配置主LIN
    ret = LIN_EX_Init(DevHandles[0],LINMasterIndex,19200,LIN_EX_MASTER)
    if ret != LIN_EX_SUCCESS:
        print("Config Master LIN failed!")
        exit()
    else:
        print("Config Master LIN Success!")

    UDSAddr = LIN_UDS_ADDR()
    UDSAddr.ReqID = 0x3C
    UDSAddr.ResID = 0x3D
    UDSAddr.NAD = 0x7F
    UDSAddr.CheckType = 0
    UDSAddr.STmin = 5
    data_buffer = (c_byte*8)(0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88)
    ret = LIN_UDS_Request(DevHandles[0],LINMasterIndex,byref(UDSAddr),data_buffer,8)
    if ret != LIN_UDS_OK:
        print("LIN_UDS_Request failed!")
        exit()
    else:
        print("LIN_UDS_Request success!")
    sleep(0.01)
    ret = LIN_UDS_Response(DevHandles[0],LINMasterIndex,byref(UDSAddr),data_buffer,100)
    print("Response:")
    for i in range(ret):
        print("0x%02X "%LINOutMsg.Data[i],end='')
    print("")
    # Close device
    ret = USB_CloseDevice(DevHandles[0])
    if(bool(ret)):
        print("Close device success!")
    else:
        print("Close device faild!")
        exit()
