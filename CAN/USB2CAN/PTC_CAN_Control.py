#coding:utf-8
from ctypes import *
import platform
import os
from time import sleep

# 直接加载USB2XXX.dll
if platform.system() == "Windows":
    if "64bit" in platform.architecture():
        USB2XXXLib = windll.LoadLibrary(os.getcwd() + "/USB2XXX.dll")
    else:
        USB2XXXLib = windll.LoadLibrary(os.getcwd() + "/USB2XXX.dll")
else:
    print("Unsupported system!")
    exit()

# 定义必要的数据结构
class DEVICE_INFO(Structure):
    _fields_ = [
        ("FirmwareName", c_char*32),   # firmware name string
        ("BuildDate", c_char*32),      # firmware build date and time string
        ("HardwareVersion", c_uint),   # hardware version
        ("FirmwareVersion",c_uint),    # firmware version
        ("SerialNumber",c_uint*3),     # USB2XXX serial number
        ("Functions",c_uint)           # USB2XXX functions
    ]

class CAN_MSG(Structure):
    _fields_ = [
        ("ID",c_uint),              # 报文ID。
        ("TimeStamp",c_uint),       # 接收到信息帧时的时间标识，从CAN 控制器初始化开始计时。
        ("RemoteFlag",c_ubyte),     # 是否是远程帧
        ("ExternFlag",c_ubyte),     # 是否是扩展帧
        ("DataLen",c_ubyte),        # 数据长度(<=8)，即Data 的长度。
        ("Data",c_ubyte*8),         # 报文的数据。
        ("TimeStampHigh",c_ubyte)   # 时间戳高位
    ]

class CAN_INIT_CONFIG(Structure):
    _fields_ = [
        ("CAN_BRP_CFG3",c_uint),    # 取值范围1~1024
        ("CAN_SJW",c_ubyte),    # 取值范围1~4
        ("CAN_BS1_CFG1",c_ubyte),    # 取值范围1~16
        ("CAN_BS2_CFG2",c_ubyte),    # 取值范围1~8
        ("CAN_Mode",c_ubyte),   # CAN工作模式，0-正常模式，1-环回模式，2-静默模式，3-静默环回模式
        ("CAN_ABOM",c_ubyte),   # 自动离线管理，0-禁止，1-使能
        ("CAN_NART",c_ubyte),   # 报文重发管理，0-使能报文重传，1-禁止报文重传
        ("CAN_RFLM",c_ubyte),   # FIFO锁定管理，0-新报文覆盖旧报文，1-丢弃新报文
        ("CAN_TXFP",c_ubyte),   # 发送优先级管理，0-标识符决定，1-发送请求顺序决定
    ]

# 定义函数
CAN_SUCCESS = 0

def USB_ScanDevice(pDevHandle):
    return USB2XXXLib.USB_ScanDevice(pDevHandle)

def USB_OpenDevice(DevHandle):
    return USB2XXXLib.USB_OpenDevice(DevHandle)

def USB_CloseDevice(DevHandle):
    return USB2XXXLib.USB_CloseDevice(DevHandle)

def DEV_GetDeviceInfo(DevHandle, pDevInfo, pFunctionStr):
    return USB2XXXLib.DEV_GetDeviceInfo(DevHandle, pDevInfo, pFunctionStr)

def DEV_GetDllBuildTime(pDateTime):
    return USB2XXXLib.DEV_GetDllBuildTime(pDateTime)

def CAN_GetCANSpeedArg(DevHandle, pCanConfig, SpeedBps):
    return USB2XXXLib.CAN_GetCANSpeedArg(DevHandle, pCanConfig, SpeedBps)

def CAN_Init(DevHandle, CANIndex, pCanConfig):
    return USB2XXXLib.CAN_Init(DevHandle, CANIndex, pCanConfig)

def CAN_SendMsg(DevHandle, CANIndex, pCanSendMsg, SendMsgNum):
    return USB2XXXLib.CAN_SendMsg(DevHandle, CANIndex, pCanSendMsg, SendMsgNum)

def CAN_GetMsg(DevHandle, CANIndex, pCanGetMsg):
    return USB2XXXLib.CAN_GetMsg(DevHandle, CANIndex, pCanGetMsg)

def DBC_ParserFile(DevHandle, pDBCFileName):
    USB2XXXLib.DBC_ParserFile.restype = c_uint64
    return USB2XXXLib.DBC_ParserFile(DevHandle, pDBCFileName)

def DBC_GetMsgQuantity(DBCHandle):
    return USB2XXXLib.DBC_GetMsgQuantity(DBCHandle)

def DBC_GetMsgName(DBCHandle, index, pMsgName):
    return USB2XXXLib.DBC_GetMsgName(DBCHandle, index, pMsgName)

def DBC_GetMsgSignalQuantity(DBCHandle, pMsgName):
    return USB2XXXLib.DBC_GetMsgSignalQuantity(DBCHandle, pMsgName)

def DBC_GetMsgSignalName(DBCHandle, pMsgName, index, pSignalName):
    return USB2XXXLib.DBC_GetMsgSignalName(DBCHandle, pMsgName, index, pSignalName)

def DBC_SetSignalValue(DBCHandle, pMsgName, pSignalName, Value):
    return USB2XXXLib.DBC_SetSignalValue(DBCHandle, pMsgName, pSignalName, Value)

def DBC_SyncValueToCANMsg(DBCHandle, pMsgName, pCANMsg):
    return USB2XXXLib.DBC_SyncValueToCANMsg(DBCHandle, pMsgName, pCANMsg)

def DBC_SyncCANMsgToValue(DBCHandle, pCANMsg, MsgLen):
    return USB2XXXLib.DBC_SyncCANMsgToValue(DBCHandle, pCANMsg, MsgLen)

def DBC_GetSignalValueStr(DBCHandle, pMsgName, pSignalName, pValueStr):
    return USB2XXXLib.DBC_GetSignalValueStr(DBCHandle, pMsgName, pSignalName, pValueStr)

if __name__ == '__main__': 
    libBuildData = (c_char * 32)()
    # 获取库编译日期
    DEV_GetDllBuildTime(byref(libBuildData))
    print("lib build date time: %s"%bytes(libBuildData).decode('ascii'))
    
    # 定义CAN通道
    CAN_CHANNEL = 0  # CAN1通道
    CAN_ID = 0x5300023b  # CAN ID
    
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
    # 获取波特率参数 (500Kbps)
    ret = CAN_GetCANSpeedArg(DevHandles[0],byref(CANConfig),500000)
    if(ret != CAN_SUCCESS):
        print("Get CAN speed failed!")
        exit()
    else:
        print("Get CAN speed Success!")
    
    # 初始化CAN1通道
    ret = CAN_Init(DevHandles[0], CAN_CHANNEL, byref(CANConfig))
    if(ret != CAN_SUCCESS):
        print("Config CAN channel failed!")
        exit()
    else:
        print("Config CAN channel Success!")
    
    # 解析DBC文件
    dbc_file_path = "d:\\老化CAN通讯\\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc"
    DBCHandle = DBC_ParserFile(DevHandles[0], dbc_file_path.encode('gbk'))
    if(DBCHandle==0):
        print("Parser DBC File error!")
        exit()
    else:
        print("Parser DBC File success!")
    
    # 打印DBC里面报文和信号相关信息
    DBCMsgNum = DBC_GetMsgQuantity(c_uint64(DBCHandle))
    print("Total messages in DBC: %d"%DBCMsgNum)
    
    # 查找相关报文信息
    for i in range(0, DBCMsgNum):
        MsgName = (c_char * 64)()
        DBC_GetMsgName(c_uint64(DBCHandle), i, MsgName)
        msg_name = bytes(MsgName.value).decode('ascii')
        if msg_name in ["ECC_0x4E0", "PTC_0x524", "PTC_0x525"]:
            print("\nFound message: %s"%msg_name)
            DBCSigNum = DBC_GetMsgSignalQuantity(c_uint64(DBCHandle), MsgName)
            print("Signals:")
            for j in range(0, DBCSigNum):
                SigName = (c_char * 64)()
                DBC_GetMsgSignalName(c_uint64(DBCHandle), MsgName, j, SigName)
                print("\t%s "%bytes(SigName.value).decode('ascii'))
    
    try:
        # 设置PTC控制参数
        print("\n=== Setting PTC Control Parameters ===")
        
        # 设置目标功率 (例如设置为2000W)
        target_power = 2000
        print("Target Power: %d W"%target_power)
        DBC_SetSignalValue(c_uint64(DBCHandle), b"ECC_0x4E0", b"ECC_TarPwr_PTC", c_double(target_power))
        
        # 设置使能命令 (1-制热使能模式)
        enable_cmd = 1
        print("Enable Command: %d"%enable_cmd)
        DBC_SetSignalValue(c_uint64(DBCHandle), b"ECC_0x4E0", b"ECC_EnaCmd_PTC", c_double(enable_cmd))
        
        # 设置目标档位 (例如设置为3档)
        target_gear = 3
        print("Target Gear: %d"%target_gear)
        DBC_SetSignalValue(c_uint64(DBCHandle), b"ECC_0x4E0", b"ECC_TarGear_PTC", c_double(target_gear))
        
        # 将信号值填入CAN消息里面
        CanMsg = (CAN_MSG*1)()
        DBC_SyncValueToCANMsg(c_uint64(DBCHandle), b"ECC_0x4E0", byref(CanMsg[0]))
        
        # 发送CAN控制报文
        print("\n=== Sending Control Message ===")
        print("Message ID: 0x%08X"%CanMsg[0].ID)
        print("Data Length: %d"%CanMsg[0].DataLen)
        print("Data: ", end='')
        for j in range(0, CanMsg[0].DataLen):
            print("%02X "%CanMsg[0].Data[j], end='')
        print("")
        
        SendedNum = CAN_SendMsg(DevHandles[0], CAN_CHANNEL, CanMsg, 1)
        if(SendedNum >= 0):
            print("Success send frames: %d"%SendedNum)
        else:
            print("Send CAN data failed! %d"%SendedNum)
        
        # 等待反馈
        sleep(1)
        
        # 读取CAN数据
        print("\n=== Reading Feedback Data ===")
        CanMsgBuffer = (CAN_MSG*1024)()
        CanNum = CAN_GetMsg(DevHandles[0], CAN_CHANNEL, byref(CanMsgBuffer))
        
        if CanNum > 0:
            print("Received %d CAN messages"%CanNum)
            
            # 处理接收到的消息
            for i in range(0, CanNum):
                msg_id = CanMsgBuffer[i].ID
                print("\nMessage ID: 0x%08X"%msg_id)
                print("TimeStamp: %d"%CanMsgBuffer[i].TimeStamp)
                print("Data Length: %d"%CanMsgBuffer[i].DataLen)
                print("Data: ", end='')
                for j in range(0, CanMsgBuffer[i].DataLen):
                    print("%02X "%CanMsgBuffer[i].Data[j], end='')
                print("")
            
            # 将CAN消息数据填充到信号里面
            DBC_SyncCANMsgToValue(c_uint64(DBCHandle), CanMsgBuffer, CanNum)
            
            # 读取PTC_0x524报文的实际功率
            ValueStr = (c_char * 64)()
            DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x524", b"PTC_CrtPwr", ValueStr)
            print("\n=== PTC Feedback Data ===")
            print("Actual Power (PTC_CrtPwr): %s"%bytes(ValueStr.value).decode('ascii'))
            
            # 读取PTC_0x524报文的其他信息
            DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x524", b"PTC_CrtT", ValueStr)
            print("Current Temperature (PTC_CrtT): %s"%bytes(ValueStr.value).decode('ascii'))
            
            DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x524", b"PTC_ActGear", ValueStr)
            print("Actual Gear (PTC_ActGear): %s"%bytes(ValueStr.value).decode('ascii'))
            
            DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x524", b"PTC_Mod", ValueStr)
            print("Current Mode (PTC_Mod): %s"%bytes(ValueStr.value).decode('ascii'))
            
            # 读取PTC_0x525报文的信息
            if DBC_GetMsgSignalQuantity(c_uint64(DBCHandle), b"PTC_0x525") > 0:
                DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x525", b"PTC_Crt", ValueStr)
                print("Current Current (PTC_Crt): %s"%bytes(ValueStr.value).decode('ascii'))
                
                DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x525", b"PTC_CrtVolt", ValueStr)
                print("Current Voltage (PTC_CrtVolt): %s"%bytes(ValueStr.value).decode('ascii'))
                
                DBC_GetSignalValueStr(c_uint64(DBCHandle), b"PTC_0x525", b"PTC_CrtSts", ValueStr)
                print("Current Status (PTC_CrtSts): %s"%bytes(ValueStr.value).decode('ascii'))
        
        elif CanNum == 0:
            print("No CAN data received!")
        else:
            print("Get CAN data error!")
            
    except Exception as e:
        print("\nError occurred: %s"%str(e))
    
    finally:
        # 关闭设备
        print("\n=== Closing Device ===")
        ret = USB_CloseDevice(DevHandles[0])
        if(bool(ret)):
            print("Close device success!")
        else:
            print("Close device faild!")
            exit()
        
        print("\nPTC CAN Control finished!")
