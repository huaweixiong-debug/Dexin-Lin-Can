"""
增强的CAN通信模块，整合PTC_Power_Sequence.py中的CAN通信逻辑
"""
import time
import threading
from ctypes import *

try:
    from usb_device import USB_ScanDevice, USB_OpenDevice, DEV_GetDeviceInfo, DEVICE_INFO
    from usb2can import CAN_Init, CAN_SendMsg, CAN_GetMsg, CAN_START_GETMSG, CAN_Filter_Init, CAN_Filter_CONFIG
    from dbc_parser import DBC_ParserFile, DBC_GetMsgQuantity, DBC_GetMsgName, DBC_GetMsgSignalQuantity, DBC_GetMsgSignalName, DBC_SetSignalValue, DBC_SyncValueToCANMsg, DBC_SyncCANMsgToValue, DBC_GetSignalValueStr
except ImportError as e:
    print(f"CAN Import Error: {e}")


# CAN配置常量
CAN_SUCCESS = 0
CAN_CHANNEL = 0

class EnhancedCANCommunication:
    def __init__(self, station_idx, station_config, log_callback=None):
        self.station_idx = station_idx
        self.config = station_config
        self.log_callback = log_callback
        self.dev_handle = None
        self.dbchandle = None
        self.device_connected = False
        self.can_initialized = False
        self.running = False
        self.paused = False
        
        # CAN模式配置
        self.use_canfd = False
        self.CAN_CHANNEL = int(self.config.get("can_channel", 0))
        
        # 0x4E0消息发送线程相关变量
        self.send_thread = None
        self.send_running = False
        self.current_power = 0
        
        # 功率序列
        self.current_sequence = [
            {"power_percent": 100, "time_sec": 350, "power_watt": 2500, "description": "2500W运行350秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"},
            {"power_percent": 80, "time_sec": 350, "power_watt": 2000, "description": "2000W运行350秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"},
            {"power_percent": 60, "time_sec": 350, "power_watt": 1500, "description": "1500W运行350秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"},
            {"power_percent": 40, "time_sec": 10, "power_watt": 1000, "description": "1000W运行10秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"}
        ]

    def log(self, message, level="INFO"):
        """记录日志"""
        if self.log_callback:
            full_msg = f"[Station {self.station_idx}] {message}"
            self.log_callback(full_msg)
        else:
            print(f"[{level}] {message}")

    def scan_devices(self):
        """扫描CAN设备"""
        self.log("开始扫描CAN设备", "INFO")
        
        try:
            DevHandles = (c_uint * 20)()
            ret = USB_ScanDevice(byref(DevHandles))
            
            if ret == 0:
                self.log("未检测到USB2CAN设备", "WARNING")
                return []
            
            self.log(f"检测到 {ret} 个设备", "INFO")
            
            device_list = []
            device_info = {}
            
            for i in range(ret):
                device_handle = DevHandles[i]
                
                # 尝试打开设备
                try:
                    ret_open = USB_OpenDevice(device_handle)
                    
                    if bool(ret_open):
                        # 获取设备信息
                        try:
                            USB2XXXInfo = DEVICE_INFO()
                            USB2XXXFunctionString = (c_char * 256)()
                            ret_info = DEV_GetDeviceInfo(device_handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                            
                            if bool(ret_info):
                                # 构建序列号字符串
                                serial_parts = []
                                for j in range(3):
                                    serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                                device_serial = ''.join(serial_parts)
                                
                                device_info[device_serial] = {
                                    "handle": device_handle,
                                    "index": i,
                                    "opened": True
                                }
                                
                                device_list.append({
                                    "serial": device_serial,
                                    "handle": device_handle,
                                    "index": i
                                })
                                
                                self.log(f"设备 {i}: 序列号 {device_serial}, 句柄 {device_handle}", "INFO")
                            else:
                                self.log(f"获取设备 {i} 信息失败", "ERROR")
                        except Exception as e:
                            self.log(f"获取设备 {i} 信息异常: {str(e)}", "ERROR")
                        
                        # 关闭设备（稍后连接时再打开）
                        try:
                            USB_CloseDevice(device_handle)
                        except:
                            pass
                    else:
                        self.log(f"打开设备 {i} 失败", "ERROR")
                except Exception as e:
                    self.log(f"处理设备 {i} 时异常: {str(e)}", "ERROR")
            
            self.log(f"找到 {len(device_list)} 个可用设备", "INFO")
            return device_list
            
        except Exception as e:
            self.log(f"扫描设备时发生错误: {str(e)}", "ERROR")
            return []

    def connect_device(self, device_handle):
        """连接到指定的CAN设备"""
        try:
            self.log("开始连接CAN设备", "INFO")
            
            # 尝试打开设备
            ret_open = USB_OpenDevice(device_handle)
            if not bool(ret_open):
                self.log("打开设备失败", "ERROR")
                return False
            
            self.dev_handle = device_handle
            self.log(f"设备打开成功，句柄: {self.dev_handle}", "INFO")
            
            # 初始化CAN通道
            if not self.init_can_channel():
                self.log("CAN通道初始化失败", "ERROR")
                return False
            
            self.device_connected = True
            self.log("CAN设备连接成功", "INFO")
            return True
            
        except Exception as e:
            self.log(f"连接设备时发生错误: {str(e)}", "ERROR")
            return False

    def init_can_channel(self):
        """初始化CAN通道"""
        self.log(f"开始初始化CAN通道 {self.CAN_CHANNEL}", "INFO")
        
        try:
            # 1. 尝试使用标准配置初始化
            CANConfig = (c_uint * 5)()
            # 配置CAN参数，波特率500kbps
            # 波特率 = 100M/(BRP*(SJW+BS1+BS2))
            CANConfig[0] = 500000  # 波特率 500kbps
            CANConfig[1] = 0       # 模式 (正常模式)
            CANConfig[2] = 0       # 过滤器
            CANConfig[3] = 0       # 掩码
            CANConfig[4] = 0       # 保留
            
            ret = CAN_Init(self.dev_handle, self.CAN_CHANNEL, byref(CANConfig))
            
            if ret == 0:  # CAN_SUCCESS
                self.log(f"CAN通道{self.CAN_CHANNEL}初始化成功", "INFO")
                self.use_canfd = False
                self.can_initialized = True
                self.log("设备已配置为传统CAN模式", "INFO")

                # 配置过滤器，必须配置，否则可能无法收到数据
                CANFilter = CAN_FILTER_CONFIG()
                CANFilter.Enable = 1
                CANFilter.ExtFrame = 0
                CANFilter.FilterIndex = 0
                CANFilter.FilterMode = 0
                CANFilter.MASK_IDE = 0
                CANFilter.MASK_RTR = 0
                CANFilter.MASK_Std_Ext = 0
                ret_filter = CAN_Filter_Init(self.dev_handle, self.CAN_CHANNEL, byref(CANFilter))
                if ret_filter != CAN_SUCCESS:
                    self.log(f"配置CAN过滤器失败，返回值: {ret_filter}", "WARNING")
                else:
                    self.log("配置CAN过滤器成功", "INFO")

                # 启动CAN接收
                if 'CAN_StartGetMsg' in globals():
                    ret_start = CAN_StartGetMsg(self.dev_handle, self.CAN_CHANNEL)
                    if ret_start == CAN_SUCCESS:
                        self.log("CAN接收已启动", "INFO")
                    else:
                        self.log(f"CAN接收启动失败: {ret_start}", "ERROR")
                
                return True
            else:
                self.log(f"CAN初始化失败，返回值: {ret}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"初始化CAN通道时发生错误: {str(e)}", "ERROR")
            return False

    def send_power_command(self, power_watt):
        """发送功率控制命令"""
        if not self.device_connected or not self.can_initialized:
            self.log("设备未连接或CAN未初始化", "ERROR")
            return False
        
        try:
            # 构建CAN消息 - 0x4E0消息（ECC_0x4E0）
            can_msg = (c_ubyte * 16)()
            
            # 设置CAN ID (0x4E0)
            can_msg[0] = 0x04  # ID高字节
            can_msg[1] = 0xE0  # ID低字节
            can_msg[2] = 0x00  # 扩展ID
            can_msg[3] = 0x00  # 扩展ID
            can_msg[4] = 8     # 数据长度
            
            # 功率值转换（假设使用2字节表示）
            power_value = min(max(power_watt, 0), 10000)  # 限制在0-10000W范围内
            can_msg[5] = (power_value >> 8) & 0xFF  # 高字节
            can_msg[6] = power_value & 0xFF         # 低字节
            
            # 使能命令（假设第3字节第0位）
            can_msg[7] = 0x01  # 使能位设为1
            # 目标档位（假设第4字节）
            can_msg[8] = 0x00  # 档位
            
            # 发送CAN消息
            if CAN_SendMsg(self.dev_handle, self.CAN_CHANNEL, byref(can_msg)) != CAN_SUCCESS:
                self.log(f"发送功率命令失败: {power_watt}W", "ERROR")
                return False
            
            self.log(f"发送功率命令成功: {power_watt}W")
            self.current_power = power_watt
            return True
            
        except Exception as e:
            self.log(f"发送功率命令错误: {str(e)}", "ERROR")
            return False

    def receive_can_messages(self):
        """接收CAN消息并解析PTC信号"""
        if not self.device_connected or not self.can_initialized:
            return None
        
        try:
            # 接收CAN消息
            response_msg = (c_ubyte * 16)()
            recv_result = CAN_GetMsg(self.dev_handle, self.CAN_CHANNEL, byref(response_msg))
            
            if recv_result == CAN_SUCCESS:
                # 解析响应
                response_id = (response_msg[0] << 8) | response_msg[1]
                data_len = response_msg[4]
                data_bytes = [response_msg[5+i] for i in range(min(data_len, 8))]
                
                # 解析不同ID的消息
                if response_id == 0x524:  # PTC_0x524 消息
                    signals = self.parse_ptc_524_signals(data_bytes)
                    return {"msg_id": 0x524, "signals": signals}
                elif response_id == 0x525:  # PTC_0x525 消息
                    signals = self.parse_ptc_525_signals(data_bytes)
                    return {"msg_id": 0x525, "signals": signals}
                elif response_id == 0x4E0:  # ECC_0x4E0 消息
                    signals = self.parse_ecc_4e0_signals(data_bytes)
                    return {"msg_id": 0x4E0, "signals": signals}
                else:
                    # 其他ID的消息
                    return {"msg_id": response_id, "data": data_bytes}
            
            return None
            
        except Exception as e:
            self.log(f"接收CAN消息错误: {str(e)}", "ERROR")
            return None

    def parse_ptc_524_signals(self, data_bytes):
        """解析PTC_0x524消息信号"""
        signals = {}
        
        if len(data_bytes) >= 8:
            # 假设信号分布如下（根据实际DBC文件调整）
            signals['actual_power'] = (data_bytes[1] << 8) | data_bytes[0]  # 实际功率
            signals['error_level'] = data_bytes[2]  # 故障等级
            signals['error_code'] = (data_bytes[4] << 8) | data_bytes[3]  # 故障码
            signals['ptc_status'] = data_bytes[5]  # PTC状态
            signals['lin_check_status'] = data_bytes[6]  # 林肯检查状态
            signals['auto_start'] = data_bytes[7] & 0x01  # 自动启动
            signals['main_status'] = (data_bytes[7] >> 1) & 0x01  # 主状态
        
        return signals

    def parse_ptc_525_signals(self, data_bytes):
        """解析PTC_0x525消息信号"""
        signals = {}
        
        if len(data_bytes) >= 8:
            # 假设信号分布如下（根据实际DBC文件调整）
            signals['actual_voltage'] = ((data_bytes[1] << 8) | data_bytes[0]) * 0.01  # 实际电压 (单位: V)
            signals['actual_current'] = ((data_bytes[3] << 8) | data_bytes[2]) * 0.001  # 实际电流 (单位: A)
            # 其他信号...
        
        return signals

    def parse_ecc_4e0_signals(self, data_bytes):
        """解析ECC_0x4E0消息信号"""
        signals = {}
        
        if len(data_bytes) >= 8:
            # 假设信号分布如下（根据实际DBC文件调整）
            signals['target_power'] = (data_bytes[1] << 8) | data_bytes[0]  # 目标功率
            signals['enable_command'] = data_bytes[2]  # 使能命令
            signals['target_gear'] = data_bytes[3]  # 目标档位
        
        return signals

    def start_power_sequence(self):
        """开始功率序列测试"""
        if not self.device_connected:
            self.log("设备未连接", "ERROR")
            return False
        
        if not self.can_initialized:
            self.log("CAN未初始化", "ERROR")
            return False
        
        self.running = True
        
        # 启动0x4E0消息发送线程
        self.send_running = True
        self.send_thread = threading.Thread(target=self.send_4e0_message)
        self.send_thread.daemon = True
        self.send_thread.start()
        self.log("启动0x4E0消息发送线程", "DEBUG")
        
        # 启动序列执行
        sequence_thread = threading.Thread(target=self.execute_sequence)
        sequence_thread.daemon = True
        sequence_thread.start()
        
        self.log("功率序列测试已启动", "INFO")
        return True

    def send_4e0_message(self):
        """发送0x4E0消息的线程函数"""
        while self.send_running and self.running:
            try:
                # 发送当前功率命令
                self.send_power_command(self.current_power)
                
                # 每100ms发送一次
                time.sleep(0.1)
            except Exception as e:
                self.log(f"发送0x4E0消息线程错误: {str(e)}", "ERROR")
                break

    def execute_sequence(self):
        """执行功率序列"""
        try:
            for phase_idx, phase in enumerate(self.current_sequence):
                if not self.running:
                    break
                
                self.log(f"开始阶段 {phase_idx+1}: {phase['description']}", "INFO")
                
                # 设置目标功率
                self.current_power = phase['power_watt']
                
                # 持续发送功率命令
                start_time = time.time()
                while time.time() - start_time < phase['time_sec']:
                    if not self.running:
                        break
                    time.sleep(1)  # 每秒检查一次
                
                if not self.running:
                    break
                
                self.log(f"阶段 {phase_idx+1} 完成", "INFO")
            
            self.log("功率序列执行完成", "INFO")
            
        except Exception as e:
            self.log(f"执行功率序列错误: {str(e)}", "ERROR")
        finally:
            # 停止发送
            self.send_running = False
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(timeout=1)

    def stop_test(self):
        """停止测试"""
        self.running = False
        self.send_running = False
        self.log("测试已停止", "INFO")
        
        # 发送0功率命令
        self.send_power_command(0)

    def disconnect_device(self):
        """断开设备连接"""
        if self.dev_handle:
            try:
                # 停止发送线程
                self.send_running = False
                if self.send_thread and self.send_thread.is_alive():
                    self.send_thread.join(timeout=1)
                
                # 发送0功率命令
                self.send_power_command(0)
                
                # 关闭设备
                USB_CloseDevice(self.dev_handle)
                self.device_connected = False
                self.can_initialized = False
                self.dev_handle = None
                self.log("设备已断开连接", "INFO")
            except Exception as e:
                self.log(f"断开设备连接错误: {str(e)}", "ERROR")