#coding:utf-8
from ctypes import *
import os
import time
import sys

# Import modules from the current directory
sys.path.append(os.getcwd())

try:
    from usb_device import *
    from usb2can import *
except ImportError:
    print("Error importing USB2CAN modules. Make sure you are running this script from the USB2CAN directory.")
    sys.exit(1)

# Try importing CANFD modules
try:
    from usb2canfd import *
    HAS_CANFD = True
except ImportError:
    HAS_CANFD = False
    print("CANFD module not found, skipping CANFD tests.")

def verify_connection():
    print("=== 开始验证USB2CAN连接 ===")
    
    # 1. Scan for devices
    print("\n[步骤1] 扫描设备...")
    DevHandles = (c_uint * 20)()
    ret = USB_ScanDevice(byref(DevHandles))
    
    if ret == 0:
        print("❌ 未检测到USB2CAN设备!")
        return False
    
    print(f"✅ 检测到 {ret} 个设备")
    
    # 2. Open the first device
    device_handle = DevHandles[0]
    print(f"\n[步骤2] 尝试打开设备 (句柄: {device_handle})...")
    
    ret_open = USB_OpenDevice(device_handle)
    if not bool(ret_open):
        print("❌ 设备打开失败!")
        return False
        
    print("✅ 设备打开成功")
    
    # Get device info
    USB2XXXInfo = DEVICE_INFO()
    USB2XXXFunctionString = (c_char * 256)()
    ret_info = DEV_GetDeviceInfo(device_handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
    
    if bool(ret_info):
        print(f"   - 固件名称: {bytes(USB2XXXInfo.FirmwareName).decode('ascii')}")
        print(f"   - 固件版本: v{(USB2XXXInfo.FirmwareVersion>>24)&0xFF}.{(USB2XXXInfo.FirmwareVersion>>16)&0xFF}.{USB2XXXInfo.FirmwareVersion&0xFFFF}")
        print(f"   - 序列号: {USB2XXXInfo.SerialNumber[0]:08X}{USB2XXXInfo.SerialNumber[1]:08X}{USB2XXXInfo.SerialNumber[2]:08X}")
    
    # 3. Initialize CAN
    print("\n[步骤3] 初始化CAN通讯...")
    can_initialized = False
    CAN_CHANNEL = 0
    
    # Try Traditional CAN first
    print("   - 尝试传统CAN模式...")
    try:
        CANConfig = CAN_INIT_CONFIG()
        CANConfig.CAN_Mode = 0
        CANConfig.CAN_ABOM = 0
        CANConfig.CAN_NART = 1
        CANConfig.CAN_RFLM = 0
        CANConfig.CAN_TXFP = 1
        # 500Kbps
        CANConfig.CAN_BRP_CFG3 = 25
        CANConfig.CAN_BS1_CFG1 = 6
        CANConfig.CAN_BS2_CFG2 = 1
        CANConfig.CAN_SJW = 1
        
        ret = CAN_Init(device_handle, CAN_CHANNEL, byref(CANConfig))
        if ret == 0:
            print("✅ 传统CAN初始化成功")
            can_initialized = True
        else:
            print(f"❌ 传统CAN初始化失败 (代码: {ret})")
    except Exception as e:
        print(f"❌ 传统CAN初始化异常: {str(e)}")

    # If failed, try CANFD
    if not can_initialized and HAS_CANFD:
        print("   - 尝试CANFD模式...")
        try:
            CANFDConfig = CANFD_INIT_CONFIG()
            CANFDConfig.Mode = 0
            CANFDConfig.ISOCRCEnable = 1
            CANFDConfig.RetrySend = 1
            CANFDConfig.ResEnable = 1
            # 500Kbps
            CANFDConfig.NBT_BRP = 10
            CANFDConfig.NBT_SEG1 = 6
            CANFDConfig.NBT_SEG2 = 1
            CANFDConfig.NBT_SJW = 1
            CANFDConfig.DBT_BRP = 10
            CANFDConfig.DBT_SEG1 = 6
            CANFDConfig.DBT_SEG2 = 1
            CANFDConfig.DBT_SJW = 1
            
            ret = CANFD_Init(device_handle, CAN_CHANNEL, byref(CANFDConfig))
            if ret == 0: # CANFD_SUCCESS
                print("✅ CANFD初始化成功")
                can_initialized = True
            else:
                print(f"❌ CANFD初始化失败 (代码: {ret})")
        except Exception as e:
            print(f"❌ CANFD初始化异常: {str(e)}")
            
    if not can_initialized:
        print("❌ CAN初始化失败，无法继续")
        USB_CloseDevice(device_handle)
        return False

    # 4. Check DBC File
    print("\n[步骤4] 检查DBC文件...")
    dbc_paths = [
        "d:\\老化CAN通讯\\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.dbc",
        "d:\\老化CAN通讯\\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc",
        "BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.dbc",
        "BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc"
    ]
    
    dbc_found = False
    for path in dbc_paths:
        if os.path.exists(path):
            print(f"✅ 找到DBC文件: {path}")
            dbc_found = True
            break
            
    if not dbc_found:
        print("❌ 未找到DBC文件!")
        print("   请确保文件名为: BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.dbc")
    
    # Cleanup
    USB_CloseDevice(device_handle)
    print("\n=== 验证完成 ===")
    
    if can_initialized and dbc_found:
        print("🎉 结果: 连接测试通过! 硬件和配置文件均已就绪。")
        return True
    else:
        print("⚠️ 结果: 连接测试未完全通过，请检查上述错误。")
        return False

if __name__ == "__main__":
    verify_connection()
