import time
from ctypes import *

try:
    from usb_device import USB_ScanDevice, USB_OpenDevice, DEV_GetDeviceInfo, DEVICE_INFO
    from usb2can import CAN_Init, CAN_SendMsg, CAN_GetMsg
    from dbc_parser import DBC_ParserFile, DBC_GetMsgQuantity, DBC_GetMsgName, DBC_GetMsgSignalQuantity, DBC_GetMsgSignalName, DBC_SetSignalValue, DBC_SyncValueToCANMsg, DBC_SyncCANMsgToValue, DBC_GetSignalValueStr
except ImportError as e:
    print(f"CAN Import Error: {e}")

# CAN配置常量
CAN_SUCCESS = 0
CAN_CHANNEL = 0

def create_can_command_message(power_percentage=50, enable=1, **kwargs):
    """
    创建CAN命令消息
    对应LIN的create_command_message功能
    """
    try:
        # 构建CAN消息结构
        # 这里模拟0x4E0消息，对应LIN的0x24命令
        msg_struct = {
            "id": 0x4E0,  # 对应LIN的0x24命令
            "data": [0] * 8,
            "dlc": 8
        }
        
        # 从kwargs中提取可能的参数，如果不存在则使用默认值
        power_pct = kwargs.get('power_percentage', power_percentage)
        enable_val = kwargs.get('enable', enable)
        
        # 根据功率百分比设置数据字段
        # 功率百分比转为数值 (0-100% -> 0-255)
        power_value = min(int(power_pct * 2.55), 255)  # 100% * 2.55 = 255
        
        # 使能位 (bit 0)
        enable_bit = 1 if enable_val else 0
        
        # 设置数据字段
        msg_struct["data"][0] = power_value
        msg_struct["data"][1] = enable_bit  # 使能位
        # 其他字段根据需要设置
        
        return msg_struct
    except Exception as e:
        print(f"创建CAN命令消息错误: {e}")
        return None

def parse_can_response_message(data_bytes):
    """
    解析CAN响应消息
    对应LIN的parse_response_message功能
    """
    try:
        signals = {}
        
        if len(data_bytes) >= 8:
            # 解析0x524消息信号 (对应LIN的0x25响应)
            # 实际的信号解析需要根据DBC文件定义
            signals['operating_status'] = {
                'value': data_bytes[0],
                'description': _get_status_description(data_bytes[0])
            }
            
            # 解析测量电流 (字节2-3)
            current_raw = (data_bytes[3] << 8) | data_bytes[2]
            current_physical = current_raw * 0.001  # 假设精度为0.001
            signals['measured_current'] = {
                'value': current_raw,
                'physical_value': current_physical
            }
            
            # 解析其他信号
            signals['error_level'] = {'value': data_bytes[4]}
            signals['error_code'] = {'value': (data_bytes[6] << 8) | data_bytes[5]}
            signals['ptc_status'] = {'value': data_bytes[7]}
            
        return signals
    except Exception as e:
        print(f"解析CAN响应消息错误: {e}")
        return {}

def _get_status_description(status_code):
    """
    获取状态码描述
    """
    status_descriptions = {
        0x0: "正常",
        0x1: "警告",
        0x2: "故障",
        0x3: "未知"
    }
    return status_descriptions.get(status_code, f"未知状态({status_code:#02x})")

def perform_can_transaction(dev_handle, cmd_data):
    """
    执行完整的CAN事务：发送命令并接收响应
    对应LIN的_perform_lin_transaction功能
    """
    try:
        if not dev_handle:
            return False, {}
        
        # 发送CAN命令消息
        # 尝试从cmd_data中提取参数，兼容LIN风格的命令数据
        power_pct = cmd_data.get('power_percentage', 50) if isinstance(cmd_data, dict) else 50
        enable = cmd_data.get('enable', 1) if isinstance(cmd_data, dict) else 1
        
        # 如果cmd_data是bytes数组（LIN风格），则尝试从中提取参数
        if isinstance(cmd_data, (list, tuple)) and len(cmd_data) >= 2:
            # 假设第一个字节是功率百分比，第二个字节包含使能位
            power_pct = cmd_data[0]  # 假设直接是功率百分比值 (0-100)
            enable = cmd_data[1] & 0x01  # 只取最低位作为使能位

        can_cmd = create_can_command_message(power_percentage=power_pct, enable=enable)
        if not can_cmd:
            return False, {}
        
        # 构建CAN消息结构体
        can_msg = (c_ubyte * 16)()
        can_msg[0] = (can_cmd["id"] >> 8) & 0xFF  # ID高字节
        can_msg[1] = can_cmd["id"] & 0xFF         # ID低字节
        can_msg[4] = can_cmd["dlc"]               # 数据长度
        
        # 复制数据
        for i in range(min(len(can_cmd["data"]), 8)):
            can_msg[5+i] = can_cmd["data"][i]
        
        # 发送消息
        send_result = CAN_SendMsg(dev_handle, CAN_CHANNEL, can_msg)
        if send_result != CAN_SUCCESS:
            print(f"CAN消息发送失败: {send_result}")
            return False, {}
        
        time.sleep(0.05)  # 短暂延迟等待响应
        
        # 接收响应消息
        response_msg = (c_ubyte * 16)()
        recv_result = CAN_GetMsg(dev_handle, CAN_CHANNEL, response_msg)
        
        if recv_result == CAN_SUCCESS:
            # 解析响应
            response_id = (response_msg[0] << 8) | response_msg[1]
            data_len = response_msg[4]
            data_bytes = [response_msg[5+i] for i in range(min(data_len, 8))]
            
            # 假设响应ID为0x524或0x525 (对应LIN的0x25响应)
            if response_id in [0x524, 0x525]:
                signals = parse_can_response_message(data_bytes)
                return True, signals
            else:
                return False, {}
        else:
            return False, {}
            
    except Exception as e:
        print(f"CAN事务执行错误: {e}")
        return False, {}