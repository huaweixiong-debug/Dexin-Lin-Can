#coding:utf-8
import os
import sys
import platform
import ctypes

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 尝试加载USB2XXX.dll
def load_usb2xxx_dll():
    print("=== 尝试加载USB2XXX.dll ===")
    if platform.system() == "Windows":
        # 使用当前工作目录定位libs文件夹（与LGV2一致）
        cwd = os.getcwd()
        libs_dir = os.path.join(cwd, "libs", "windows")
        
        # 检测Python架构
        python_arch = platform.architecture()[0]
        print(f"Python architecture: {python_arch}")
        print(f"Current working directory: {cwd}")
        print(f"Libs directory: {libs_dir}")
        
        try:
            # 根据Python架构选择正确的DLL版本和加载方式（与LGV2一致，使用windll）
            from ctypes import windll
            if python_arch == "64bit":
                libusb_path = os.path.join(libs_dir, "x86_64", "libusb-1.0.dll")
                usb2xxx_path = os.path.join(libs_dir, "x86_64", "USB2XXX.dll")
                print(f"Loading 64-bit DLLs:")
                print(f"libusb-1.0.dll: {libusb_path}")
                print(f"USB2XXX.dll: {usb2xxx_path}")
            else:
                libusb_path = os.path.join(libs_dir, "x86", "libusb-1.0.dll")
                usb2xxx_path = os.path.join(libs_dir, "x86", "USB2XXX.dll")
                print(f"Loading 32-bit DLLs:")
                print(f"libusb-1.0.dll: {libusb_path}")
                print(f"USB2XXX.dll: {usb2xxx_path}")
            
            # 检查文件是否存在
            print(f"libusb-1.0.dll exists: {os.path.exists(libusb_path)}")
            print(f"USB2XXX.dll exists: {os.path.exists(usb2xxx_path)}")
            
            # 加载DLL（与LGV2一致，使用windll）
            windll.LoadLibrary(libusb_path)
            USB2XXXLib = windll.LoadLibrary(usb2xxx_path)
            print("DLL加载成功！")
            print("USB2XXX.dll loaded successfully!")
            return USB2XXXLib
        except Exception as e:
            print(f"DLL加载失败: {str(e)}")
            return None
    else:
        print("当前系统不是Windows，无法加载USB2XXX.dll")
        return None

# 定义设备信息结构（与LGV2一致）
class DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("FirmwareName", ctypes.c_char * 32),   # firmware name string
        ("BuildDate", ctypes.c_char * 32),      # firmware build date and time string
        ("HardwareVersion", ctypes.c_uint),   # hardware version
        ("FirmwareVersion", ctypes.c_uint),    # firmware version
        ("SerialNumber", ctypes.c_uint * 3),     # USB2XXX serial number
        ("Functions", ctypes.c_uint)           # USB2XXX functions
    ]

# 定义CAN消息结构（与LGV2一致）
class CAN_MSG(ctypes.Structure):
    _fields_ = [
        ("ID", ctypes.c_uint),              # 报文ID
        ("TimeStamp", ctypes.c_uint),       # 接收到信息帧时的时间标识
        ("RemoteFlag", ctypes.c_ubyte),     # 是否是远程帧
        ("ExternFlag", ctypes.c_ubyte),     # 是否是扩展帧
        ("DataLen", ctypes.c_ubyte),        # 数据长度(<=8)
        ("Data", ctypes.c_ubyte * 8),       # 报文的数据
        ("TimeStampHigh", ctypes.c_ubyte)   # 时间戳高位
    ]

# 定义CAN初始化配置结构体（与LGV2一致）
class CAN_INIT_CONFIG(ctypes.Structure):
    _fields_ = [
        ("CAN_BRP_CFG3", ctypes.c_uint),    # 取值范围1~1024
        ("CAN_SJW", ctypes.c_ubyte),    # 取值范围1~4
        ("CAN_BS1_CFG1", ctypes.c_ubyte),    # 取值范围1~16
        ("CAN_BS2_CFG2", ctypes.c_ubyte),    # 取值范围1~8
        ("CAN_Mode", ctypes.c_ubyte),   # CAN工作模式，0-正常模式，1-环回模式，2-静默模式，3-静默环回模式
        ("CAN_ABOM", ctypes.c_ubyte),   # 自动离线管理，0-禁止，1-使能
        ("CAN_NART", ctypes.c_ubyte),   # 报文重发管理，0-使能报文重传，1-禁止报文重传
        ("CAN_RFLM", ctypes.c_ubyte),   # FIFO锁定管理，0-新报文覆盖旧报文，1-丢弃新报文
        ("CAN_TXFP", ctypes.c_ubyte),   # 发送优先级管理，0-标识符决定，1-发送请求顺序决定
    ]

# 初始化设备
def init_device(USB2XXXLib):
    print("\n=== 开始初始化设备 ===")
    
    # 扫描设备（与LGV2一致，只使用一个参数）
    print("=== 开始扫描设备 ===")
    DevHandleArray = (ctypes.c_uint32 * 20)()
    ret = USB2XXXLib.USB_ScanDevice(ctypes.byref(DevHandleArray))
    print(f"扫描设备返回值: {ret}")
    
    # 检查返回值，ret表示检测到的设备数量
    DevCount = ret
    print(f"检测到 {DevCount} 个设备")
    
    if DevCount == 0:
        print("未检测到设备，退出")
        return None
    
    # 显示设备列表（确保显示所有设备的句柄值）
    print("设备列表:")
    for i in range(20):  # 显示整个数组，确保能看到所有设备句柄
        handle = DevHandleArray[i]
        if handle != 0:
            print(f"设备 {i}: {handle}")
    
    # 尝试打开每个设备，直到成功
    print("\n=== 开始打开设备 ===")
    for i in range(DevCount):
        DevHandle = DevHandleArray[i]
        if DevHandle == 0:
            continue  # 跳过无效的设备句柄
        
        print(f"尝试打开设备 {i}，句柄: {DevHandle}")
        ret = USB2XXXLib.USB_OpenDevice(DevHandle)
        print(f"打开设备返回值: {ret}")
        print(f"设备句柄: {DevHandle}")
        
        if bool(ret):  # 与LGV2一致，使用bool(ret)判断是否成功
            print("设备打开成功")
            
            # 获取设备信息（与LGV2一致，使用三个参数）
            print("\n=== 获取设备信息 ===")
            DevInfo = DEVICE_INFO()
            FunctionStr = (ctypes.c_char * 256)()
            ret = USB2XXXLib.DEV_GetDeviceInfo(DevHandle, ctypes.byref(DevInfo), ctypes.byref(FunctionStr))
            print(f"获取设备信息返回值: {ret}")
            
            if bool(ret):  # 与LGV2一致，使用bool(ret)判断是否成功
                print(f"固件名称: {DevInfo.FirmwareName.decode('utf-8')}")
                print(f"构建日期: {DevInfo.BuildDate.decode('utf-8')}")
                print(f"硬件版本: {DevInfo.HardwareVersion}")
                print(f"固件版本: {DevInfo.FirmwareVersion}")
                print(f"序列号: {[DevInfo.SerialNumber[i] for i in range(3)]}")
                print(f"功能: {DevInfo.Functions}")
                print(f"功能字符串: {FunctionStr.value.decode('utf-8')}")
            else:
                print("获取设备信息失败")
            
            return DevHandle
        else:
            print(f"设备 {i} 打开失败，返回值: {ret}")
    
    print("所有设备打开失败，退出")
    return None

# 初始化CAN通道
def init_can_channel(USB2XXXLib, DevHandle):
    print("\n=== 初始化CAN通道 ===")
    
    # 尝试不同的CAN通道
    for CanChannel in [0, 1]:
        print(f"\n尝试CAN通道: {CanChannel}")
        
        # 创建CAN初始化配置结构体
        CanConfig = CAN_INIT_CONFIG()
        
        # 设置CAN波特率为500Kbps（使用MCP2515的配置参数）
        # MCP_16MHz_500kBPS_CFG1 = (0x00)
        # MCP_16MHz_500kBPS_CFG2 = (0xF0)
        # MCP_16MHz_500kBPS_CFG3 = (0x86)
        CanConfig.CAN_BRP_CFG3 = 8  # BRP=8
        CanConfig.CAN_SJW = 1       # SJW=1
        CanConfig.CAN_BS1_CFG1 = 15  # BS1=15
        CanConfig.CAN_BS2_CFG2 = 1   # BS2=1
        CanConfig.CAN_Mode = 0       # 正常模式
        CanConfig.CAN_ABOM = 1       # 使能自动离线管理
        CanConfig.CAN_NART = 0       # 使能报文重传
        CanConfig.CAN_RFLM = 0       # 新报文覆盖旧报文
        CanConfig.CAN_TXFP = 0       # 标识符决定发送优先级
        
        print(f"CAN配置: BRP={CanConfig.CAN_BRP_CFG3}, SJW={CanConfig.CAN_SJW}, BS1={CanConfig.CAN_BS1_CFG1}, BS2={CanConfig.CAN_BS2_CFG2}")
        print(f"CAN模式: {CanConfig.CAN_Mode}, ABOM={CanConfig.CAN_ABOM}, NART={CanConfig.CAN_NART}")
        
        # 初始化CAN通道（与LGV2一致，使用三个参数）
        ret = USB2XXXLib.CAN_Init(DevHandle, CanChannel, ctypes.byref(CanConfig))
        print(f"CAN通道初始化返回值: {ret}")
        
        if ret == 0:
            print("CAN通道初始化成功")
            return CanChannel  # 返回成功初始化的CAN通道号
        else:
            print(f"CAN通道初始化失败，返回值: {ret}")
            print("可能原因: 通道不存在或被占用")
    
    print("\n所有CAN通道初始化失败")
    return -1  # 返回-1表示初始化失败

# 发送CAN消息
def send_can_message(USB2XXXLib, DevHandle, CanChannel):
    print("\n=== 发送CAN消息 ===")
    print(f"使用CAN通道: {CanChannel}")
    
    # 创建CAN消息（与LGV2一致，使用正确的字段名）
    CanMsg = CAN_MSG()
    CanMsg.ID = 0x4E0  # PTC功率设置和使能的CAN ID
    CanMsg.ExternFlag = 0  # 标准ID
    CanMsg.RemoteFlag = 0  # 数据帧
    CanMsg.DataLen = 8  # 8字节数据
    # 设置数据：假设这里设置功率为100%（2500瓦特），使能PTC
    CanMsg.Data[0] = 0xFF  # 功率设置（0-255对应0-100%）
    CanMsg.Data[1] = 0x01  # 使能标志（1=使能，0=禁用）
    CanMsg.Data[2] = 0x00  # 保留
    CanMsg.Data[3] = 0x00  # 保留
    CanMsg.Data[4] = 0x00  # 保留
    CanMsg.Data[5] = 0x00  # 保留
    CanMsg.Data[6] = 0x00  # 保留
    CanMsg.Data[7] = 0x00  # 保留
    
    # 发送CAN消息（与LGV2一致，使用四个参数）
    ret = USB2XXXLib.CAN_SendMsg(DevHandle, CanChannel, ctypes.byref(CanMsg), 1)
    print(f"发送CAN消息返回值: {ret}")
    
    if ret == 1:
        print("CAN消息发送成功！")
        print(f"CAN ID: 0x{CanMsg.ID:X}")
        print(f"数据: {[hex(CanMsg.Data[i]) for i in range(CanMsg.DataLen)]}")
        return True
    else:
        print("CAN消息发送失败")
        return False

# 接收CAN消息
def receive_can_message(USB2XXXLib, DevHandle, CanChannel):
    print("\n=== 接收CAN消息 ===")
    print(f"使用CAN通道: {CanChannel}")
    
    # 准备接收CAN消息
    CanMsgArray = (CAN_MSG * 10)()
    
    # 接收CAN消息（与LGV2一致，使用三个参数）
    ret = USB2XXXLib.CAN_GetMsg(DevHandle, CanChannel, ctypes.byref(CanMsgArray))
    print(f"接收CAN消息返回值: {ret}")
    
    # 检查返回值，ret表示接收到的消息数量
    if ret > 0:
        print(f"接收到 {ret} 条消息")
        print("接收到的CAN消息:")
        for i in range(ret):
            msg = CanMsgArray[i]
            print(f"消息 {i}:")
            print(f"  CAN ID: 0x{msg.ID:X}")
            print(f"  扩展标志: {msg.ExternFlag}")
            print(f"  远程标志: {msg.RemoteFlag}")
            print(f"  数据长度: {msg.DataLen}")
            print(f"  数据: {[hex(msg.Data[j]) for j in range(msg.DataLen)]}")
            print(f"  时间戳: {msg.TimeStamp}")
        return True
    else:
        print("未接收到CAN消息")
        return False

# 关闭设备
def close_device(USB2XXXLib, DevHandle):
    print("\n=== 关闭设备 ===")
    if DevHandle is not None:
        ret = USB2XXXLib.USB_CloseDevice(DevHandle)
        print(f"关闭设备返回值: {ret}")
        if ret == 0:
            print("设备关闭成功")
        else:
            print("设备关闭失败")

# 主函数
def main():
    print("=== 测试CAN通讯功能 ===")
    
    # 加载USB2XXX.dll
    USB2XXXLib = load_usb2xxx_dll()
    if USB2XXXLib is None:
        print("无法加载USB2XXX.dll，退出测试")
        return
    
    # 初始化设备
    DevHandle = init_device(USB2XXXLib)
    if DevHandle is None:
        print("无法初始化设备，退出测试")
        return
    
    try:
        # 初始化CAN通道
        CanChannel = init_can_channel(USB2XXXLib, DevHandle)
        if CanChannel == -1:
            print("无法初始化CAN通道，退出测试")
            return
        
        # 发送CAN消息
        send_can_message(USB2XXXLib, DevHandle, CanChannel)
        
        # 接收CAN消息
        receive_can_message(USB2XXXLib, DevHandle, CanChannel)
        
    finally:
        # 关闭设备
        close_device(USB2XXXLib, DevHandle)

if __name__ == "__main__":
    main()
