import json
import os
import time
from ctypes import *
from usb_device import *
from usb2lin_ex import *

# 配置输出颜色
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def load_config():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    config_file = os.path.join(base_dir, "config.json")
    
    if not os.path.exists(config_file):
        print(f"{Colors.FAIL}Error: {config_file} not found!{Colors.ENDC}")
        return None
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def scan_devices():
    """扫描所有USB设备并返回句柄列表"""
    DevHandles = (c_uint * 20)()
    ret = USB_ScanDevice(byref(DevHandles))
    if ret <= 0:
        return []
    
    devices = []
    for i in range(ret):
        devices.append(DevHandles[i])
    return devices

def get_device_serial(handle, keep_open=False):
    """获取设备序列号"""
    # 尝试打开设备
    ret = USB_OpenDevice(handle)
    if not ret:
        return None
        
    USB2XXXInfo = DEVICE_INFO()
    USB2XXXFunctionString = (c_char * 256)()
    ret_info = DEV_GetDeviceInfo(handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
    
    serial = None
    if ret_info:
        serial_parts = []
        for j in range(len(USB2XXXInfo.SerialNumber)):
            serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
        serial = ''.join(serial_parts)
    
    if not keep_open:
        USB_CloseDevice(handle)
        
    return serial

def diagnose_station(station_idx, config, active_handles):
    """诊断单个工位"""
    station_key = f"工位{station_idx}"
    if "hardware_settings" not in config or station_key not in config["hardware_settings"]:
        print(f"工位 {station_idx}: {Colors.WARNING}未配置{Colors.ENDC}")
        return False

    settings = config["hardware_settings"][station_key]
    lin_sn = settings.get("lin_sn", "")
    lin_index = int(settings.get("lin_index", 0))
    
    print(f"工位 {station_idx}: SN={lin_sn}, Index={lin_index} ... ", end="")
    
    if not lin_sn:
        print(f"{Colors.FAIL}FAIL (无SN配置){Colors.ENDC}")
        return False

    # 1. 查找设备
    device_entry = active_handles.get(lin_sn)
    
    if device_entry is None:
        print(f"{Colors.FAIL}FAIL (设备未连接){Colors.ENDC}")
        return False

    handle = device_entry['handle']

    # 2. 确保设备已打开 (应该在main中已打开)
    if not device_entry['opened']:
         # 如果没打开，尝试打开
        ret = USB_OpenDevice(handle)
        if not ret:
            print(f"{Colors.FAIL}FAIL (无法打开设备){Colors.ENDC}")
            return False
        device_entry['opened'] = True
    
    # 3. 初始化LIN
    ret = LIN_EX_Init(handle, lin_index, 19200, LIN_EX_MASTER)
    if ret != LIN_EX_SUCCESS:
        print(f"{Colors.FAIL}FAIL (LIN初始化失败 Code={ret}){Colors.ENDC}")
        return False
        
    print(f"{Colors.OKGREEN}OK{Colors.ENDC}")
    return True

def main():
    print(f"{Colors.HEADER}=== LGV2 LIN通讯系统诊断工具 ==={Colors.ENDC}")
    
    config = load_config()
    if not config:
        return

    # 预先扫描所有设备并建立 SN -> Handle 映射
    print("正在扫描USB设备...")
    dev_handles = scan_devices()
    print(f"找到 {len(dev_handles)} 个USB设备")
    
    sn_map = {} # SN -> Handle
    
    for h in dev_handles:
        # 保持设备打开
        sn = get_device_serial(h, keep_open=True)
        if sn:
            sn_map[sn] = {'handle': h, 'opened': True}
            print(f"  - 设备: {sn} (已连接并打开)")
        else:
            print(f"  - 设备: 未知SN (Handle {h})")

    print("\n开始诊断各工位配置与连接:")
    
    # 检查工位 1-10
    results = {}
    for i in range(1, 11):
        # 不需要重新扫描，只使用sn_map中的已打开设备
        success = diagnose_station(i, config, sn_map)
        results[i] = success
    
    # 清理：关闭所有打开的设备
    print("\n正在关闭设备连接...")
    for sn, state in sn_map.items():
        if state['opened']:
            USB_CloseDevice(state['handle'])
            
    print("\n" + "="*30)
    print("诊断摘要:")
    all_pass = True
    # 重点关注工位6和7
    special_check = True
    
    for i in range(1, 11):
        status = "PASS" if results[i] else "FAIL"
        color = Colors.OKGREEN if results[i] else Colors.FAIL
        if not results[i]: all_pass = False
        print(f"工位 {i}: {color}{status}{Colors.ENDC}")
        
    if all_pass:
        print(f"\n{Colors.OKGREEN}系统状态正常: 所有配置的工位LIN通讯测试通过。{Colors.ENDC}")
    else:
        print(f"\n{Colors.FAIL}系统状态异常: 存在LIN通讯故障，请检查上述红色标记的工位。{Colors.ENDC}")
        print("常见原因提示:")
        print("1. USB线未插好或松动")
        print("2. 配置文件(config.json)中的序列号(SN)与实际设备不匹配")
        print("3. 同一个USB设备被配置了错误的LIN Index (特别是工位6和7)")

if __name__ == "__main__":
    main()
