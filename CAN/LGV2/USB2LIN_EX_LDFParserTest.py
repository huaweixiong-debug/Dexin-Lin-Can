"""
文件说明：USB2XXX LIN LDF解析相关函数测试程序
更多帮助：www.toomoss.com
"""
from ctypes import *
import platform
from time import sleep
from usb_device import *
from ldf_parser import *
from usb2lin_ex import *

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
    #解析LDF文件并初始化LIN通道
    LDFHandle = LDF_ParserFile(DevHandles[0],0,1, b"example.ldf")
    if(LDFHandle == 0):
        print("解析LDF文件失败")
        exit()
    print("ProtocolVersion = %d"%LDF_GetProtocolVersion(c_uint64(LDFHandle)))
    print("LINSpeed = %d"%LDF_GetLINSpeed(c_uint64(LDFHandle)))
    MasterName = (c_char * 64)()
    LDF_GetMasterName(c_uint64(LDFHandle),MasterName)
    print("Master Name = %s"%bytes(MasterName.value).decode('ascii'))
    FrameLen = LDF_GetFrameQuantity(c_uint64(LDFHandle))
    for i in range(0,FrameLen):
        FrameName = (c_char * 64)()
        if (LDF_PARSER_OK == LDF_GetFrameName(c_uint64(LDFHandle), i, FrameName)):
            PublisherName = (c_char * 64)()
            LDF_GetFramePublisher(c_uint64(LDFHandle), FrameName, PublisherName)
            if (bytes(MasterName.value).decode('ascii')==bytes(PublisherName.value).decode('ascii')):
                #当前帧为主机发送数据帧
                print("[MW]Frame[%d].Name=%s  Publisher=%s"%(i, bytes(FrameName.value).decode('ascii'), bytes(PublisherName.value).decode('ascii')))
            else:
                #当前帧为主机读数据帧
                print("[MR]Frame[%d].Name=%s  Publisher=%s"%(i, bytes(FrameName.value).decode('ascii'), bytes(PublisherName.value).decode('ascii')))
            SignalNum = LDF_GetFrameSignalQuantity(c_uint64(LDFHandle), FrameName)
            for j in range(0,SignalNum):
                SignalName = (c_char * 64)()
                if (LDF_PARSER_OK == LDF_GetFrameSignalName(c_uint64(LDFHandle), FrameName, j, SignalName)):
                    print("----Signal[%d].Name=%s"%(j, bytes(SignalName.value).decode('ascii')))
    #test
    LINMsg = LIN_EX_MSG()
    LDF_SetFrameRawValue(c_uint64(LDFHandle),b"ID_DATA",LINMsg.Data)
    #主机读操作，读取从机返回的数据值
    ValueStr = (c_char * 64)();
    LDF_ExeFrameToBus(c_uint64(LDFHandle), b"ID_DATA",1);
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"ID_DATA", b"Supplier_ID", ValueStr)
    print("ID_DATA.Supplier_ID=%s"%bytes(ValueStr.value).decode('ascii'))
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"ID_DATA", b"Machine_ID", ValueStr)
    print("ID_DATA.Machine_ID=%s"%bytes(ValueStr.value).decode('ascii'))
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"ID_DATA", b"Chip_ID", ValueStr)
    print("ID_DATA.Chip_ID=%s"%bytes(ValueStr.value).decode('ascii'))
    #主机写操作，发送数据给从机
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"Reg_Set_Voltage", c_double(13.5))
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"Ramp_Time", c_double(3))
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"Cut_Off_Speed", c_double(4))
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"Exc_Limitation", c_double(15.6))
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"Derat_Shift", c_double(2))
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"MM_Request", c_double(2))
    LDF_SetSignalValue(c_uint64(LDFHandle), b"LIN_CONTROL", b"Reg_Blind", c_double(1))
    #执行调度表
    LDF_ExeSchToBus(c_uint64(LDFHandle), b"Nissan",1)
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"LIN_STATE", b"MM_State", ValueStr)
    print("LIN_STATE.MM_State=%s"%bytes(ValueStr.value).decode('ascii'))
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"LIN_STATE", b"Exc_Duty_Cycle", ValueStr)
    print("LIN_STATE.Exc_Duty_Cycle=%s"%bytes(ValueStr.value).decode('ascii'))
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"LIN_STATE", b"Exc_Current", ValueStr)
    print("LIN_STATE.Exc_Current=%s"%bytes(ValueStr.value).decode('ascii'))
    LDF_GetSignalValueStr(c_uint64(LDFHandle), b"LIN_STATE", b"iStARS_Voltage", ValueStr)
    print("LIN_STATE.iStARS_Voltage=%s"%bytes(ValueStr.value).decode('ascii'))
    exit()

