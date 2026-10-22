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

class PTCPowerSequenceApp:
    def __init__(self, root):
        try:
            print("=== 开始初始化PTCPowerSequenceApp ===")
            self.root = root
            self.root.title("PTC功率序列控制")
            self.root.geometry("800x600")
            
            print("=== 设置字体 ===")
            # 设置字体
            self.font = ("SimHei", 10)
            
            print("=== 定义CAN通道 ===")
            # 定义CAN通道
            self.CAN_CHANNEL = 0  # 诊断显示通道0有数据
            self.CAN_ID = 0x53000023B  # CAN ID
            
            print("=== 初始化设备相关变量 ===")
            # 设备相关变量
            self.dev_handle = None
            self.dbchandle = None
            self.device_connected = False
            
            print("=== 初始化运行状态变量 ===")
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
            
            print("=== 定义默认参数序列 ===")
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
            
            print("=== 复制当前参数序列 ===")
            # 当前参数序列
            self.current_sequence = self.default_sequence.copy()
            
            # CAN模式配置
            self.use_canfd = False  # 默认使用传统CAN，不使用CANFD
            self.can_initialized = False
            
            print("=== 创建UI ===")
            # 创建UI
            self.create_ui()
            print("=== UI创建成功 ===")
            
            print("=== 初始化设备 ===")
            # 初始化设备
            self.init_device()
            print("=== 设备初始化完成 ===")
        except Exception as e:
            print(f"=== 初始化错误: {str(e)} ===")
            import traceback
            traceback.print_exc()
            # 继续执行，以便窗口能够显示
            pass
    
    def create_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设备状态区域
        status_frame = ttk.LabelFrame(main_frame, text="设备状态", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        # 设备选择区域
        device_frame = ttk.Frame(status_frame)
        device_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(device_frame, text="选择设备:", font=self.font).pack(side=tk.LEFT, padx=5)
        self.device_var = tk.StringVar(value="请选择设备")
        self.device_combobox = ttk.Combobox(device_frame, textvariable=self.device_var, font=self.font, width=40, state="readonly")
        self.device_combobox.pack(side=tk.LEFT, padx=5)
        
        # CAN通道选择
        ttk.Label(device_frame, text="CAN通道:", font=self.font).pack(side=tk.LEFT, padx=5)
        self.can_channel_var = tk.StringVar(value="0")
        self.can_channel_combobox = ttk.Combobox(device_frame, textvariable=self.can_channel_var, values=["0", "1"], width=5, state="readonly")
        self.can_channel_combobox.pack(side=tk.LEFT, padx=5)
        
        self.refresh_device_btn = ttk.Button(device_frame, text="刷新设备", command=self.refresh_devices)
        self.refresh_device_btn.pack(side=tk.LEFT, padx=5)
        
        self.connect_device_btn = ttk.Button(device_frame, text="连接设备", command=self.connect_selected_device)
        self.connect_device_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="未连接设备")
        ttk.Label(status_frame, textvariable=self.status_var, font=self.font).pack(anchor=tk.W, pady=5)
        
        # 参数设置区域
        params_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        params_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建参数表格
        self.param_entries = []
        
        # 表格标题
        ttk.Label(params_frame, text="阶段", font=self.font, width=10).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(params_frame, text="功率(W)", font=self.font, width=10).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(params_frame, text="时间(秒)", font=self.font, width=10).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(params_frame, text="描述", font=self.font, width=30).grid(row=0, column=3, padx=5, pady=5)
        
        # 添加参数行
        for i, phase in enumerate(self.current_sequence):
            phase_frame = ttk.Frame(params_frame)
            phase_frame.grid(row=i+1, column=0, padx=5, pady=5, sticky=tk.W)
            ttk.Label(phase_frame, text=f"阶段{i+1}", font=self.font).pack()
            
            power_entry = ttk.Entry(params_frame, width=10, font=self.font)
            power_entry.insert(0, str(phase["power_watt"]))
            power_entry.grid(row=i+1, column=1, padx=5, pady=5)
            
            time_entry = ttk.Entry(params_frame, width=10, font=self.font)
            time_entry.insert(0, str(phase["time_sec"]))
            time_entry.grid(row=i+1, column=2, padx=5, pady=5)
            
            desc_label = ttk.Label(params_frame, text=phase["description"], font=self.font, width=30)
            desc_label.grid(row=i+1, column=3, padx=5, pady=5, sticky=tk.W)
            
            self.param_entries.append((power_entry, time_entry, desc_label))
        
        # 控制按钮区域
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="开始", command=self.start_sequence)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="暂停", command=self.pause_sequence, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="停止", command=self.stop_sequence, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_btn = ttk.Button(control_frame, text="重置参数", command=self.reset_parameters)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        # 运行状态区域
        run_frame = ttk.LabelFrame(main_frame, text="运行状态", padding="10")
        run_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
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
        
        ttk.Label(run_frame, textvariable=self.phase_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.time_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.power_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # PTC_0x524 信号显示
        ttk.Label(run_frame, text="--- PTC_0x524 状态 ---", font=(self.font[0], self.font[1], "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.actual_power_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.error_level_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.error_code_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.ptc_status_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.lin_check_status_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.auto_start_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.main_status_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # PTC_0x525 信号显示
        ttk.Label(run_frame, text="--- PTC_0x525 状态 ---", font=(self.font[0], self.font[1], "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.actual_voltage_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.actual_current_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # ECC_0x4E0 信号显示
        ttk.Label(run_frame, text="--- ECC_0x4E0 状态 ---", font=(self.font[0], self.font[1], "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.target_power_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.enable_command_var, font=self.font).pack(anchor=tk.W, pady=2)
        ttk.Label(run_frame, textvariable=self.target_gear_var, font=self.font).pack(anchor=tk.W, pady=2)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, font=self.font)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.log_text, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def init_device(self):
        """初始化设备（已迁移到refresh_devices和connect_selected_device方法）"""
        # 初始化状态变量
        self.can_initialized = False
        self.device_connected = False
        self.device_info = {}
        
        # 自动刷新设备列表
        self.refresh_devices()
        
        # 记录初始化完成
        self.log("设备初始化流程已迁移到手动选择模式", "INFO")
        self.log("请在设备状态区域选择并连接设备", "INFO")
    
    def log(self, message, level="INFO"):
        """记录日志信息
        
        Args:
            message: 日志消息
            level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        # 同时打印到控制台，便于调试
        print(log_entry.strip())
    
    def read_parameters(self):
        """读取用户设置的参数"""
        try:
            for i, (power_entry, time_entry, _) in enumerate(self.param_entries):
                # 读取功率值（瓦特）
                try:
                    power_watt = int(power_entry.get())
                    # 验证功率值范围（根据DBC文件，最大10000W）
                    if power_watt < 0 or power_watt > 10000:
                        messagebox.showerror("错误", f"阶段{i+1}的功率必须在0-10000W之间")
                        return False
                except ValueError:
                    messagebox.showerror("错误", f"阶段{i+1}的功率必须是有效的整数")
                    return False
                
                # 读取时间值
                try:
                    time_sec = int(time_entry.get())
                    # 验证时间范围
                    if time_sec < 1:
                        messagebox.showerror("错误", f"阶段{i+1}的时间必须大于0秒")
                        return False
                    if time_sec > 3600:  # 最大1小时
                        messagebox.showerror("错误", f"阶段{i+1}的时间不能超过3600秒")
                        return False
                except ValueError:
                    messagebox.showerror("错误", f"阶段{i+1}的时间必须是有效的整数")
                    return False
                
                # 计算功率百分比（保持兼容性）
                power_percent = int((power_watt / 2500) * 100) if power_watt > 0 else 0
                power_percent = min(power_percent, 100)  # 确保不超过100%
                
                # 更新序列参数
                self.current_sequence[i]["power_percent"] = power_percent
                self.current_sequence[i]["time_sec"] = time_sec
                self.current_sequence[i]["power_watt"] = power_watt
                # 更新描述
                if power_watt > 0:
                    self.current_sequence[i]["description"] = f"{power_watt}W运行{time_sec}秒"
                else:
                    self.current_sequence[i]["description"] = f"0W运行{time_sec}秒"
                # 更新UI显示
                _, _, desc_label = self.param_entries[i]
                desc_label.config(text=self.current_sequence[i]["description"])
                
            self.log("参数读取成功")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"参数读取错误: {str(e)}")
            return False
    
    def reset_parameters(self):
        """重置参数为默认值"""
        self.current_sequence = self.default_sequence.copy()
        
        for i, (power_entry, time_entry, desc_label) in enumerate(self.param_entries):
            phase = self.current_sequence[i]
            power_entry.delete(0, tk.END)
            power_entry.insert(0, str(phase["power_watt"]))
            time_entry.delete(0, tk.END)
            time_entry.insert(0, str(phase["time_sec"]))
            desc_label.config(text=phase["description"])
        
        self.log("参数已重置为默认值")
    
    def start_sequence(self):
        """开始运行序列"""
        if not self.device_connected:
            messagebox.showerror("错误", "设备未连接")
            return
        
        if not self.can_initialized:
            messagebox.showerror("错误", "CAN未初始化")
            return
        
        if not self.read_parameters():
            return
        
        # 记录序列信息
        sequence_info = "\n".join([f"阶段{i+1}: {phase['description']}" for i, phase in enumerate(self.current_sequence)])
        self.log(f"功率序列信息:\n{sequence_info}", "INFO")
        
        self.running = True
        self.paused = False
        self.current_phase = 0
        self.remaining_time = 0
        
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.reset_btn.config(state=tk.DISABLED)
        
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
    
    def pause_sequence(self):
        """暂停运行"""
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.config(text="继续")
            self.log("序列运行已暂停")
        else:
            self.pause_btn.config(text="暂停")
            self.start_time = time.time() - (self.current_sequence[self.current_phase]["time_sec"] - self.remaining_time)
            self.log("序列运行已继续")
    
    def stop_sequence(self):
        """停止运行"""
        self.running = False
        self.paused = False
        self.send_running = False
        
        # 发送0功率命令
        self.send_power_command(0)
        
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED, text="暂停")
        self.stop_btn.config(state=tk.DISABLED)
        self.reset_btn.config(state=tk.NORMAL)
        
        self.phase_var.set("当前阶段: 已停止")
        self.time_var.set("剩余时间: 0秒")
        self.power_var.set("目标功率: 0W")
        
        self.log("序列运行已停止")
    
    def run_sequence(self):
        """运行功率序列"""
        try:
            self.log(f"开始运行功率序列，共{len(self.current_sequence)}个阶段", "INFO")
            
            for phase_idx, phase in enumerate(self.current_sequence):
                if not self.running:
                    self.log(f"序列运行被手动停止，当前阶段: {phase_idx+1}", "WARNING")
                    break
                
                self.current_phase = phase_idx
                self.remaining_time = phase["time_sec"]
                self.start_time = time.time()
                
                # 发送功率命令
                power_watt = phase["power_watt"]
                self.log(f"准备发送功率命令: {power_watt}W", "DEBUG")
                self.send_power_command(power_watt)
                
                self.log(f"开始阶段{phase_idx+1}: {phase['description']}", "INFO")
                
                # 运行当前阶段
                while self.remaining_time > 0 and self.running:
                    if not self.paused:
                        elapsed = time.time() - self.start_time
                        self.remaining_time = max(0, phase["time_sec"] - int(elapsed))
                        # 每10秒记录一次状态
                        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                            self.log(f"阶段{phase_idx+1} - 已运行{int(elapsed)}秒，剩余{self.remaining_time}秒", "DEBUG")
                        time.sleep(0.5)
                    else:
                        time.sleep(0.1)
                
                if not self.running:
                    self.log(f"序列运行被手动停止，当前阶段: {phase_idx+1}", "WARNING")
                    break
                
                self.log(f"完成阶段{phase_idx+1}: {phase['description']}", "INFO")
            
            if self.running:
                # 运行完成
                self.log("发送最终功率命令: 0W", "DEBUG")
                self.send_power_command(0)
                self.log("功率序列运行完成", "INFO")
                self.phase_var.set("当前阶段: 运行完成")
                self.time_var.set("剩余时间: 0秒")
                self.power_var.set("目标功率: 0W")
                
                self.start_btn.config(state=tk.NORMAL)
                self.pause_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.DISABLED)
                self.reset_btn.config(state=tk.NORMAL)
                
                self.log("序列运行完成，所有阶段已执行", "INFO")
                
        except Exception as e:
            self.log(f"运行错误: {str(e)}", "ERROR")
            import traceback
            self.log(f"详细错误: {traceback.format_exc()}", "ERROR")
            self.stop_sequence()
    
    def send_power_command(self, power_watt):
        """更新功率控制命令（由发送线程实际发送）"""
        # 检查设备是否已连接且CAN是否已初始化
        if not getattr(self, 'device_connected', False):
            self.log(f"设备未连接，无法更新功率命令: {power_watt}W")
            print(f"设备未连接，无法更新功率命令: {power_watt}W")
            return
        
        if not getattr(self, 'can_initialized', False):
            self.log(f"CAN未初始化，无法更新功率命令: {power_watt}W")
            print(f"CAN未初始化，无法更新功率命令: {power_watt}W")
            return
        
        try:
            # 更新当前功率值
            self.current_power = power_watt
            
            # 设置使能命令（功率>0时使能，否则禁用）
            enable_cmd = 1 if power_watt > 0 else 0
            
            # 设置目标档位（根据功率自动设置）
            if power_watt >= 2000:
                target_gear = 3
            elif power_watt >= 1500:
                target_gear = 2
            elif power_watt >= 1000:
                target_gear = 1
            else:
                target_gear = 0
            
            # 更新ECC_0x4E0状态显示
            current_target_power_text = f"目标功率: {power_watt}W"
            if self.target_power_var.get() != current_target_power_text:
                self.target_power_var.set(current_target_power_text)
            current_enable_command_text = f"使能命令: {enable_cmd}"
            if self.enable_command_var.get() != current_enable_command_text:
                self.enable_command_var.set(current_enable_command_text)
            current_target_gear_text = f"目标档位: {target_gear}"
            if self.target_gear_var.get() != current_target_gear_text:
                self.target_gear_var.set(current_target_gear_text)
            
            self.log(f"更新功率命令: {power_watt}W")
            print(f"更新功率命令: {power_watt}W")
        except Exception as e:
            print(f"更新功率命令错误: {str(e)}")
            self.log(f"更新功率命令错误: {str(e)}")
    
    def send_4e0_message(self):
        """循环发送0x4E0消息"""
        while self.send_running:
            try:
                # 检查设备是否已连接且CAN是否已初始化
                if not getattr(self, 'device_connected', False) or not getattr(self, 'can_initialized', False):
                    time.sleep(0.1)
                    continue
                
                # 获取当前功率值
                power_watt = self.current_power
                
                # 设置使能命令（功率>0时使能，否则禁用）
                enable_cmd = 1 if power_watt > 0 else 0
                
                # 设置目标档位（根据功率自动设置）
                if power_watt >= 2000:
                    target_gear = 3
                elif power_watt >= 1500:
                    target_gear = 2
                elif power_watt >= 1000:
                    target_gear = 1
                else:
                    target_gear = 0
                
                # 发送命令
                if getattr(self, 'use_canfd', False) and 'CANFD_SendMsg' in globals():
                    # 使用CANFD发送消息
                    try:
                        CanMsg = (CANFD_MSG*1)()
                        CanMsg[0].ID = 0x4E0  # ECC_0x4E0的CAN ID
                        CanMsg[0].DLC = 8  # 数据长度为8字节
                        CanMsg[0].Flags = 0x00  # 0x00-标准CAN帧, 0x04-CANFD帧 (PTC为标准CAN设备)
                        CanMsg[0].TimeStamp = 0
                        
                        # 根据DBC文件中的信号定义构建数据
                        # ECC_TarPwr_PTC：起始字节23，长度16位，单位"W"，范围0-10000
                        # ECC_EnaCmd_PTC：起始字节55，长度2位，范围0-3
                        
                        power_value = min(int(power_watt), 10000)
                        
                        # 设置功率值（字节2和3，起始位16，长度16位）
                        CanMsg[0].Data[2] = (power_value >> 8) & 0xFF  # 功率高8位
                        CanMsg[0].Data[3] = power_value & 0xFF  # 功率低8位
                        
                        # 设置使能命令（字节6，起始位55，长度2位）
                        # 使能1对应0x40（位55-56=01），禁用对应0x00
                        CanMsg[0].Data[6] = 0x40 if enable_cmd else 0x00
                        
                        # 其他字节设置为0
                        CanMsg[0].Data[0] = 0x00
                        CanMsg[0].Data[1] = 0x00
                        CanMsg[0].Data[4] = 0x00
                        CanMsg[0].Data[5] = 0x00
                        CanMsg[0].Data[7] = 0x00
                        # 添加调试信息，显示发送的功率值和相关参数
                        print(f"发送0x4E0消息: 功率={power_watt}W, 使能={enable_cmd}, 档位={target_gear}")
                        print(f"数据: {CanMsg[0].Data[0]:02X} {CanMsg[0].Data[1]:02X} {CanMsg[0].Data[2]:02X} {CanMsg[0].Data[3]:02X} {CanMsg[0].Data[4]:02X} {CanMsg[0].Data[5]:02X} {CanMsg[0].Data[6]:02X} {CanMsg[0].Data[7]:02X}")
                        
                        SendedNum = CANFD_SendMsg(self.dev_handle, self.CAN_CHANNEL, CanMsg, 1)
                        if SendedNum < 0:
                            self.log(f"发送0x4E0消息失败: {SendedNum} (CANFD)")
                        else:
                            # 添加详细的发送日志，格式与图片一致
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            device_id = getattr(self, 'device_serial', 'N/A')
                            can_type = 'CANFD'
                            can_id = '0x4E0'
                            channel = self.CAN_CHANNEL
                            data_len = 8
                            data = ' '.join([f"{b:02X}" for b in CanMsg[0].Data[:8]])
                            operation = '发送'
                            log_message = f"[{timestamp}] {device_id} {can_type} {can_id} {channel} {data_len} {data} {operation}"
                            print(log_message)
                            self.log(log_message)
                    except Exception as e:
                        print(f"CANFD发送0x4E0消息错误: {str(e)}")
                        self.log(f"CANFD发送0x4E0消息错误: {str(e)}")
                        # 尝试使用传统CAN发送
                        self.use_canfd = False
                else:
                    # 使用传统CAN发送消息
                    try:
                        CanMsg = (CAN_MSG*1)()
                        CanMsg[0].ExternFlag = 0  # 使用标准帧
                        CanMsg[0].RemoteFlag = 0  # 使用数据帧
                        CanMsg[0].ID = 0x4E0  # ECC_0x4E0的CAN ID
                        CanMsg[0].DataLen = 8  # 数据长度为8字节
                        
                        # 根据DBC文件中的信号定义构建数据
                        # ECC_TarPwr_PTC：起始字节23，长度16位，单位"W"，范围0-10000
                        # ECC_EnaCmd_PTC：起始字节55，长度2位，范围0-3
                        
                        power_value = min(int(power_watt), 10000)
                        
                        # 设置功率值（字节2和3，起始位16，长度16位）
                        CanMsg[0].Data[2] = (power_value >> 8) & 0xFF  # 功率高8位
                        CanMsg[0].Data[3] = power_value & 0xFF  # 功率低8位
                        
                        # 设置使能命令（字节6，起始位55，长度2位）
                        # 使能1对应0x40（位55-56=01），禁用对应0x00
                        CanMsg[0].Data[6] = 0x40 if enable_cmd else 0x00
                        
                        # 其他字节设置为0
                        CanMsg[0].Data[0] = 0x00
                        CanMsg[0].Data[1] = 0x00
                        CanMsg[0].Data[4] = 0x00
                        CanMsg[0].Data[5] = 0x00
                        CanMsg[0].Data[7] = 0x00
                        # 添加调试信息，显示发送的功率值和相关参数
                        print(f"传统CAN发送0x4E0消息: 功率={power_watt}W, 使能={enable_cmd}, 档位={target_gear}")
                        print(f"数据: {CanMsg[0].Data[0]:02X} {CanMsg[0].Data[1]:02X} {CanMsg[0].Data[2]:02X} {CanMsg[0].Data[3]:02X} {CanMsg[0].Data[4]:02X} {CanMsg[0].Data[5]:02X} {CanMsg[0].Data[6]:02X} {CanMsg[0].Data[7]:02X}")
                        
                        SendedNum = CAN_SendMsg(self.dev_handle, self.CAN_CHANNEL, CanMsg, 1)
                        if SendedNum < 0:
                            self.log(f"发送0x4E0消息失败: {SendedNum} (传统CAN)")
                        else:
                            # 添加详细的发送日志，格式与图片一致
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            device_id = getattr(self, 'device_serial', 'N/A')
                            can_type = 'CAN'
                            can_id = '0x4E0'
                            channel = self.CAN_CHANNEL
                            data_len = 8
                            data = ' '.join([f"{b:02X}" for b in CanMsg[0].Data[:8]])
                            operation = '发送'
                            log_message = f"[{timestamp}] {device_id} {can_type} {can_id} {channel} {data_len} {data} {operation}"
                            print(log_message)
                            self.log(log_message)
                    except Exception as e:
                        print(f"传统CAN发送0x4E0消息错误: {str(e)}")
                        self.log(f"传统CAN发送0x4E0消息错误: {str(e)}")
                
                # 按照图片中的设置，每100ms发送一次
                time.sleep(0.1)
                
            except Exception as e:
                print(f"发送0x4E0消息错误: {str(e)}")
                self.log(f"发送0x4E0消息错误: {str(e)}")
                time.sleep(0.1)
    
    def update_status(self):
        """实时更新运行状态"""
        while True:
            if not self.running:
                time.sleep(1)
                continue
            
            if self.current_phase < len(self.current_sequence):
                phase = self.current_sequence[self.current_phase]
                # 只在值变化时更新UI，减少不必要的更新
                current_phase_text = f"当前阶段: {self.current_phase+1}/{len(self.current_sequence)}"
                current_time_text = f"剩余时间: {self.remaining_time}秒"
                current_power_text = f"目标功率: {phase['power_watt']}W ({phase['power_percent']}%)"
                
                if self.phase_var.get() != current_phase_text:
                    self.phase_var.set(current_phase_text)
                if self.time_var.get() != current_time_text:
                    self.time_var.set(current_time_text)
                if self.power_var.get() != current_power_text:
                    self.power_var.set(current_power_text)
                
                # 读取实际功率、电压和电流（每次循环都读取，确保实时更新）
                self.read_actual_power()
            
            time.sleep(0.5)  # 缩短休眠时间，提高响应速度
    
    def read_actual_power(self):
        """读取实际功率"""
        # 检查设备是否已连接且CAN是否已初始化
        if not getattr(self, 'device_connected', False):
            return
        
        if not getattr(self, 'can_initialized', False):
            return
        
        try:
            if getattr(self, 'use_canfd', False) and 'CANFD_GetMsg' in globals():
                # 使用CANFD读取消息
                try:
                    # 减少缓冲区大小，只需要少量消息
                    CanMsgBuffer = (CANFD_MSG*64)()
                    CanNum = CANFD_GetMsg(self.dev_handle, self.CAN_CHANNEL, byref(CanMsgBuffer), 64)
                    
                    # 添加调试信息，显示是否接收到消息
                    print(f"CANFD_GetMsg返回值: {CanNum}")
                    if CanNum > 0:
                        # 打印接收到的消息数量，便于调试
                        print(f"接收到 {CanNum} 条CANFD消息")
                        # 手动解析PTC_0x524和0x525消息
                        for i in range(CanNum):
                            # 打印接收到的消息ID，便于调试
                            print(f"消息 {i} ID: 0x{CanMsgBuffer[i].ID:X}, DLC: {CanMsgBuffer[i].DLC}")
                            # 打印接收到的原始数据，便于调试
                            data_str = ' '.join([f"{b:02X}" for b in CanMsgBuffer[i].Data[:CanMsgBuffer[i].DLC]])
                            print(f"消息 {i} 数据: {data_str}")
                            # 即使不是0x524或0x525，也打印所有接收到的消息ID
                            print(f"接收到的消息ID: 0x{CanMsgBuffer[i].ID:X}")
                            if CanMsgBuffer[i].ID == 0x524:  # PTC_0x524的CAN ID
                                # 添加详细的接收日志，格式与图片一致
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                                device_id = getattr(self, 'device_serial', 'N/A')
                                can_type = 'CANFD'
                                can_id = '0x524'
                                channel = self.CAN_CHANNEL
                                data_len = CanMsgBuffer[i].DLC
                                data = ' '.join([f"{b:02X}" for b in CanMsgBuffer[i].Data[:data_len]])
                                operation = '接收'
                                # 按照图片中的格式输出日志
                                log_message = f"[{timestamp}] {device_id} {can_type} {can_id} {channel} {data_len} {data} {operation}"
                                print(log_message)
                                self.log(log_message)
                                
                                # 根据DBC文件中的信号定义解析0x524消息
                                # PTC_ErrCode：起始位21，长度6位
                                # PTC_ErrorLevel：起始位23，长度2位
                                # PTC_CrtPwr：起始位39，长度16位，范围0-10000
                                # PTC_CrtT：起始位55，长度8位，偏移-48，单位"°C"
                                # PTC_IninSts：起始位56，长度1位
                                # PTC_HVPwrSplySts：起始位57，长度1位
                                # PTC_ActGear：起始位61，长度4位
                                # PTC_Mod：起始位62，长度1位
                                # PTC_HVIntlkFlt：起始位63，长度1位
                                
                                # 解析错误代码和错误等级
                                error_level = (CanMsgBuffer[i].Data[2] >> 6) & 0x03  # 字节2，位6-7
                                error_code = CanMsgBuffer[i].Data[2] & 0x3F  # 字节2，位0-5
                                
                                # 解析实际功率（字节4和5，起始位39）
                                # 假设大端模式 (Motorola): Data[4] MSB, Data[5] LSB
                                actual_power = (CanMsgBuffer[i].Data[4] << 8) | CanMsgBuffer[i].Data[5]
                                
                                # 解析温度（字节6，起始位55）
                                ptc_temp = CanMsgBuffer[i].Data[6] - 48  # 偏移-48
                                
                                # 解析状态位（字节7）
                                ptc_init_status = (CanMsgBuffer[i].Data[7] >> 0) & 0x01  # 位0
                                ptc_hv_power_status = (CanMsgBuffer[i].Data[7] >> 1) & 0x01  # 位1
                                ptc_act_gear = (CanMsgBuffer[i].Data[7] >> 5) & 0x0F  # 位5-8
                                ptc_mode = (CanMsgBuffer[i].Data[7] >> 9) & 0x01  # 位9（需要跨字节）
                                ptc_hv_intlk_fault = (CanMsgBuffer[i].Data[7] >> 10) & 0x01  # 位10（需要跨字节）
                                
                                # 打印调试信息
                                raw_hex = ' '.join([f'{b:02X}' for b in CanMsgBuffer[i].Data[:8]])
                                print(f"RX 0x524 [{raw_hex}] -> Power: {actual_power}W, Temp: {ptc_temp}C")

                                # 只在值变化时更新UI
                                current_power_text = f"实际功率: {actual_power}W (CANFD)"
                                if self.actual_power_var.get() != current_power_text:
                                    self.actual_power_var.set(current_power_text)
                                current_error_level_text = f"故障等级: {error_level}"
                                if self.error_level_var.get() != current_error_level_text:
                                    self.error_level_var.set(current_error_level_text)
                                current_error_code_text = f"故障码: {error_code}"
                                if self.error_code_var.get() != current_error_code_text:
                                    self.error_code_var.set(current_error_code_text)
                                current_ptc_temp_text = f"PTC温度: {ptc_temp}°C"
                                if hasattr(self, 'ptc_temp_var'):
                                    if self.ptc_temp_var.get() != current_ptc_temp_text:
                                        self.ptc_temp_var.set(current_ptc_temp_text)
                                current_ptc_init_status_text = f"初始化状态: {ptc_init_status}"
                                if hasattr(self, 'ptc_init_status_var'):
                                    if self.ptc_init_status_var.get() != current_ptc_init_status_text:
                                        self.ptc_init_status_var.set(current_ptc_init_status_text)
                                current_ptc_hv_power_status_text = f"高压供电状态: {ptc_hv_power_status}"
                                if hasattr(self, 'ptc_hv_power_status_var'):
                                    if self.ptc_hv_power_status_var.get() != current_ptc_hv_power_status_text:
                                        self.ptc_hv_power_status_var.set(current_ptc_hv_power_status_text)
                                current_ptc_act_gear_text = f"实际档位: {ptc_act_gear}"
                                if hasattr(self, 'ptc_act_gear_var'):
                                    if self.ptc_act_gear_var.get() != current_ptc_act_gear_text:
                                        self.ptc_act_gear_var.set(current_ptc_act_gear_text)
                                current_ptc_mode_text = f"PTC模式: {ptc_mode}"
                                if hasattr(self, 'ptc_mode_var'):
                                    if self.ptc_mode_var.get() != current_ptc_mode_text:
                                        self.ptc_mode_var.set(current_ptc_mode_text)
                                current_ptc_hv_intlk_fault_text = f"高压互锁故障: {ptc_hv_intlk_fault}"
                                if hasattr(self, 'ptc_hv_intlk_fault_var'):
                                    if self.ptc_hv_intlk_fault_var.get() != current_ptc_hv_intlk_fault_text:
                                        self.ptc_hv_intlk_fault_var.set(current_ptc_hv_intlk_fault_text)
                            elif CanMsgBuffer[i].ID == 0x525:  # PTC_0x525的CAN ID
                                # 添加详细的接收日志，格式与图片一致
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                                device_id = getattr(self, 'device_serial', 'N/A')
                                can_type = 'CANFD'
                                can_id = '0x525'
                                channel = self.CAN_CHANNEL
                                data_len = CanMsgBuffer[i].DLC
                                data = ' '.join([f"{b:02X}" for b in CanMsgBuffer[i].Data[:data_len]])
                                operation = '接收'
                                # 按照图片中的格式输出日志
                                log_message = f"[{timestamp}] {device_id} {can_type} {can_id} {channel} {data_len} {data} {operation}"
                                print(log_message)
                                self.log(log_message)
                                
                                # 根据DBC文件中的信号定义解析0x525消息
                                # PTC_PCBT：起始位23，长度8位，偏移-48
                                # PTC_Crt：起始位31，长度16位，精度0.001
                                # PTC_CrtSts：起始位41，长度2位
                                # PTC_CrtVolt：起始位55，长度16位，范围0-1000
                                
                                # 解析PCBT（字节2，起始位23）
                                ptc_pcbt = CanMsgBuffer[i].Data[2] - 48  # 偏移-48
                                
                                # 解析电流（字节3和4，起始位31）
                                # 假设大端模式: Data[3] MSB, Data[4] LSB
                                actual_current = ((CanMsgBuffer[i].Data[3] << 8) | CanMsgBuffer[i].Data[4]) * 0.001
                                
                                # 解析电流状态（字节5，起始位41）
                                ptc_crt_status = (CanMsgBuffer[i].Data[5] >> 1) & 0x03  # 位1-2
                                
                                # 解析电压（字节6和7，起始位55）
                                # 假设大端模式: Data[6] MSB, Data[7] LSB
                                actual_voltage = (CanMsgBuffer[i].Data[6] << 8) | CanMsgBuffer[i].Data[7]
                                
                                # 打印调试信息
                                print(f"RX 0x525 [{data}] -> Temp: {ptc_pcbt}, Curr: {actual_current:.3f}, Volt: {actual_voltage}")
                                
                                # 只在值变化时更新UI
                                current_voltage_text = f"实际电压: {actual_voltage}V"
                                current_current_text = f"实际电流: {actual_current:.3f}A"
                                if hasattr(self, 'actual_voltage_var'):
                                    if self.actual_voltage_var.get() != current_voltage_text:
                                        self.actual_voltage_var.set(current_voltage_text)
                                if hasattr(self, 'actual_current_var'):
                                    if self.actual_current_var.get() != current_current_text:
                                        self.actual_current_var.set(current_current_text)
                except Exception as e:
                    # 只在调试模式下打印错误
                    import traceback
                    traceback.print_exc()
                    # 尝试使用传统CAN读取
                    self.use_canfd = False
                    # 避免递归调用，直接执行传统CAN读取
                    self._read_actual_power_traditional()
            else:
                # 使用传统CAN读取消息
                self._read_actual_power_traditional()
                
        except Exception as e:
            # 只在调试模式下打印错误
            pass
    
    def _read_actual_power_traditional(self):
        """使用传统CAN读取实际功率"""
        try:
            # 减少缓冲区大小，只需要少量消息
            CanMsgBuffer = (CAN_MSG*64)()
            CanNum = CAN_GetMsg(self.dev_handle, self.CAN_CHANNEL, byref(CanMsgBuffer))
            
            # 添加调试信息，显示是否接收到消息
            print(f"CAN_GetMsg返回值: {CanNum}")
            if CanNum > 0:
                # 打印接收到的消息数量，便于调试
                print(f"接收到 {CanNum} 条传统CAN消息")
                # 手动解析PTC_0x524和0x525消息
                for i in range(CanNum):
                    # 打印接收到的消息ID，便于调试
                    print(f"消息 {i} ID: 0x{CanMsgBuffer[i].ID:X}, DLC: {CanMsgBuffer[i].DataLen}")
                    # 打印接收到的原始数据，便于调试
                    data_str = ' '.join([f"{b:02X}" for b in CanMsgBuffer[i].Data[:CanMsgBuffer[i].DataLen]])
                    print(f"消息 {i} 数据: {data_str}")
                    # 即使不是0x524或0x525，也打印所有接收到的消息ID
                    print(f"接收到的消息ID: 0x{CanMsgBuffer[i].ID:X}")
                    if CanMsgBuffer[i].ID == 0x524:  # PTC_0x524的CAN ID
                        # 添加详细的接收日志，格式与图片一致
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        device_id = getattr(self, 'device_serial', 'N/A')
                        can_type = 'CAN'
                        can_id = '0x524'
                        channel = self.CAN_CHANNEL
                        data_len = CanMsgBuffer[i].DataLen
                        data = ' '.join([f"{b:02X}" for b in CanMsgBuffer[i].Data[:data_len]])
                        operation = '接收'
                        # 按照图片中的格式输出日志
                        log_message = f"[{timestamp}] {device_id} {can_type} {can_id} {channel} {data_len} {data} {operation}"
                        print(log_message)
                        self.log(log_message)
                        
                        # 根据DBC文件中的信号定义解析0x524消息
                        # PTC_ErrCode：起始位21，长度6位
                        # PTC_ErrorLevel：起始位23，长度2位
                        # PTC_CrtPwr：起始位39，长度16位，范围0-10000
                        # PTC_CrtT：起始位55，长度8位，偏移-48，单位"°C"
                        # PTC_IninSts：起始位56，长度1位
                        # PTC_HVPwrSplySts：起始位57，长度1位
                        # PTC_ActGear：起始位61，长度4位
                        # PTC_Mod：起始位62，长度1位
                        # PTC_HVIntlkFlt：起始位63，长度1位
                        
                        # 解析错误代码和错误等级
                        error_level = (CanMsgBuffer[i].Data[2] >> 6) & 0x03  # 字节2，位6-7
                        error_code = CanMsgBuffer[i].Data[2] & 0x3F  # 字节2，位0-5
                        
                        # 解析实际功率（字节4和5，起始位39）
                        actual_power = (CanMsgBuffer[i].Data[5] << 8) | CanMsgBuffer[i].Data[4]
                        
                        # 解析温度（字节6，起始位55）
                        ptc_temp = CanMsgBuffer[i].Data[6] - 48  # 偏移-48
                        
                        # 解析状态位（字节7）
                        ptc_init_status = (CanMsgBuffer[i].Data[7] >> 0) & 0x01  # 位0
                        ptc_hv_power_status = (CanMsgBuffer[i].Data[7] >> 1) & 0x01  # 位1
                        ptc_act_gear = (CanMsgBuffer[i].Data[7] >> 5) & 0x0F  # 位5-8
                        ptc_mode = (CanMsgBuffer[i].Data[7] >> 9) & 0x01  # 位9（需要跨字节）
                        ptc_hv_intlk_fault = (CanMsgBuffer[i].Data[7] >> 10) & 0x01  # 位10（需要跨字节）
                        
                        # 只在值变化时更新UI
                        current_power_text = f"实际功率: {actual_power}W (传统CAN)"
                        if self.actual_power_var.get() != current_power_text:
                            self.actual_power_var.set(current_power_text)
                        current_error_level_text = f"故障等级: {error_level}"
                        if self.error_level_var.get() != current_error_level_text:
                            self.error_level_var.set(current_error_level_text)
                        current_error_code_text = f"故障码: {error_code}"
                        if self.error_code_var.get() != current_error_code_text:
                            self.error_code_var.set(current_error_code_text)
                        current_ptc_temp_text = f"PTC温度: {ptc_temp}°C"
                        if hasattr(self, 'ptc_temp_var'):
                            if self.ptc_temp_var.get() != current_ptc_temp_text:
                                self.ptc_temp_var.set(current_ptc_temp_text)
                        current_ptc_init_status_text = f"初始化状态: {ptc_init_status}"
                        if hasattr(self, 'ptc_init_status_var'):
                            if self.ptc_init_status_var.get() != current_ptc_init_status_text:
                                self.ptc_init_status_var.set(current_ptc_init_status_text)
                        current_ptc_hv_power_status_text = f"高压供电状态: {ptc_hv_power_status}"
                        if hasattr(self, 'ptc_hv_power_status_var'):
                            if self.ptc_hv_power_status_var.get() != current_ptc_hv_power_status_text:
                                self.ptc_hv_power_status_var.set(current_ptc_hv_power_status_text)
                        current_ptc_act_gear_text = f"实际档位: {ptc_act_gear}"
                        if hasattr(self, 'ptc_act_gear_var'):
                            if self.ptc_act_gear_var.get() != current_ptc_act_gear_text:
                                self.ptc_act_gear_var.set(current_ptc_act_gear_text)
                        current_ptc_mode_text = f"PTC模式: {ptc_mode}"
                        if hasattr(self, 'ptc_mode_var'):
                            if self.ptc_mode_var.get() != current_ptc_mode_text:
                                self.ptc_mode_var.set(current_ptc_mode_text)
                        current_ptc_hv_intlk_fault_text = f"高压互锁故障: {ptc_hv_intlk_fault}"
                        if hasattr(self, 'ptc_hv_intlk_fault_var'):
                            if self.ptc_hv_intlk_fault_var.get() != current_ptc_hv_intlk_fault_text:
                                self.ptc_hv_intlk_fault_var.set(current_ptc_hv_intlk_fault_text)
                    elif CanMsgBuffer[i].ID == 0x525:  # PTC_0x525的CAN ID
                        # 添加详细的接收日志，格式与图片一致
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        device_id = getattr(self, 'device_serial', 'N/A')
                        can_type = 'CAN'
                        can_id = '0x525'
                        channel = self.CAN_CHANNEL
                        data_len = CanMsgBuffer[i].DataLen
                        data = ' '.join([f"{b:02X}" for b in CanMsgBuffer[i].Data[:data_len]])
                        operation = '接收'
                        # 按照图片中的格式输出日志
                        log_message = f"[{timestamp}] {device_id} {can_type} {can_id} {channel} {data_len} {data} {operation}"
                        print(log_message)
                        self.log(log_message)
                        
                        # 根据DBC文件中的信号定义解析0x525消息
                        # PTC_PCBT：起始位23，长度8位，偏移-48
                        # PTC_Crt：起始位31，长度16位，精度0.001
                        # PTC_CrtSts：起始位41，长度2位
                        # PTC_CrtVolt：起始位55，长度16位，范围0-1000
                        
                        # 解析PCBT（字节2，起始位23）
                        ptc_pcbt = CanMsgBuffer[i].Data[2] - 48  # 偏移-48
                        
                        # 解析电流（字节3和4，起始位31）
                        actual_current = ((CanMsgBuffer[i].Data[4] << 8) | CanMsgBuffer[i].Data[3]) * 0.001
                        
                        # 解析电流状态（字节5，起始位41）
                        ptc_crt_status = (CanMsgBuffer[i].Data[5] >> 1) & 0x03  # 位1-2
                        
                        # 解析电压（字节6和7，起始位55）
                        actual_voltage = (CanMsgBuffer[i].Data[7] << 8) | CanMsgBuffer[i].Data[6]
                        
                        # 只在值变化时更新UI
                        current_voltage_text = f"实际电压: {actual_voltage}V"
                        current_current_text = f"实际电流: {actual_current:.3f}A"
                        if hasattr(self, 'actual_voltage_var'):
                            if self.actual_voltage_var.get() != current_voltage_text:
                                self.actual_voltage_var.set(current_voltage_text)
                        if hasattr(self, 'actual_current_var'):
                            if self.actual_current_var.get() != current_current_text:
                                self.actual_current_var.set(current_current_text)
        except Exception as e:
            # 只在调试模式下打印错误
            pass
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.log("开始刷新设备列表", "INFO")
        
        try:
            # 扫描设备
            DevHandles = (c_uint * 20)()
            self.log("调用USB_ScanDevice扫描设备", "DEBUG")
            ret = USB_ScanDevice(byref(DevHandles))
            self.log(f"USB_ScanDevice返回值: {ret}", "DEBUG")
            
            if ret == 0:
                self.log("未检测到USB2CAN设备", "WARNING")
                self.device_combobox['values'] = []
                self.device_var.set("未检测到设备")
                return
            
            self.log(f"检测到 {ret} 个设备", "INFO")
            
            # 遍历设备，获取序列号
            device_list = []
            self.device_info = {}
            
            for i in range(ret):
                device_handle = DevHandles[i]
                self.log(f"处理设备 {i}, 句柄: {device_handle}", "DEBUG")
                
                # 尝试打开设备
                try:
                    ret_open = USB_OpenDevice(device_handle)
                    self.log(f"USB_OpenDevice返回值: {ret_open}, 类型: {type(ret_open)}", "DEBUG")
                    
                    if bool(ret_open):
                        # 获取设备信息
                        try:
                            USB2XXXInfo = DEVICE_INFO()
                            USB2XXXFunctionString = (c_char * 256)()
                            ret_info = DEV_GetDeviceInfo(device_handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                            self.log(f"DEV_GetDeviceInfo返回值: {ret_info}, 类型: {type(ret_info)}", "DEBUG")
                            
                            if bool(ret_info):
                                # 构建序列号字符串
                                try:
                                    serial_parts = []
                                    # DEVICE_INFO结构体中的SerialNumber是c_uint*3类型，固定长度为3
                                    for j in range(3):
                                        serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                                    device_serial = ''.join(serial_parts)
                                    self.log(f"设备序列号: {device_serial}", "DEBUG")
                                    
                                    # 获取设备功能
                                    try:
                                        function_string = bytes(USB2XXXFunctionString.value).decode('ascii')
                                        self.log(f"设备功能: {function_string}", "DEBUG")
                                        
                                        # 构建设备显示名称
                                        device_name = f"设备{i}: 序列号={device_serial} (功能: {function_string})"
                                        device_list.append(device_name)
                                        self.device_info[device_name] = device_handle
                                        
                                        self.log(f"发现设备: {device_name}", "INFO")
                                    except Exception as e:
                                        self.log(f"解析设备功能错误: {str(e)}", "ERROR")
                                except Exception as e:
                                    self.log(f"构建序列号错误: {str(e)}", "ERROR")
                            else:
                                self.log(f"设备{i}获取信息失败", "WARNING")
                        except Exception as e:
                            self.log(f"获取设备信息错误: {str(e)}", "ERROR")
                        finally:
                            # 关闭设备
                            try:
                                USB_CloseDevice(device_handle)
                                self.log(f"关闭设备{i}成功", "DEBUG")
                            except Exception as e:
                                self.log(f"关闭设备{i}错误: {str(e)}", "ERROR")
                    else:
                        self.log(f"设备{i}打开失败", "WARNING")
                except Exception as e:
                    self.log(f"设备{i}操作错误: {str(e)}", "ERROR")
            
            # 更新设备下拉菜单
            self.log(f"设备列表: {device_list}", "DEBUG")
            if device_list:
                self.device_combobox['values'] = device_list
                self.device_var.set(device_list[0])
                self.log("设备列表刷新成功", "INFO")
            else:
                self.device_combobox['values'] = []
                self.device_var.set("无可用设备")
                self.log("无可用设备", "WARNING")
                
        except Exception as e:
            self.log(f"刷新设备列表错误: {str(e)}", "ERROR")
            import traceback
            self.log(f"详细错误: {traceback.format_exc()}", "ERROR")
            # 确保下拉菜单被重置
            self.device_combobox['values'] = []
            self.device_var.set("刷新失败")
    
    def connect_selected_device(self):
        """连接选择的设备"""
        selected_device = self.device_var.get()
        
        if selected_device not in self.device_info:
            self.log(f"未选择有效的设备", "ERROR")
            messagebox.showerror("错误", "请先选择一个有效的设备")
            return
        
        # 获取用户选择的CAN通道
        try:
            self.CAN_CHANNEL = int(self.can_channel_var.get())
            self.log(f"使用CAN通道: {self.CAN_CHANNEL}", "INFO")
        except Exception as e:
            self.log(f"CAN通道设置错误: {str(e)}", "ERROR")
            messagebox.showerror("错误", "CAN通道设置错误")
            return
        
        # 获取设备索引
        device_index = int(selected_device.split(':')[0].replace('设备', ''))
        
        try:
            # 重新扫描设备，获取最新的设备句柄
            DevHandles = (c_uint * 20)()
            ret = USB_ScanDevice(byref(DevHandles))
            
            if ret == 0:
                self.log("未检测到USB2CAN设备", "ERROR")
                messagebox.showerror("错误", "未检测到USB2CAN设备")
                return
            
            if device_index >= ret:
                self.log(f"设备索引超出范围: {device_index}", "ERROR")
                messagebox.showerror("错误", "设备索引超出范围")
                return
            
            # 获取设备句柄
            device_handle = DevHandles[device_index]
            self.log(f"使用设备索引 {device_index}, 句柄: {device_handle}", "DEBUG")
            
            # 关闭之前可能打开的设备
            if hasattr(self, 'dev_handle') and self.dev_handle:
                try:
                    USB_CloseDevice(self.dev_handle)
                    self.log("关闭之前的设备", "DEBUG")
                except Exception as e:
                    self.log(f"关闭之前设备错误: {str(e)}", "WARNING")
            
            # 打开选择的设备
            ret_open = USB_OpenDevice(device_handle)
            
            if not bool(ret_open):
                self.log(f"设备打开失败", "ERROR")
                messagebox.showerror("错误", "设备打开失败")
                return
            
            self.dev_handle = device_handle
            self.log(f"设备打开成功: {selected_device}", "INFO")
            
            # 获取设备信息
            USB2XXXInfo = DEVICE_INFO()
            USB2XXXFunctionString = (c_char * 256)()
            ret_info = DEV_GetDeviceInfo(self.dev_handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
            
            if bool(ret_info):
                firmware_name = bytes(USB2XXXInfo.FirmwareName).decode('ascii')
                firmware_version = f"v{(USB2XXXInfo.FirmwareVersion>>24)&0xFF}.{(USB2XXXInfo.FirmwareVersion>>16)&0xFF}.{USB2XXXInfo.FirmwareVersion&0xFFFF}"
                hardware_version = f"v{(USB2XXXInfo.HardwareVersion>>24)&0xFF}.{(USB2XXXInfo.HardwareVersion>>16)&0xFF}.{USB2XXXInfo.HardwareVersion&0xFFFF}"
                build_date = bytes(USB2XXXInfo.BuildDate).decode('ascii')
                function_string = bytes(USB2XXXFunctionString.value).decode('ascii')
                
                self.log(f"固件名称: {firmware_name}", "INFO")
                self.log(f"固件版本: {firmware_version}", "INFO")
                self.log(f"硬件版本: {hardware_version}", "INFO")
                self.log(f"构建日期: {build_date}", "INFO")
                self.log(f"功能字符串: {function_string}", "INFO")
            
            # 初始化CAN
            if not self.init_can():
                self.log("CAN初始化失败，停止连接过程", "ERROR")
                messagebox.showerror("错误", "CAN初始化失败，请检查设备连接和通道设置")
                return
            
            # 解析DBC文件（可选）
            self.log("=== 解析DBC文件 ===", "INFO")
            
            # 尝试多个可能的DBC文件路径
            dbc_file_paths = [
                "d:\\老化CAN通讯\\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.dbc",  # 无空格
                "d:\\老化CAN通讯\\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc",  # 有空格
                "BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.dbc",  # 相对路径
                "BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc"  # 相对路径有空格
            ]
            
            dbc_file_path = None
            for path in dbc_file_paths:
                if os.path.exists(path):
                    dbc_file_path = path
                    self.log(f"找到DBC文件: {path}", "INFO")
                    break
            
            if dbc_file_path:
                self.log(f"使用DBC文件路径: {dbc_file_path}", "INFO")
                
                self.log("=== 尝试解析DBC文件 ===", "INFO")
                try:
                    # 尝试使用不同的编码方式
                    encodings = ['gbk', 'utf-8', 'ascii']
                    self.dbchandle = 0
                    
                    for encoding in encodings:
                        try:
                            self.log(f"尝试使用编码: {encoding}", "DEBUG")
                            result = DBC_ParserFile(self.dev_handle, dbc_file_path.encode(encoding))
                            self.log(f"DBC_ParserFile返回值 ({encoding}): {result}", "DEBUG")
                            
                            if result != 0:
                                self.dbchandle = result
                                break
                        except Exception as e:
                            self.log(f"编码 {encoding} 错误: {str(e)}", "WARNING")
                    
                    # 检查是否解析成功
                    if self.dbchandle == 0:
                        self.log("DBC文件解析失败", "WARNING")
                        # 尝试使用默认的DBC文件路径
                        self.log("尝试使用默认DBC文件路径...", "INFO")
                        try:
                            default_dbc = "demo.dbc"
                            if os.path.exists(default_dbc):
                                self.log(f"使用默认DBC文件: {default_dbc}", "INFO")
                                self.dbchandle = DBC_ParserFile(self.dev_handle, default_dbc.encode('gbk'))
                                self.log(f"默认DBC解析返回值: {self.dbchandle}", "DEBUG")
                                if self.dbchandle == 0:
                                    self.log("默认DBC解析也失败了", "WARNING")
                            else:
                                self.log("默认DBC文件不存在", "WARNING")
                        except Exception as e:
                            self.log(f"默认DBC解析错误: {str(e)}", "ERROR")
                    else:
                        # 只有当解析成功时才执行以下代码
                        self.log("DBC文件解析成功", "INFO")
                        
                        # 验证DBC解析结果
                        self.log("=== 验证DBC解析结果 ===", "INFO")
                        try:
                            DBCMsgNum = DBC_GetMsgQuantity(c_uint64(self.dbchandle))
                            self.log(f"DBC文件中包含 {DBCMsgNum} 条报文", "INFO")
                        except Exception as e:
                            self.log(f"验证DBC解析结果错误: {str(e)}", "ERROR")
                            # 即使验证失败，也继续运行
                            pass
                except Exception as e:
                    self.log(f"DBC解析错误: {str(e)}", "ERROR")
                    # 即使DBC解析失败，也继续运行
            else:
                self.log("未找到DBC文件，跳过DBC解析", "WARNING")
            
            # 记录连接完成
            if self.dbchandle == 0:
                self.status_var.set("设备就绪（DBC解析失败）")
            else:
                self.status_var.set("设备就绪")
            # 设置设备连接状态为已连接
            self.device_connected = True
            self.log("设备连接完成，状态: 就绪", "INFO")
            
        except Exception as e:
            self.log(f"连接设备错误: {str(e)}", "ERROR")
            import traceback
            self.log(f"详细错误: {traceback.format_exc()}", "ERROR")
            messagebox.showerror("错误", f"连接设备失败: {str(e)}")
    
    def init_can(self):
        """初始化CAN，自动匹配CAN或CANFD"""
        self.log("开始初始化CAN通道", "INFO")
        self.log(f"当前CAN通道: {self.CAN_CHANNEL}", "INFO")
        self.log(f"当前CAN ID: {hex(self.CAN_ID)}", "INFO")
        
        # 自动匹配CAN或CANFD
        can_initialized = False
        
        # 1. 首先尝试传统CAN初始化
        self.log("尝试使用传统CAN初始化", "INFO")
        try:
            # 创建CAN初始化配置结构体
            CANConfig = CAN_INIT_CONFIG()
            
            # 设置CAN配置参数
            # 根据USB2CAN_Test.py中的配置参数
            # 波特率：500Kbps
            # 波特率 = 100M/(BRP*(SJW+BS1+BS2))
            
            CANConfig.CAN_Mode = 0      # 1-自发自收模式，0-正常模式
            CANConfig.CAN_ABOM = 0
            CANConfig.CAN_NART = 1
            CANConfig.CAN_RFLM = 0
            CANConfig.CAN_TXFP = 1
            # 配置波特率,波特率 = 100M/(BRP*(SJW+BS1+BS2))
            CANConfig.CAN_BRP_CFG3 = 25
            CANConfig.CAN_BS1_CFG1 = 6
            CANConfig.CAN_BS2_CFG2 = 1
            CANConfig.CAN_SJW = 1
            
            ret = CAN_Init(self.dev_handle, self.CAN_CHANNEL, byref(CANConfig))
            
            if ret == 0:
                self.log(f"传统CAN通道{self.CAN_CHANNEL}初始化成功", "INFO")
                self.use_canfd = False
                can_initialized = True
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
            else:
                self.log(f"传统CAN初始化失败，返回值: {ret}", "ERROR")
        except Exception as e:
            self.log(f"传统CAN初始化错误: {str(e)}", "ERROR")
        
        # 2. 如果传统CAN失败，尝试CANFD初始化
        if not can_initialized and 'CANFD_Init' in globals() and 'CANFD_SendMsg' in globals() and 'CANFD_GetMsg' in globals():
            self.log("尝试使用CANFD初始化（设备支持CANFD功能）", "INFO")
            try:
                # 创建CANFD初始化配置结构体
                CANFDConfig = CANFD_INIT_CONFIG()
                
                # 设置CANFD配置参数
                CANFDConfig.Mode = 0  # 正常模式
                CANFDConfig.ISOCRCEnable = 1  # 使能ISO CRC
                CANFDConfig.RetrySend = 1  # 无限制重发
                CANFDConfig.ResEnable = 1  # 接入内部120欧终端电阻
                
                # 配置标称波特率为500Kbps (Nominal Bit Time)
                CANFDConfig.NBT_BRP = 10
                CANFDConfig.NBT_SEG1 = 6
                CANFDConfig.NBT_SEG2 = 1
                CANFDConfig.NBT_SJW = 1
                
                # 配置数据相位波特率也为500Kbps
                CANFDConfig.DBT_BRP = 10
                CANFDConfig.DBT_SEG1 = 6
                CANFDConfig.DBT_SEG2 = 1
                CANFDConfig.DBT_SJW = 1
                
                ret = CANFD_Init(self.dev_handle, self.CAN_CHANNEL, byref(CANFDConfig))
                
                if ret == CANFD_SUCCESS:
                    self.log(f"CANFD通道{self.CAN_CHANNEL}初始化成功", "INFO")
                    
                    # 配置CANFD过滤器 (必须配置，否则无法接收数据)
                    CANFDFilter = CANFD_FILTER_CONFIG()
                    CANFDFilter.Enable = 1
                    CANFDFilter.Index = 0
                    CANFDFilter.ID_Accept = 0
                    CANFDFilter.ID_Mask = 0 # 接收所有ID
                    
                    ret_filter = CANFD_SetFilter(self.dev_handle, self.CAN_CHANNEL, byref(CANFDFilter), 1)
                    if ret_filter == CANFD_SUCCESS:
                        self.log("CANFD过滤器配置成功 (接收所有ID)", "INFO")
                        
                        # 启动CANFD接收
                        ret_start = CANFD_StartGetMsg(self.dev_handle, self.CAN_CHANNEL)
                        if ret_start == CANFD_SUCCESS:
                             self.log("CANFD接收已启动", "INFO")
                        else:
                             self.log(f"CANFD接收启动失败: {ret_start}", "ERROR")
                    else:
                        self.log(f"CANFD过滤器配置失败: {ret_filter}", "WARNING")

                    self.use_canfd = True
                    can_initialized = True
                    self.can_initialized = True
                    self.log("设备已配置为CANFD模式", "INFO")
                else:
                    self.log(f"CANFD初始化失败，返回值: {ret}", "ERROR")
            except Exception as e:
                self.log(f"CANFD初始化错误: {str(e)}", "ERROR")
        
        # 3. 如果仍然失败，尝试使用替代配置
        if not can_initialized:
            self.log("传统CAN和CANFD初始化都失败，尝试使用替代配置", "INFO")
            try:
                # 创建CAN初始化配置结构体
                CANConfig = CAN_INIT_CONFIG()
                
                # 使用替代的500Kbps配置
                self.log("尝试使用替代CAN配置参数（500Kbps）", "INFO")
                CANConfig.CAN_Mode = 0      # 1-自发自收模式，0-正常模式
                CANConfig.CAN_ABOM = 0
                CANConfig.CAN_NART = 1
                CANConfig.CAN_RFLM = 0
                CANConfig.CAN_TXFP = 1
                # 配置波特率,波特率 = 100M/(BRP*(SJW+BS1+BS2))
                CANConfig.CAN_BRP_CFG3 = 25
                CANConfig.CAN_BS1_CFG1 = 6
                CANConfig.CAN_BS2_CFG2 = 1
                CANConfig.CAN_SJW = 1
                
                # 初始化CAN通道
                ret = CAN_Init(self.dev_handle, self.CAN_CHANNEL, byref(CANConfig))
                
                if ret == 0:
                    self.log(f"使用替代配置后CAN通道{self.CAN_CHANNEL}初始化成功", "INFO")
                    self.use_canfd = False
                    can_initialized = True
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
                else:
                    self.log(f"使用替代配置后CAN初始化失败，返回值: {ret}", "ERROR")
                    
                    # 尝试切换到另一个CAN通道
                    if self.CAN_CHANNEL == 0:
                        self.CAN_CHANNEL = 1
                        self.log("尝试切换到CAN通道1", "INFO")
                    else:
                        self.CAN_CHANNEL = 0
                        self.log("尝试切换到CAN通道0", "INFO")
                    
                    # 重新初始化
                    ret = CAN_Init(self.dev_handle, self.CAN_CHANNEL, byref(CANConfig))
                    if ret == 0:
                        self.log(f"切换通道后CAN通道{self.CAN_CHANNEL}初始化成功", "INFO")
                        self.use_canfd = False
                        can_initialized = True
                        self.can_initialized = True
                        self.log("设备已配置为传统CAN模式", "INFO")
                    else:
                        self.log(f"切换通道后CAN初始化仍然失败，返回值: {ret}", "ERROR")
                        # 恢复原来的通道
                        if self.CAN_CHANNEL == 0:
                            self.CAN_CHANNEL = 1
                        else:
                            self.CAN_CHANNEL = 0
                        self.log(f"恢复到原来的CAN通道: {self.CAN_CHANNEL}", "INFO")
                            
            except Exception as e:
                self.log(f"尝试替代配置时发生错误: {str(e)}", "ERROR")
        
        # 4. 最终结果
        if can_initialized:
            self.device_connected = True
            self.status_var.set("设备就绪")
            self.log("设备初始化完成，状态: 就绪", "INFO")
            return True
        else:
            self.status_var.set("CAN初始化失败")
            self.log("CAN初始化失败", "ERROR")
            return False
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'dev_handle') and self.dev_handle:
            try:
                USB_CloseDevice(self.dev_handle)
            except:
                pass

if __name__ == '__main__':
    try:
        print("=== 开始运行PTC_Power_Sequence.py ===")
        root = tk.Tk()
        print("=== 创建tkinter窗口成功 ===")
        app = PTCPowerSequenceApp(root)
        print("=== 创建PTC_Power_SequenceApp实例成功 ===")
        
        # 处理窗口关闭
        def on_closing():
            if app.running:
                app.stop_sequence()
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        print("=== 进入主循环 ===")
        root.mainloop()
    except Exception as e:
        print(f"=== 运行错误: {str(e)} ===")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
