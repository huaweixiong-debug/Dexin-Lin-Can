import time
import threading
from ctypes import *
import os
import sys

# Import device modules
try:
    from usb_device import USB_ScanDevice, USB_OpenDevice, DEV_GetDeviceInfo, DEVICE_INFO
    from usb2can import CAN_Init, CAN_SendMsg, CAN_GetMsg
    from dbc_parser import DBC_ParserFile, DBC_SetSignalValue, DBC_SyncValueToCANMsg, DBC_SyncCANMsgToValue, DBC_GetSignalValueStr
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Define constants
CAN_SUCCESS = 0
CAN_CHANNEL = 0
CAN_ID = 0x53000023B

class CANPowerTester:
    """
    CAN功率测试器类，用于连接CAN设备并执行功率测试
    """
    def __init__(self, station_idx, station_config, power_settings, time_settings, log_callback=None, test_complete_callback=None):
        """
        初始化CAN功率测试器
        
        Args:
            station_idx: 工位索引
            station_config: 工位配置
            power_settings: 功率设置字典
            time_settings: 时间设置字典
            log_callback: 日志回调函数
            test_complete_callback: 测试完成回调函数
        """
        self.station_idx = station_idx
        self.station_config = station_config
        self.power_settings = power_settings
        self.time_settings = time_settings
        self.log_callback = log_callback
        self.test_complete_callback = test_complete_callback
        
        # 设备相关变量
        self.dev_handle = None
        self.dbchandle = None
        self.device_connected = False
        self.can_initialized = False
        
        # 测试相关变量
        self.running = False
        self.paused = False
        self.current_phase = 0
        self.remaining_time = 0
        self.start_time = 0
        self.test_data = {}
        
        # 功率测试序列
        self.test_sequence = []
        self._build_test_sequence()
        
    def _build_test_sequence(self):
        """
        根据设置页面的功率参数和时间设置构建测试序列
        """
        # 功率阶段映射
        power_phases = [
            ("100%功率参数设置", "100%功率时间设置"),
            ("0%功率参数设置_1", "0%功率时间设置_1"),
            ("80%功率参数设置", "80%功率时间设置"),
            ("0%功率参数设置_2", "0%功率时间设置_2"),
            ("60%功率参数设置", "60%功率时间设置"),
            ("0%功率参数设置_3", "0%功率时间设置_3"),
            ("40%功率参数设置", "40%功率时间设置"),
            ("0%功率参数设置_4", "0%功率时间设置_4")
        ]
        
        for i, (power_key, time_key) in enumerate(power_phases):
            power_watt = int(self.power_settings.get(power_key, 0))
            time_sec = int(self.time_settings.get(time_key, 0))
            
            if time_sec > 0:
                self.test_sequence.append({
                    "phase": i + 1,
                    "power_percent": int(power_key.split('%')[0]) if '%' in power_key else 0,
                    "power_watt": power_watt,
                    "time_sec": time_sec,
                    "description": f"{power_key}运行{time_sec}秒"
                })
        
    def log(self, message, level="INFO"):
        """
        记录日志
        
        Args:
            message: 日志消息
            level: 日志级别
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] 工位{self.station_idx} - {message}"
        print(log_message)
        
        if self.log_callback:
            self.log_callback(log_message)
    
    def scan_devices(self):
        """
        扫描CAN设备
        
        Returns:
            list: 设备列表
        """
        self.log("开始扫描CAN设备")
        
        try:
            DevHandles = (c_uint * 20)()
            ret = USB_ScanDevice(byref(DevHandles))
            
            if ret == 0:
                self.log("未找到CAN设备")
                return []
            
            devices = []
            for i in range(ret):
                device = {}
                dev_info = DEVICE_INFO()
                
                if USB_OpenDevice(DevHandles[i]) == 0:
                    if DEV_GetDeviceInfo(DevHandles[i], byref(dev_info)) == 0:
                        device["handle"] = DevHandles[i]
                        device["firmware"] = dev_info.FirmwareName.decode('utf-8', errors='ignore')
                        device["hardware"] = dev_info.HardwareVersion
                        device["firmware_version"] = dev_info.FirmwareVersion
                        device["device_type"] = dev_info.DeviceType
                        devices.append(device)
                    USB_CloseDevice(DevHandles[i])
            
            self.log(f"找到{len(devices)}个CAN设备")
            return devices
            
        except Exception as e:
            self.log(f"扫描设备错误: {str(e)}", "ERROR")
            return []
    
    def connect_device(self, device_handle):
        """
        连接CAN设备
        
        Args:
            device_handle: 设备句柄
            
        Returns:
            bool: 连接是否成功
        """
        self.log("开始连接CAN设备")
        
        try:
            # 打开设备
            if USB_OpenDevice(device_handle) != 0:
                self.log("设备打开失败", "ERROR")
                return False
            
            self.dev_handle = device_handle
            self.device_connected = True
            
            # 初始化CAN
            if not self._init_can():
                self.log("CAN初始化失败", "ERROR")
                USB_CloseDevice(self.dev_handle)
                self.dev_handle = None
                self.device_connected = False
                return False
            
            self.log("CAN设备连接成功")
            return True
            
        except Exception as e:
            self.log(f"连接设备错误: {str(e)}", "ERROR")
            if self.dev_handle:
                USB_CloseDevice(self.dev_handle)
                self.dev_handle = None
            self.device_connected = False
            return False
    
    def _init_can(self):
        """
        初始化CAN通讯
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 初始化CAN通道
            # 波特率: 500Kbps
            can_config = (c_uint * 5)()
            can_config[0] = 500000  # 波特率
            can_config[1] = 0       # 模式
            can_config[2] = 0       # 过滤器
            can_config[3] = 0       # 掩码
            can_config[4] = 0       # 保留
            
            if CAN_Init(self.dev_handle, CAN_CHANNEL, byref(can_config)) != CAN_SUCCESS:
                self.log("CAN初始化失败", "ERROR")
                return False
            
            self.can_initialized = True
            self.log("CAN初始化成功")
            return True
            
        except Exception as e:
            self.log(f"CAN初始化错误: {str(e)}", "ERROR")
            return False
    
    def send_power_command(self, power_watt):
        """
        发送功率控制命令
        
        Args:
            power_watt: 功率值（瓦特）
            
        Returns:
            bool: 发送是否成功
        """
        if not self.device_connected or not self.can_initialized:
            self.log("设备未连接或CAN未初始化", "ERROR")
            return False
        
        try:
            # 构建CAN消息
            # 这里需要根据实际的CAN协议格式构建消息
            # 示例：假设消息格式为 0x4E0，数据长度为8字节
            can_msg = (c_ubyte * 16)()
            can_msg[0] = 0x4E  # CAN ID 高字节
            can_msg[1] = 0x00  # CAN ID 低字节
            can_msg[2] = 0x00  # 扩展ID
            can_msg[3] = 0x00  # 扩展ID
            can_msg[4] = 8     # 数据长度
            
            # 功率值转换为字节（示例：假设功率范围为0-2500W，使用2字节表示）
            power_value = min(max(power_watt, 0), 2500)
            can_msg[5] = (power_value >> 8) & 0xFF  # 高字节
            can_msg[6] = power_value & 0xFF        # 低字节
            can_msg[7] = 0x00  # 保留
            can_msg[8] = 0x00  # 保留
            can_msg[9] = 0x00  # 保留
            can_msg[10] = 0x00  # 保留
            can_msg[11] = 0x00  # 保留
            can_msg[12] = 0x00  # 保留
            
            # 发送CAN消息
            if CAN_SendMsg(self.dev_handle, CAN_CHANNEL, byref(can_msg)) != CAN_SUCCESS:
                self.log(f"发送功率命令失败: {power_watt}W", "ERROR")
                return False
            
            self.log(f"发送功率命令成功: {power_watt}W")
            return True
            
        except Exception as e:
            self.log(f"发送功率命令错误: {str(e)}", "ERROR")
            return False
    
    def run_test_sequence(self):
        """
        运行功率测试序列
        """
        if not self.device_connected or not self.can_initialized:
            self.log("设备未连接或CAN未初始化", "ERROR")
            return False
        
        if not self.test_sequence:
            self.log("测试序列为空", "ERROR")
            return False
        
        self.log("开始运行功率测试序列")
        self.running = True
        self.current_phase = 0
        
        try:
            for phase in self.test_sequence:
                if not self.running:
                    break
                
                self.log(f"开始阶段{phase['phase']}: {phase['description']}")
                
                # 发送功率命令
                if not self.send_power_command(phase['power_watt']):
                    self.log(f"阶段{phase['phase']}功率命令发送失败", "ERROR")
                    continue
                
                # 运行指定时间
                start_time = time.time()
                end_time = start_time + phase['time_sec']
                
                while time.time() < end_time and self.running:
                    if self.paused:
                        pause_start = time.time()
                        while self.paused and self.running:
                            time.sleep(0.1)
                        pause_duration = time.time() - pause_start
                        end_time += pause_duration
                    
                    # 监控测试状态
                    self._monitor_test()
                    time.sleep(1)
                
                # 记录阶段结果
                self.test_data[f"phase_{phase['phase']}"] = {
                    "power_watt": phase['power_watt'],
                    "time_sec": phase['time_sec'],
                    "status": "completed" if self.running else "interrupted"
                }
                
                self.log(f"阶段{phase['phase']}完成")
            
            # 测试完成，发送0功率命令
            self.send_power_command(0)
            
            if self.running:
                self.log("功率测试序列运行完成")
                if self.test_complete_callback:
                    self.test_complete_callback(self.test_data)
                return True
            else:
                self.log("功率测试序列被中断")
                return False
                
        except Exception as e:
            self.log(f"运行测试序列错误: {str(e)}", "ERROR")
            # 发送0功率命令
            self.send_power_command(0)
            return False
        finally:
            self.running = False
    
    def _monitor_test(self):
        """
        监控测试状态
        """
        try:
            # 这里可以添加代码来监控测试状态，例如读取CAN消息获取实际功率、电压、电流等
            # 示例：读取CAN消息
            can_msg = (c_ubyte * 16)()
            
            # 尝试读取CAN消息
            if CAN_GetMsg(self.dev_handle, CAN_CHANNEL, byref(can_msg)) == CAN_SUCCESS:
                # 处理CAN消息
                can_id = (can_msg[0] << 8) | can_msg[1]
                data_len = can_msg[4]
                
                if can_id == 0x530:  # 假设0x530是状态消息
                    # 解析状态消息
                    # 这里需要根据实际的CAN协议格式解析
                    pass
                    
        except Exception as e:
            self.log(f"监控测试错误: {str(e)}", "ERROR")
    
    def stop_test(self):
        """
        停止测试
        """
        self.log("停止功率测试")
        self.running = False
        self.paused = False
        
        # 发送0功率命令
        self.send_power_command(0)
    
    def pause_test(self):
        """
        暂停测试
        """
        self.paused = not self.paused
        if self.paused:
            self.log("功率测试已暂停")
        else:
            self.log("功率测试已继续")
    
    def disconnect_device(self):
        """
        断开CAN设备
        """
        self.log("断开CAN设备")
        
        # 停止测试
        if self.running:
            self.stop_test()
        
        # 关闭设备
        if self.dev_handle:
            try:
                USB_CloseDevice(self.dev_handle)
                self.log("CAN设备已关闭")
            except Exception as e:
                self.log(f"关闭设备错误: {str(e)}", "ERROR")
            finally:
                self.dev_handle = None
                self.device_connected = False
                self.can_initialized = False
