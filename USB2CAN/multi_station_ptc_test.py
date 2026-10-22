#coding:utf-8
from ctypes import *
import platform
import os
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# 使用与USB2CAN_Test.py相同的方式导入模块
from usb_device import *
from usb2can import *

# 尝试导入CANFD相关模块
try:
    from usb2canfd import *
except ImportError:
    print("Error importing CANFD functions from usb2canfd module")

# 定义函数别名，保持与原有代码兼容
CAN_SUCCESS = 0
USB_ScanDevice = USB_ScanDevice
USB_OpenDevice = USB_OpenDevice
USB_CloseDevice = USB_CloseDevice
DEV_GetDeviceInfo = DEV_GetDeviceInfo

# 尝试定义缺失的函数
try:
    from usb_device import DEV_GetDllBuildTime
except ImportError:
    def DEV_GetDllBuildTime(pDateTime):
        raise AttributeError("function 'DEV_GetDllBuildTime' not found")

try:
    from usb2can import CAN_GetCANSpeedArg
except ImportError:
    def CAN_GetCANSpeedArg(DevHandle, pCanConfig, SpeedBps):
        raise AttributeError("function 'CAN_GetCANSpeedArg' not found")

try:
    from usb2can import CAN_Init
    from usb2can import CAN_SendMsg
    from usb2can import CAN_GetMsg
except ImportError:
    print("Error importing CAN functions from usb2can module")
    exit(1)

# 定义CANFD相关的全局变量
USE_CANFD = True  # 尝试使用CANFD
CANFD_SUCCESS = 0  # CANFD操作成功返回值

# 尝试导入CANFD相关模块和函数
try:
    from usb2canfd import *
    print("成功导入CANFD支持")
    # 确保CANFD相关函数可用
    if 'CANFD_Init' in globals() and 'CANFD_SendMsg' in globals() and 'CANFD_GetMsg' in globals():
        print("所有CANFD函数都可用")
    else:
        print("部分CANFD函数不可用")
except ImportError as e:
    print(f"导入CANFD模块错误: {str(e)}")
except Exception as e:
    print(f"初始化CANFD支持错误: {str(e)}")

try:
    from dbc_parser import DBC_ParserFile
    from dbc_parser import DBC_GetMsgQuantity
    from dbc_parser import DBC_GetMsgName
    from dbc_parser import DBC_GetMsgSignalQuantity
    from dbc_parser import DBC_GetMsgSignalName
    from dbc_parser import DBC_SetSignalValue
    from dbc_parser import DBC_SyncValueToCANMsg
    from dbc_parser import DBC_SyncCANMsgToValue
    from dbc_parser import DBC_GetSignalValueStr
except ImportError:
    print("Error importing DBC functions from dbc_parser module")
    exit(1)

class StationController:
    """单个工位控制器"""
    def __init__(self, station_idx, log_callback=None):
        self.station_idx = station_idx
        self.log_callback = log_callback
        self.CAN_CHANNEL = 0
        self.CAN_ID = 0x53000023B
        
        # 设备相关变量
        self.dev_handle = None
        self.dbchandle = None
        self.device_connected = False
        
        # 运行状态变量
        self.running = False
        self.paused = False
        self.current_phase = 0
        self.remaining_time = 0
        self.start_time = 0
        
        # 0x4E0消息发送线程相关变量
        self.send_thread = None
        self.send_running = False
        self.current_power = 0
        
        # 定义默认参数序列
        self.default_sequence = [
            {"power_percent": 100, "time_sec": 350, "power_watt": 2500, "description": "2500W运行350秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"},
            {"power_percent": 80, "time_sec": 350, "power_watt": 2000, "description": "2000W运行350秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"},
            {"power_percent": 60, "time_sec": 350, "power_watt": 1500, "description": "1500W运行350秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"},
            {"power_percent": 40, "time_sec": 10, "power_watt": 1000, "description": "1000W运行10秒"},
            {"power_percent": 0, "time_sec": 10, "power_watt": 0, "description": "0W运行10秒"}
        ]
        
        # 当前参数序列
        self.current_sequence = self.default_sequence.copy()
        
        # CAN模式配置
        self.use_canfd = False  # 默认使用传统CAN，不使用CANFD
        self.can_initialized = False
        
        # 状态变量
        self.phase_var = tk.StringVar(value="当前阶段: 未开始")
        self.time_var = tk.StringVar(value="剩余时间: 0秒")
        self.power_var = tk.StringVar(value="目标功率: 0W")
        # PTC_0x524 信号
        self.actual_power_var = tk.StringVar(value="实际功率: 0W")
        self.error_level_var = tk.StringVar(value="故障等级: 0")
        self.error_code_var = tk.StringVar(value="故障码: 0")
        self.ptc_status_var = tk.StringVar(value="PTC状态: 0")
        self.lin_check_status_var = tk.StringVar(value="林肯检查状态: 0")
        self.auto_start_var = tk.StringVar(value="自动启动: 0")
        self.main_status_var = tk.StringVar(value="主状态: 0")
        # PTC_0x525 信号
        self.actual_voltage_var = tk.StringVar(value="实际电压: 0V")
        self.actual_current_var = tk.StringVar(value="实际电流: 0.000A")
        # ECC_0x4E0 信号
        self.target_power_var = tk.StringVar(value="目标功率: 0W")
        self.enable_command_var = tk.StringVar(value="使能命令: 0")
        self.target_gear_var = tk.StringVar(value="目标档位: 0")
    
    def log(self, message, level="INFO"):
        """记录日志信息"""
        if self.log_callback:
            self.log_callback(f"[工位{self.station_idx}] {message}", level)
        else:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [工位{self.station_idx}] [{level}] {message}")
    
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

    def start_sequence(self):
        """开始运行序列"""
        if not self.device_connected:
            self.log("设备未连接")
            return False
        
        if not self.can_initialized:
            self.log("CAN未初始化")
            return False
        
        self.running = True
        self.paused = False
        self.current_phase = 0
        self.remaining_time = 0
        
        # 启动0x4E0消息发送线程
        self.send_running = True
        self.send_thread = threading.Thread(target=self.send_4e0_message)
        self.send_thread.daemon = True
        self.send_thread.start()
        self.log("启动0x4E0消息发送线程", "DEBUG")
        
        # 启动运行线程
        self.run_thread = threading.Thread(target=self.run_sequence)
        self.run_thread.daemon = True
        self.run_thread.start()
        self.log("启动运行线程", "DEBUG")
        
        # 启动状态更新线程
        self.update_thread = threading.Thread(target=self.update_status)
        self.update_thread.daemon = True
        self.update_thread.start()
        self.log("启动状态更新线程", "DEBUG")
        
        self.log("开始运行功率序列", "INFO")
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

    def run_sequence(self):
        """运行功率序列"""
        try:
            for phase_idx, phase in enumerate(self.current_sequence):
                if not self.running:
                    break
                
                self.current_phase = phase_idx
                self.log(f"开始阶段 {phase_idx+1}: {phase['description']}", "INFO")
                
                # 设置目标功率
                self.current_power = phase['power_watt']
                
                # 更新UI
                self.phase_var.set(f"当前阶段: {phase['description']}")
                self.power_var.set(f"目标功率: {self.current_power}W")
                
                # 持续发送功率命令
                start_time = time.time()
                self.remaining_time = phase['time_sec']
                
                while self.remaining_time > 0:
                    if not self.running:
                        break
                    
                    if not self.paused:
                        elapsed = time.time() - start_time
                        self.remaining_time = max(0, phase['time_sec'] - int(elapsed))
                        
                        # 更新UI
                        self.time_var.set(f"剩余时间: {self.remaining_time}秒")
                    
                    time.sleep(1)  # 每秒检查一次
                
                if not self.running:
                    break
                
                self.log(f"阶段 {phase_idx+1} 完成", "INFO")
            
            self.log("功率序列执行完成", "INFO")
            
            # 完成后停止
            self.running = False
            self.send_running = False
            
        except Exception as e:
            self.log(f"执行功率序列错误: {str(e)}", "ERROR")
        finally:
            # 停止发送
            self.send_running = False
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(timeout=1)

    def update_status(self):
        """更新状态显示"""
        while self.running and self.send_running:
            try:
                # 接收CAN消息
                msg_data = self.receive_can_messages()
                if msg_data:
                    msg_id = msg_data["msg_id"]
                    signals = msg_data["signals"]
                    
                    # 根据消息ID更新相应信号
                    if msg_id == 0x524:  # PTC_0x524
                        self.actual_power_var.set(f"实际功率: {signals.get('actual_power', 0)}W")
                        self.error_level_var.set(f"故障等级: {signals.get('error_level', 0)}")
                        self.error_code_var.set(f"故障码: {signals.get('error_code', 0)}")
                        self.ptc_status_var.set(f"PTC状态: {signals.get('ptc_status', 0)}")
                        self.lin_check_status_var.set(f"林肯检查状态: {signals.get('lin_check_status', 0)}")
                        self.auto_start_var.set(f"自动启动: {signals.get('auto_start', 0)}")
                        self.main_status_var.set(f"主状态: {signals.get('main_status', 0)}")
                    elif msg_id == 0x525:  # PTC_0x525
                        self.actual_voltage_var.set(f"实际电压: {signals.get('actual_voltage', 0.0):.2f}V")
                        self.actual_current_var.set(f"实际电流: {signals.get('actual_current', 0.000):.3f}A")
                    elif msg_id == 0x4E0:  # ECC_0x4E0
                        self.target_power_var.set(f"目标功率: {signals.get('target_power', 0)}W")
                        self.enable_command_var.set(f"使能命令: {signals.get('enable_command', 0)}")
                        self.target_gear_var.set(f"目标档位: {signals.get('target_gear', 0)}")
                
                time.sleep(0.1)  # 每100ms更新一次
            except Exception as e:
                self.log(f"更新状态错误: {str(e)}", "ERROR")
                break

    def pause_sequence(self):
        """暂停运行"""
        self.paused = not self.paused
        if self.paused:
            self.log("序列运行已暂停")
        else:
            self.start_time = time.time() - (self.current_sequence[self.current_phase]["time_sec"] - self.remaining_time)
            self.log("序列运行已继续")

    def stop_sequence(self):
        """停止运行"""
        self.running = False
        self.paused = False
        self.send_running = False
        
        # 发送0功率命令
        self.send_power_command(0)
        
        self.log("序列已停止", "INFO")

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


class MultiStationPTCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("多工位PTC功率序列控制 - 10工位")
        self.root.geometry("1400x900")
        
        # 设置字体
        self.font = ("SimHei", 9)
        
        # 存储所有工位控制器
        self.station_controllers = {}
        self.station_widgets = {}  # 存储每个工位的UI组件
        
        # 创建UI
        self.create_ui()
        
        # 初始化所有工位
        self.init_stations()
    
    def create_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="多工位PTC功率序列控制系统 (共10工位)", font=("SimHei", 14, "bold"))
        title_label.pack(pady=10)
        
        # 创建工位控制框架容器
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 为每个工位创建标签页
        for station_idx in range(10):
            frame = ttk.Frame(notebook, padding="10")
            notebook.add(frame, text=f"工位 {station_idx + 1}")
            
            self.create_station_ui(frame, station_idx)
        
        # 总体控制区域
        control_frame = ttk.LabelFrame(main_frame, text="总体控制", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        self.start_all_btn = ttk.Button(control_frame, text="全部开始", command=self.start_all_stations)
        self.start_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_all_btn = ttk.Button(control_frame, text="全部停止", command=self.stop_all_stations)
        self.stop_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.refresh_all_btn = ttk.Button(control_frame, text="刷新所有设备", command=self.refresh_all_devices)
        self.refresh_all_btn.pack(side=tk.LEFT, padx=5)
    
    def create_station_ui(self, parent, station_idx):
        # 存储当前工位的UI组件
        widgets = {}
        
        # 工位状态区域
        status_frame = ttk.LabelFrame(parent, text=f"工位 {station_idx + 1} - 设备状态", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        # 设备选择区域
        device_frame = ttk.Frame(status_frame)
        device_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(device_frame, text="选择设备:", font=self.font).pack(side=tk.LEFT, padx=5)
        device_var = tk.StringVar(value="请选择设备")
        device_combobox = ttk.Combobox(device_frame, textvariable=device_var, font=self.font, width=40, state="readonly")
        device_combobox.pack(side=tk.LEFT, padx=5)
        widgets['device_combobox'] = device_combobox
        
        # CAN通道选择
        ttk.Label(device_frame, text="CAN通道:", font=self.font).pack(side=tk.LEFT, padx=5)
        can_channel_var = tk.StringVar(value="0")
        can_channel_combobox = ttk.Combobox(device_frame, textvariable=can_channel_var, values=["0", "1"], width=5, state="readonly")
        can_channel_combobox.pack(side=tk.LEFT, padx=5)
        widgets['can_channel_combobox'] = can_channel_combobox
        
        refresh_btn = ttk.Button(device_frame, text="刷新设备", command=lambda idx=station_idx: self.refresh_station_devices(idx))
        refresh_btn.pack(side=tk.LEFT, padx=5)
        widgets['refresh_btn'] = refresh_btn
        
        connect_btn = ttk.Button(device_frame, text="连接设备", command=lambda idx=station_idx: self.connect_station_device(idx))
        connect_btn.pack(side=tk.LEFT, padx=5)
        widgets['connect_btn'] = connect_btn
        
        status_var = tk.StringVar(value="未连接设备")
        status_label = ttk.Label(status_frame, textvariable=status_var, font=self.font)
        status_label.pack(anchor=tk.W, pady=5)
        widgets['status_label'] = status_label
        
        # 控制按钮区域
        control_frame = ttk.LabelFrame(parent, text="工位控制", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        start_btn = ttk.Button(control_frame, text="开始", command=lambda idx=station_idx: self.start_station(idx))
        start_btn.pack(side=tk.LEFT, padx=5)
        widgets['start_btn'] = start_btn
        
        pause_btn = ttk.Button(control_frame, text="暂停", command=lambda idx=station_idx: self.pause_station(idx), state=tk.DISABLED)
        pause_btn.pack(side=tk.LEFT, padx=5)
        widgets['pause_btn'] = pause_btn
        
        stop_btn = ttk.Button(control_frame, text="停止", command=lambda idx=station_idx: self.stop_station(idx), state=tk.DISABLED)
        stop_btn.pack(side=tk.LEFT, padx=5)
        widgets['stop_btn'] = stop_btn
        
        # 运行状态区域
        run_frame = ttk.LabelFrame(parent, text="运行状态", padding="10")
        run_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 为该工位创建状态变量
        station_ctrl = StationController(station_idx, self.global_log)
        
        # 显示当前阶段等信息
        ttk.Label(run_frame, textvariable=station_ctrl.phase_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.time_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.power_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # PTC_0x524 信号显示
        ttk.Label(run_frame, text="--- PTC_0x524 状态 ---", font=(self.font[0], self.font[1], "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.actual_power_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.error_level_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.error_code_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.ptc_status_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.lin_check_status_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.auto_start_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.main_status_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # PTC_0x525 信号显示
        ttk.Label(run_frame, text="--- PTC_0x525 状态 ---", font=(self.font[0], self.font[1], "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.actual_voltage_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.actual_current_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # ECC_0x4E0 信号显示
        ttk.Label(run_frame, text="--- ECC_0x4E0 状态 ---", font=(self.font[0], self.font[1], "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.target_power_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.enable_command_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=station_ctrl.target_gear_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # 日志区域
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        log_text = tk.Text(log_frame, height=8, font=self.font)
        log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_text, orient=tk.VERTICAL, command=log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(yscrollcommand=scrollbar.set)
        
        # 保存控件引用
        station_ctrl.log_text = log_text
        self.station_controllers[station_idx] = station_ctrl
        self.station_widgets[station_idx] = widgets
    
    def init_stations(self):
        """初始化所有工位"""
        for station_idx in range(10):
            # 初始化完成后自动刷新设备列表
            self.refresh_station_devices(station_idx)
            self.global_log(f"工位 {station_idx + 1} 初始化完成", "INFO")
    
    def global_log(self, message, level="INFO"):
        """全局日志记录"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def refresh_station_devices(self, station_idx):
        """刷新特定工位的设备"""
        controller = self.station_controllers[station_idx]
        widgets = self.station_widgets[station_idx]
        
        devices = controller.scan_devices()
        if devices:
            device_list = [f"{dev['serial']} ({dev['index']})" for dev in devices]
            # 更新下拉框选项
            widgets['device_combobox']['values'] = device_list
            if device_list:
                widgets['device_combobox'].set(device_list[0])  # 设置第一个设备为默认选项
            controller.log(f"发现设备: {device_list}")
        else:
            controller.log("未发现设备")
    
    def connect_station_device(self, station_idx):
        """连接特定工位的设备"""
        controller = self.station_controllers[station_idx]
        widgets = self.station_widgets[station_idx]
        
        # 获取选定的设备
        selected_device = widgets['device_combobox'].get()
        if selected_device == "请选择设备":
            controller.log("请先选择设备")
            return
        
        # 从设备列表中找到对应的设备
        devices = controller.scan_devices()
        if devices:
            # 这里简化处理，直接连接第一个设备
            success = controller.connect_device(devices[0]["handle"])
            if success:
                widgets['status_label'].config(text="设备连接成功")
                controller.log("设备连接成功")
            else:
                widgets['status_label'].config(text="设备连接失败")
                controller.log("设备连接失败")
        else:
            widgets['status_label'].config(text="未找到可用设备")
            controller.log("未找到可用设备")
    
    def start_station(self, station_idx):
        """开始特定工位的测试"""
        controller = self.station_controllers[station_idx]
        widgets = self.station_widgets[station_idx]
        
        success = controller.start_sequence()
        if success:
            widgets['start_btn'].config(state=tk.DISABLED)
            widgets['stop_btn'].config(state=tk.NORMAL)
            controller.log("工位测试开始")
        else:
            controller.log("工位测试开始失败")
    
    def pause_station(self, station_idx):
        """暂停特定工位的测试"""
        controller = self.station_controllers[station_idx]
        controller.pause_sequence()
    
    def stop_station(self, station_idx):
        """停止特定工位的测试"""
        controller = self.station_controllers[station_idx]
        widgets = self.station_widgets[station_idx]
        
        controller.stop_sequence()
        widgets['start_btn'].config(state=tk.NORMAL)
        widgets['stop_btn'].config(state=tk.DISABLED)
    
    def start_all_stations(self):
        """开始所有工位的测试"""
        for station_idx in range(10):
            self.start_station(station_idx)
    
    def stop_all_stations(self):
        """停止所有工位的测试"""
        for station_idx in range(10):
            self.stop_station(station_idx)
    
    def refresh_all_devices(self):
        """刷新所有工位的设备"""
        for station_idx in range(10):
            self.refresh_station_devices(station_idx)


def main():
    root = tk.Tk()
    app = MultiStationPTCApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()