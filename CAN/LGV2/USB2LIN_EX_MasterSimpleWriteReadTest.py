"""
文件说明：USB2XXX LIN相关函数测试程序
更多帮助：www.usbxyz.com
"""
from ctypes import *
import platform
from time import sleep
from usb_device import *
from usb2lin_ex import *

if __name__ == '__main__':
    LINMasterIndex = 0  # LIN主站索引
    DevHandles = (c_uint * 20)()
    # Scan device
    ret = USB_ScanDevice(byref(DevHandles))
    if (ret == 0):
        print("No device connected!")
        exit()
    else:
        print("Have %d device connected!" % ret)
    # Open device
    ret = USB_OpenDevice(DevHandles[0])
    if (bool(ret)):
        print("Open device success!")
    else:
        print("Open device faild!")
        exit()
    # Get device infomation
    USB2XXXInfo = DEVICE_INFO()
    USB2XXXFunctionString = (c_char * 256)()
    ret = DEV_GetDeviceInfo(DevHandles[0], byref(USB2XXXInfo), byref(USB2XXXFunctionString))
    if (bool(ret)):
        print("USB2XXX device infomation:")
        print("--Firmware Name: %s" % bytes(USB2XXXInfo.FirmwareName).decode('ascii'))
        print("--Firmware Version: v%d.%d.%d" % ((USB2XXXInfo.FirmwareVersion >> 24) & 0xFF,
                                                 (USB2XXXInfo.FirmwareVersion >> 16) & 0xFF,
                                                 USB2XXXInfo.FirmwareVersion & 0xFFFF))
        print("--Hardware Version: v%d.%d.%d" % ((USB2XXXInfo.HardwareVersion >> 24) & 0xFF,
                                                 (USB2XXXInfo.HardwareVersion >> 16) & 0xFF,
                                                 USB2XXXInfo.HardwareVersion & 0xFFFF))
        print("--Build Date: %s" % bytes(USB2XXXInfo.BuildDate).decode('ascii'))
        print("--Serial Number: ", end='')
        for i in range(0, len(USB2XXXInfo.SerialNumber)):
            print("%08X" % USB2XXXInfo.SerialNumber[i], end='')
        print("")
        print("--Function String: %s" % bytes(USB2XXXFunctionString.value).decode('ascii'))
    else:
        print("Get device infomation faild!")
        exit()

    # 初始化配置主LIN
    ret = LIN_EX_Init(DevHandles[0], LINMasterIndex, 19200, LIN_EX_MASTER)
    if ret != LIN_EX_SUCCESS:
        print("Config Master LIN failed!")
        exit()
    else:
        print("Config Master LIN Success!")

    # 发送BREAK信号（使用同步方式）
    LINOutMsg = LIN_EX_MSG()
    LINMsg = LIN_EX_MSG()
    LINMsg.MsgType = LIN_EX_MSG_TYPE_BK  # 消息类型为同步间隔信号
    LINMsg.Timestamp = 10  # 发送同步间隔信号之后延时10ms
    ret = LIN_EX_MasterSync(DevHandles[0], LINMasterIndex, byref(LINMsg), byref(LINOutMsg), 1)
    if ret != 1:
        print("Send LIN break failed!")
        exit()
    else:
        print("Send LIN break success!")

    sleep(0.01)

    # 主机写数据到ID 0x24
    data_buffer = (c_byte * 8)(0x50, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)

    # 设置消息结构体
    LINMsg.MsgType = LIN_EX_MSG_TYPE_MW  # 消息类型为主机写数据
    LINMsg.Timestamp = 10  # 发送完毕数据之后延时10ms
    LINMsg.PID = 0x24  # 要写入的ID
    LINMsg.CheckType = LIN_EX_CHECK_EXT  # 使用增强型校验
    LINMsg.DataLen = 8
    for i in range(0, LINMsg.DataLen):
        LINMsg.Data[i] = data_buffer[i]

    print("\n写入ID 0x24...")
    print("写入数据: 0x50 0x01 0x00 0x00 0x00 0x00 0x00 0x00")

    ret = LIN_EX_MasterSync(DevHandles[0], LINMasterIndex, byref(LINMsg), byref(LINOutMsg), 1)
    if ret != 1:
        print("LIN ID[0x%02X] write data failed!" % 0x24)
        exit()
    else:
        print("LIN ID[0x%02X] write data success" % 0x24)
        print("响应PID: 0x%02X" % LINOutMsg.PID)
        print("响应数据长度: %d" % LINOutMsg.DataLen)
        if LINOutMsg.DataLen > 0:
            print("响应数据:", end='')
            for i in range(LINOutMsg.DataLen):
                print("0x%02X " % LINOutMsg.Data[i], end='')
            print("")

    sleep(0.1)  # 给从设备处理时间

    # 主机从ID 0x25读取数据
    print("\n读取ID 0x25...")
    LINMsg.MsgType = LIN_EX_MSG_TYPE_MR  # 消息类型为主机读数据
    LINMsg.Timestamp = 10  # 发送完毕数据之后延时10ms
    LINMsg.PID = 0x25  # 要读取的ID
    LINMsg.CheckType = LIN_EX_CHECK_EXT  # 使用增强型校验
    LINMsg.DataLen = 8  # 期望读取的数据长度

    ret = LIN_EX_MasterSync(DevHandles[0], LINMasterIndex, byref(LINMsg), byref(LINOutMsg), 1)
    if ret != 1:
        print("LIN ID[0x%02X] read data failed!" % 0x25)
        # 尝试使用LIN_EX_MasterRead作为备用方案
        print("尝试使用LIN_EX_MasterRead函数读取...")
        read_buffer = (c_byte * 8)()
        ret2 = LIN_EX_MasterRead(DevHandles[0], LINMasterIndex, 0x25, read_buffer)
        if ret2 <= 0:
            print("LIN_EX_MasterRead也失败! ret = %d" % ret2)
        else:
            print("LIN_EX_MasterRead读取成功，数据长度: %d" % ret2)
            print("数据:", end='')
            for i in range(ret2):
                print("0x%02X " % (read_buffer[i] & 0xFF), end='')
            print("")
    else:
        print("LIN ID[0x%02X] read data success" % 0x25)
        print("读取到的数据长度: %d" % LINOutMsg.DataLen)
        if LINOutMsg.DataLen > 0:
            print("数据:", end='')
            for i in range(LINOutMsg.DataLen):
                print("0x%02X " % LINOutMsg.Data[i], end='')
            print("")
        else:
            print("警告：读取成功但数据长度为0！")

    # Close device
    ret = USB_CloseDevice(DevHandles[0])
    if (bool(ret)):
        print("\nClose device success!")
    else:
        print("\nClose device faild!")
        exit()