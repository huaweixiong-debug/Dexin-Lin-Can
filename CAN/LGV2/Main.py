import tkinter as tk
import threading
import time
import sys
from test_monitor_ui import TestMonitorUI
from hv_test_runner import HVTestRunner
from loading_view import LoadingWindow

from database import init_db
from plc_controller import PLCController
from logger import logger
from scanner_new import scanner_manager
from calibration_manager import CalibrationManager, CalibrationStatus
from power_communication_manager import power_comm_manager
from label_printer import LabelPrinter
from can_manager import init_can_manager, get_can_manager
from fault_handler import init_fault_handler, get_fault_handler

# Import OPC config parser from S7-200.py using importlib
import importlib.util
import os

# Dynamically import S7-200.py
script_dir = os.path.dirname(os.path.abspath(__file__))
s7_200_path = os.path.join(script_dir, "S7-200.py")

spec = importlib.util.spec_from_file_location("S7_200", s7_200_path)
S7_200 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S7_200)

# Now we can use S7_200.parse_opc_config

class MainApp:
    def __init__(self, root, loader=None):
        self.root = root
        
        # Helper to update loader
        def update_loader(val, msg):
            if loader:
                loader.update_progress(val, msg)

        update_loader(5, "Initializing System...")
        logger.info("Starting LGV2 Test System...")
        
        # Initialize Database
        update_loader(10, "Initializing Database...")
        try:
            init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
        
        update_loader(20, "Initializing User Interface...")
        self.ui = TestMonitorUI(root)
        logger.info("UI initialized successfully")
        
        # Connect UI callbacks
        self.ui.set_start_callback(self.on_start_test)
        self.ui.set_stop_callback(self.on_stop_test)
        
        # Connect config save callback
        self.ui.set_config_save_callback(self.update_wind_speed)
        
        self.plc_controller = None
        

        
        # Store active runners: station_idx -> HVTestRunner instance
        self.runners = {}
        
        # Store scan results: station_idx -> scan_result
        self.scan_results = {}
        
        # Store station status: station_idx -> status
        self.station_status = {}  # 'idle', 'scanning', 'waiting_start', 'testing', 'completed'
        
        # Initialize all stations to waiting_start state
        for i in range(1, 11):
            self.station_status[i] = 'waiting_start'

        update_loader(30, "Initializing Calibration Manager...")
        # Initialize Calibration Manager with the same config file path as UI
        self.calibration_manager = CalibrationManager(config_file=self.ui.config_file)
        
        # 读取扫码和标签设置
        self.scan_start = self.ui.config.get("scan_start", False)
        self.print_label_qr = self.ui.config.get("print_label_qr", True)
        logger.info(f"Scan start setting: {self.scan_start}")
        logger.info(f"Print label QR setting: {self.print_label_qr}")
        
        # 初始化标签打印机（创建独立窗口）
        self.label_printer_window = tk.Toplevel(self.root)
        self.label_printer_window.withdraw()  # 隐藏标签打印机窗口
        self.label_printer = LabelPrinter(self.label_printer_window)
        
        # 用于跟踪需要打印标签的工位
        self.need_label_print = {
        }
        
        # 用于存储标签二维码内容
        self.label_qr_contents = {
        }
        
        # 标签打印队列和相关变量
        self.print_queue = []
        self.print_queue_lock = threading.Lock()
        self.print_queue_running = False
        self.print_queue_thread = None
        
        # 启动标签打印队列线程
        self.start_print_queue_thread()
        
        # 如果不扫码启动，启动线程持续发送扫码合格信号
        self.no_scan_thread = None
        self.no_scan_running = False
        if not self.scan_start:
            self.start_no_scan_thread()

        update_loader(40, "Connecting to PLC Controller...")
        # Initialize PLC Controller
        try:
            # 首先解析OPCOPC.xml文件获取PLC配置
            logger.info("Parsing OPC configuration from OPCOPC.xml...")
            plc_config = S7_200.parse_opc_config()
            
            # 从解析结果中提取PLC IP地址
            plc_ips = list(plc_config.keys())
            logger.info(f"Found PLC IPs in OPCOPC.xml: {plc_ips}")
            
            # 初始化PLC控制器
            self.plc_controller = PLCController()
            
            # 根据解析结果设置PLC IP地址
            if len(plc_ips) >= 1:
                plc1_ip = plc_ips[0]
            else:
                # 如果解析失败，使用配置文件中的值或默认值
                plc_settings = self.ui.config.get("plc_settings", {})
                plc1_ip = plc_settings.get("plc1_ip", "192.168.10.180")
            
            if len(plc_ips) >= 2:
                plc2_ip = plc_ips[1]
            else:
                # 如果解析失败，使用配置文件中的值或默认值
                plc_settings = self.ui.config.get("plc_settings", {})
                plc2_ip = plc_settings.get("plc2_ip", "192.168.10.181")
            
            logger.info(f"Updating PLC IP addresses: PLC1={plc1_ip}, PLC2={plc2_ip}")
            self.plc_controller.update_plc_ips(plc1_ip, plc2_ip)
            
            self.plc_controller.set_callbacks(
                self.thread_safe_start_test, 
                self.thread_safe_stop_test,
                self.on_emergency_stop,
                self.on_reset
            )
            self.plc_controller.set_log_callback(self.thread_safe_log_message)
            self.plc_controller.start()
            logger.info("PLC controller started successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PLC controller: {e}")
            import traceback
            traceback.print_exc()
            self.plc_controller = None

        update_loader(60, "Initializing Scanners...")
        # Initialize scanners from config
        self.init_scanners()
        
        update_loader(70, "Initializing CAN Manager...")
        # Initialize CAN Manager
        try:
            self.can_manager = init_can_manager()
            logger.info("CAN manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CAN manager: {e}")
            self.can_manager = None
        
        update_loader(80, "Initializing Fault Handler...")
        # Initialize Fault Handler
        try:
            self.fault_handler = init_fault_handler()
            # 注册故障处理回调
            self.fault_handler.register_callback("stop_test", self.on_fault_stop_test)
            logger.info("Fault handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize fault handler: {e}")
            self.fault_handler = None
        
        update_loader(90, "Starting Background Services...")
        # Setup input logging and heartbeat
        self.setup_input_logging()
        self.start_heartbeat()
        
        # Start PLC status monitoring
        self.start_plc_status_monitor()
        
        # Start wind speed control
        self.start_wind_speed_control()
        
        update_loader(100, "Ready!")
        logger.info("LGV2 Test System started successfully")
    
    def init_scanners(self):
        """从配置文件中初始化扫码枪"""
        try:
            import json
            import os
            
            config_file = "config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                hardware_settings = config.get("hardware_settings", {})
                for station_key, settings in hardware_settings.items():
                    # 解析工位索引，如"工位1" -> 1
                    try:
                        station_idx = int(station_key.replace("工位", ""))
                    except:
                        continue
                    
                    scanner_ip = settings.get("scanner_ip", "")
                    if scanner_ip:
                        # 添加扫码枪
                        scanner_manager.add_scanner(station_idx, scanner_ip)
                        # 初始化状态
                        self.station_status[station_idx] = 'waiting_start'
                        self.scan_results[station_idx] = ""
                        logger.info(f"Initialized scanner for station {station_idx}: {scanner_ip}")
            
            # 无论scan_start设置如何，都启动自动扫码功能
            # 因为即使在scan_start为False的情况下，当需要打印标签时，也需要接收扫码结果
            scanner_manager.start_auto_scan_all(self.on_scan_result)
            logger.info("Auto scan started for all scanners")
            
        except Exception as e:
            logger.error(f"Failed to initialize scanners: {e}")

    def init_all_can_devices(self):
        """初始化所有工位的CAN设备"""
        if not self.can_manager:
            return
            
        logger.info("Starting auto-initialization of all CAN devices...")
        
        def _init_task():
            try:
                import re
                hardware_settings = self.ui.config.get("hardware_settings", {})
                
                for station_key, settings in hardware_settings.items():
                    try:
                        station_idx = int(station_key.replace("工位", ""))
                    except:
                        continue
                        
                    can_device_str = settings.get("can_device", "") or settings.get("can_sn", "")
                    if not can_device_str:
                        continue
                        
                    # Parse SN
                    sn = None
                    if "序列号=" in can_device_str:
                        try:
                            sn = can_device_str.split("序列号=")[1].split(" ")[0].strip()
                        except: pass
                    
                    if not sn:
                        # Try regex
                        matches = re.findall(r'[0-9A-Fa-f]{16,}', can_device_str)
                        if matches:
                            sn = matches[0].upper()
                            
                    if not sn:
                        logger.warning(f"Could not parse SN for Station {station_idx}: {can_device_str}")
                        continue
                        
                    can_channel = 0
                    try:
                        can_channel = int(settings.get("can_channel", 0))
                    except: pass
                    
                    logger.info(f"Auto-initializing CAN for Station {station_idx}: SN={sn} Ch={can_channel}")
                    # 使用 initialize_can，它会自动处理连接和初始化
                    if self.can_manager.initialize_can(sn, can_channel):
                        logger.info(f"Station {station_idx} CAN initialized successfully.")
                    else:
                        logger.error(f"Station {station_idx} CAN initialization failed.")
                        
            except Exception as e:
                logger.error(f"Error during CAN auto-initialization: {e}")
                import traceback
                traceback.print_exc()

        # 在后台线程中运行，避免阻塞启动
        threading.Thread(target=_init_task, daemon=True).start()

    
    def on_scan_result(self, station_idx, scan_result):
        """扫码结果回调函数"""
        logger.info(f"=== Scan result for station {station_idx}: {scan_result} ===")
        
        # 检查是否是标签打印后的扫码确认
        if station_idx in self.need_label_print:
            label_info = self.need_label_print[station_idx]
            expected_scan = label_info.get('scan_result', '')
            logger.info(f"Station {station_idx} is in need_label_print list, expected scan: {expected_scan}")
            
            # 验证扫码结果是否匹配
            if scan_result == expected_scan:
                logger.info(f"=== Label scan confirmed for station {station_idx} ===")
                self.thread_safe_log_message(f"工位{station_idx}标签扫码确认成功")
                
                # 发送合格信号给PLC
                if self.plc_controller:
                    logger.info(f"Sending PASS signal to PLC for station {station_idx} after label confirmation")
                    self.plc_controller.write_status(station_idx, 'PASS', True)
                    logger.info(f"Sent PASS signal to PLC for station {station_idx} after label confirmation")
                
                # 更新UI
                self.thread_safe_update_ui(station_idx, 0, "扫码确认完成", "#90EE90")  # 绿色
                
                # 清除标签打印标记
                logger.info(f"Clearing label print mark for station {station_idx}")
                del self.need_label_print[station_idx]
                
                # 更新状态
                logger.info(f"Updating station {station_idx} status to waiting_start")
                self.station_status[station_idx] = 'waiting_start'
                
                # 重置扫码结果
                self.scan_results[station_idx] = ""
                
                # 更新其他方框为Waiting...
                self.reset_test_ui(station_idx)
                
                logger.info(f"=== Label scan confirmation process completed for station {station_idx} ===")
                return
            else:
                logger.warning(f"=== Label scan mismatch for station {station_idx}: expected={expected_scan}, got={scan_result} ===")
                self.thread_safe_log_message(f"工位{station_idx}标签扫码不匹配，请重新扫码")
                self.thread_safe_update_ui(station_idx, 0, "扫码不匹配", "#FFCCCB")  # 红色
                return
        
        # 正常扫码流程
        logger.info(f"Processing normal scan for station {station_idx}")
        # 更新扫码结果
        self.scan_results[station_idx] = scan_result
        
        # 更新UI
        self.thread_safe_update_ui(station_idx, 0, scan_result, "#90EE90")  # 绿色
        
        # 更新状态
        self.station_status[station_idx] = 'waiting_start'
        
        # 发送扫码完成信号给PLC
        if self.plc_controller and self.scan_start:
            logger.info(f"Sent SCAN_OK signal to PLC for station {station_idx} (scan_start is True)")
            self.plc_controller.write_status(station_idx, 'SCAN_OK', True)
        
        # 更新其他方框为Waiting...
        self.reset_test_ui(station_idx)
        
        # 记录日志
        self.thread_safe_log_message(f"工位{station_idx}扫码完成: {scan_result}")
        logger.info(f"=== Normal scan process completed for station {station_idx} ===")
    
    def reset_test_ui(self, station_idx):
        """重置测试UI，将所有测试项设置为Waiting..."""
        # 重置所有测试项（1-31），不重置第0行（扫码内容/状态）
        # 包括实时数据、各阶段数据、监控项等
        for item_idx in range(1, 32):
            self.thread_safe_update_ui(station_idx, item_idx, "Waiting...", "white")

    def setup_input_logging(self):
        self.root.bind_all("<Button-1>", self.on_mouse_click)
        self.root.bind_all("<Key>", self.on_key_press)

    def on_mouse_click(self, event):
        # Optional: Log to UI or just console? User asked for "log".
        # To avoid spamming the UI log too much, maybe we format it nicely or filter.
        # self.ui.log_message(f"Mouse Click: {event.x}, {event.y}")
        pass

    def on_key_press(self, event):
        # self.ui.log_message(f"Key Press: {event.keysym}")
        pass

    def start_heartbeat(self):
        self.update_heartbeat()

    def update_heartbeat(self):
        # 获取电源通信统计
        try:
            stats = power_comm_manager.get_stats()
            running_stations = [idx for idx, r in self.runners.items() if r.running]
            status_msg = f"系统状态: 运行工位={running_stations}, 电源通信次数={stats['total_communications']}"
            print(status_msg)
        except Exception as e:
            print(f"Heartbeat error: {e}")
        
        # 每10秒更新一次UI日志中的电源通信状态
        current_time = time.time()
        if not hasattr(self, '_last_comm_stats_time'):
            self._last_comm_stats_time = 0
        
        if current_time - self._last_comm_stats_time >= 10:
            self.display_power_comm_stats()
            self._last_comm_stats_time = current_time
        
        self.root.after(5000, self.update_heartbeat)

    def on_start_test(self, station_idx):
        logger.info(f"=== on_start_test called for station {station_idx} ===")
        if station_idx in self.runners and self.runners[station_idx].running:
            logger.warning(f"Station {station_idx} is already running.")
            return
        
        # 检查状态
        if self.station_status.get(station_idx) != 'waiting_start':
            logger.warning(f"Station {station_idx} is not in waiting_start state.")
            self.thread_safe_log_message(f"工位{station_idx}状态不正确，无法启动测试")
            return

        # 清除之前的数据，重置为Waiting状态
        self.reset_test_ui(station_idx)

        logger.info(f"Starting test for Station {station_idx}...")
        
        # 1. Get Configuration
        station_config = self.ui.get_station_config(station_idx)
        if not station_config:
            logger.error(f"No hardware config for Station {station_idx}")
            self.ui.update_cell(station_idx, 0, "No Config", "#FFCCCB")
            return

        product_config = self.ui.get_current_product_config()
        if not product_config:
            logger.error("No product selected")
            self.ui.update_cell(station_idx, 0, "No Product", "#FFCCCB")
            return
            
        # Extract configuration
        # NOTE: In config.json, "times" keys hold Power Values (Watts) and "powers" keys hold Duration Values (Seconds)
        # This is due to historical variable naming in test_monitor_ui.py
        power_settings = product_config.get("times", {})    # Watts
        duration_settings = product_config.get("powers", {}) # Seconds
        product_name = product_config.get("name", "Unknown")
        
        # 使用扫码结果，如果没有则使用默认值
        scan_result = self.scan_results.get(station_idx, "") or "PLC_START"

        # 2. Create Runner
        # 获取二维码内容（如果有）
        label_qr = self.label_qr_contents.get(station_idx, None)
        
        runner = HVTestRunner(
            station_idx=station_idx,
            station_config=station_config,
            duration_settings=duration_settings,
            power_settings=power_settings,
            ui_callback=self.thread_safe_update_ui,
            log_callback=self.thread_safe_log_message, # Pass log callback
            product_name=product_name,
            scan_result=scan_result,
            plc_controller=self.plc_controller,
            test_complete_callback=self.on_test_complete,
            print_label_qr=self.print_label_qr,
            label_qr=label_qr,
            can_manager=self.can_manager,
            fault_handler=self.fault_handler
        )
        self.runners[station_idx] = runner
        
        # 更新状态
        self.station_status[station_idx] = 'testing'
        
        # 3. Start Thread
        t = threading.Thread(target=runner.run, daemon=True)
        t.start()
        logger.info(f"Test thread started for Station {station_idx}")
        self.thread_safe_log_message(f"工位{station_idx}测试开始")

    def on_stop_test(self, station_idx):
        if station_idx in self.runners:
            logger.info(f"Stopping Station {station_idx}...")
            self.runners[station_idx].stop()
            # 更新状态
            self.station_status[station_idx] = 'waiting_start'
            # 重置扫码结果
            self.scan_results[station_idx] = ""
            # 重置UI
            self.thread_safe_update_ui(station_idx, 0, "准备就绪", "white")
            self.reset_test_ui(station_idx)
            # 发送停止信号给PLC
            if self.plc_controller:
                if self.scan_start:
                    self.plc_controller.write_status(station_idx, 'SCAN_OK', False)
                self.plc_controller.write_status(station_idx, 'PASS', False)
                self.plc_controller.write_status(station_idx, 'FAIL', False)
            # 重置标签打印标记
            if station_idx in self.need_label_print:
                del self.need_label_print[station_idx]
            self.thread_safe_log_message(f"工位{station_idx}测试停止")
            # Don't remove immediately, let the thread finish and cleanup
        else:
            logger.warning(f"Station {station_idx} is not running.")
            self.thread_safe_log_message(f"工位{station_idx}未运行")
    
    def on_emergency_stop(self, station_idx):
        """紧急停止处理"""
        logger.info(f"Emergency stop for station {station_idx}")
        self.thread_safe_log_message(f"工位{station_idx}紧急停止")
        
        # 停止测试
        if station_idx in self.runners:
            self.runners[station_idx].stop()
        
        # 更新状态
        self.station_status[station_idx] = 'waiting_start'
        
        # 重置UI
        self.thread_safe_update_ui(station_idx, 0, "急停", "#FF0000")  # 红色
        for item_idx in list(range(1, 5)) + list(range(7, 31)):
            self.thread_safe_update_ui(station_idx, item_idx, "急停", "#FF0000")
        
        # 发送急停信号给PLC
        if self.plc_controller:
            if self.scan_start:
                self.plc_controller.write_status(station_idx, 'SCAN_OK', False)
            self.plc_controller.write_status(station_idx, 'PASS', False)
            self.plc_controller.write_status(station_idx, 'FAIL', False)
        
        # 重置标签打印标记
        if station_idx in self.need_label_print:
            del self.need_label_print[station_idx]
    
    def on_reset(self, station_idx):
        """复位处理"""
        logger.info(f"Reset for station {station_idx}")
        self.thread_safe_log_message(f"工位{station_idx}复位")
        
        # 停止测试
        if station_idx in self.runners:
            self.runners[station_idx].stop()
        
        # 重置状态
        self.station_status[station_idx] = 'waiting_start'
        self.scan_results[station_idx] = ""
        
        # 重置UI
        self.thread_safe_update_ui(station_idx, 0, "准备就绪", "white")
        self.reset_test_ui(station_idx)
        
        # 发送复位信号给PLC
        if self.plc_controller:
            if self.scan_start:
                self.plc_controller.write_status(station_idx, 'SCAN_OK', False)
            self.plc_controller.write_status(station_idx, 'PASS', False)
            self.plc_controller.write_status(station_idx, 'FAIL', False)
        
        # 重置标签打印标记
        if station_idx in self.need_label_print:
            del self.need_label_print[station_idx]

    def thread_safe_start_test(self, station_idx):
        # Called from PLC thread
        self.root.after(0, lambda: self.on_start_test(station_idx))

    def thread_safe_stop_test(self, station_idx):
        # Called from PLC thread
        self.root.after(0, lambda: self.on_stop_test(station_idx))

    def start_plc_status_monitor(self):
        """启动PLC状态监控"""
        def update_plc_status():
            if self.plc_controller:
                try:
                    # 获取PLC连接状态
                    plc1_status = "已连接" if self.plc_controller.connected1 else "未连接"
                    plc2_status = "已连接" if self.plc_controller.connected2 else "未连接"
                    
                    # 更新PLC状态显示
                    status_msg = f"PLC状态: PLC1({self.plc_controller.plc1_ip}) {plc1_status}, PLC2({self.plc_controller.plc2_ip}) {plc2_status}"
                    
                    # 记录到系统日志
                    self.thread_safe_log_message(status_msg)
                    
                    # 可以在这里添加更多的PLC状态信息，如：
                    # - 每个工位的信号状态
                    # - 通讯延迟
                    # - 错误计数等
                    
                except Exception as e:
                    logger.error(f"Error updating PLC status: {e}")
            
            # 每5秒更新一次状态
            self.root.after(5000, update_plc_status)
        
        # 启动状态监控
        self.root.after(1000, update_plc_status)  # 1秒后开始，然后每5秒更新一次

    def thread_safe_update_ui(self, station_idx, item_idx, text, color):
        # Schedule update on main thread
        self.root.after(0, lambda: self.ui.update_cell(station_idx, item_idx, text, color))

    def thread_safe_log_message(self, message):
        # Schedule log update on main thread
        self.root.after(0, lambda: self.ui.log_message(message))

    def update_wind_speed(self):
        """手动更新风速设置到PLC"""
        # 在单独的线程中执行，避免阻塞UI线程
        threading.Thread(target=self._update_wind_speed_internal, daemon=True).start()
        
        # 更新扫码启动设置
        new_scan_start = self.ui.config.get("scan_start", False)
        if new_scan_start != self.scan_start:
            logger.info(f"Scan start setting changed from {self.scan_start} to {new_scan_start}")
            self.scan_start = new_scan_start
            
            # 根据新的设置启动或停止no_scan_thread
            if self.scan_start:
                # 如果启用了扫码启动，停止no_scan_thread
                if self.no_scan_running:
                    logger.info("Stopping no_scan_thread as scan_start is now True")
                    self.no_scan_running = False
                    if self.no_scan_thread:
                        self.no_scan_thread.join(timeout=2)
                    self.no_scan_thread = None
                    logger.info(f"no_scan_thread stopped successfully, scan_start={self.scan_start}")
            else:
                # 如果禁用了扫码启动，启动no_scan_thread
                if not self.no_scan_running:
                    logger.info("Starting no_scan_thread as scan_start is now False")
                    self.start_no_scan_thread()
                    logger.info(f"no_scan_thread started successfully, scan_start={self.scan_start}")
    
    def _update_wind_speed_internal(self):
        """在后台线程中执行风速更新"""
        if self.plc_controller:
            try:
                # 从配置读取风速设置
                wind_speed_settings = self.ui.config.get("wind_speed_settings", {})
                
                # 从配置读取PLC IP地址并更新
                plc_settings = self.ui.config.get("plc_settings", {})
                plc1_ip = plc_settings.get("plc1_ip", "192.168.10.221")
                plc2_ip = plc_settings.get("plc2_ip", "192.168.10.222")
                self.plc_controller.update_plc_ips(plc1_ip, plc2_ip)
                
                # 读取PLC1风速设置
                plc1_wind_speed = wind_speed_settings.get("plc1_wind_speed", "")
                if plc1_wind_speed:
                    try:
                        # 写入PLC1风速（1-5工位）
                        self.plc_controller.write_wind_speed(1, plc1_wind_speed)
                    except ValueError as e:
                        logger.error(f"Invalid PLC1 wind speed value: {plc1_wind_speed} - {e}")
                
                # 读取PLC2风速设置
                plc2_wind_speed = wind_speed_settings.get("plc2_wind_speed", "")
                if plc2_wind_speed:
                    try:
                        # 写入PLC2风速（6-10工位）
                        self.plc_controller.write_wind_speed(2, plc2_wind_speed)
                    except ValueError as e:
                        logger.error(f"Invalid PLC2 wind speed value: {plc2_wind_speed} - {e}")
                
            except Exception as e:
                logger.error(f"Error updating wind speed: {e}")

    def on_start_calibration(self, station_idx):
        """开始校准"""
        logger.info(f"Starting calibration for Station {station_idx}...")
        
        # 检查工位配置
        station_config = self.ui.get_station_config(station_idx)
        if not station_config:
            logger.warning(f"No hardware config for Station {station_idx}")
            self.thread_safe_log_message(f"工位{station_idx}无硬件配置，无法校准")
            return
        
        # 启动校准
        success = self.calibration_manager.start_calibration(
            station_idx=station_idx,
            station_config=station_config,
            ui_callback=self.thread_safe_update_calibration_status,
            log_callback=self.thread_safe_log_message,
            plc_controller=self.plc_controller,
            current_callback=self.thread_safe_update_calibration_current
        )
        
        if success:
            self.thread_safe_log_message(f"工位{station_idx}校准开始")
        else:
            self.thread_safe_log_message(f"工位{station_idx}校准启动失败")

    def on_stop_calibration(self, station_idx):
        """停止校准"""
        logger.info(f"Stopping calibration for Station {station_idx}...")
        
        success = self.calibration_manager.stop_calibration(station_idx)
        if success:
            self.thread_safe_log_message(f"工位{station_idx}校准停止")

    def thread_safe_update_calibration_status(self, station_idx, status, voltage, error):
        """线程安全更新校准状态"""
        self.root.after(0, lambda: self.ui.update_calibration_status(station_idx, status, voltage, error))

    def thread_safe_update_calibration_current(self, station_idx, current, voltage=None):
        """线程安全更新校准电流和电压"""
        self.root.after(0, lambda s=station_idx, c=current, v=voltage: self.ui.update_calibration_current(s, c, v))

    def start_wind_speed_control(self):
        """启动风速控制功能"""
        self.root.after(0, self.update_wind_speed)
    
    def display_power_comm_stats(self):
        """显示电源通信统计信息到系统日志"""
        try:
            stats = power_comm_manager.get_stats()
            comm_msg = f"电源通信统计: 总通信次数={stats['total_communications']}, 最小间隔={stats['min_interval_ms']}ms"
            self.thread_safe_log_message(comm_msg)
            logger.info(comm_msg)
        except Exception as e:
            logger.error(f"获取电源通信统计失败: {e}")
    
    def get_power_comm_stats(self):
        """获取电源通信统计信息
        
        返回:
            dict: 包含通信统计信息的字典，如果获取失败返回None
        """
        try:
            return power_comm_manager.get_stats()
        except Exception as e:
            logger.error(f"获取电源通信统计失败: {e}")
            return None
    
    def start_print_queue_thread(self):
        """启动标签打印队列线程"""
        self.print_queue_running = True
        self.print_queue_thread = threading.Thread(target=self.process_print_queue, daemon=True)
        self.print_queue_thread.start()
        logger.info("Print queue thread started")
    
    def process_print_queue(self):
        """处理标签打印队列，确保每个标签打印间隔2秒"""
        while self.print_queue_running:
            try:
                # 获取队列中的第一个任务
                with self.print_queue_lock:
                    if not self.print_queue:
                        time.sleep(0.1)  # 队列为空时短暂休眠
                        continue
                    print_task = self.print_queue.pop(0)
                
                # 执行打印任务
                station_idx = print_task['station_idx']
                scan_result = print_task['scan_result']
                logger.info(f"Processing print task for station {station_idx}")
                
                # 执行打印
                self._print_label_internal(station_idx, scan_result)
                
                # 打印完成后等待2秒
                logger.info(f"Print task completed for station {station_idx}, waiting 2 seconds before next task")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in print queue processing: {e}")
                import traceback
                traceback.print_exc()
                # 发生错误后也等待2秒
                time.sleep(2)
    
    def start_no_scan_thread(self):
        """启动不扫码启动线程，持续给PLC发送扫码合格信号"""
        self.no_scan_running = True
        self.no_scan_thread = threading.Thread(target=self.no_scan_loop, daemon=True)
        self.no_scan_thread.start()
        logger.info("No scan thread started")
    
    def no_scan_loop(self):
        """不扫码启动循环，持续给PLC发送扫码合格信号"""
        while self.no_scan_running:
            try:
                # 直接从UI获取当前的scan_start设置，确保实时反映用户的选择
                current_scan_start = self.ui.config.get("scan_start", False) if hasattr(self.ui, 'config') else False
                
                # 检查scan_start设置，只有在scan_start为False时才发送SCAN_OK信号
                if not current_scan_start and self.plc_controller:
                    for station_idx in range(1, 11):
                        # 只有在待机状态才发送扫码合格信号
                        # 测试过程中不需要发送
                        station_status = self.station_status.get(station_idx, 'waiting_start')
                        if station_status == 'waiting_start':
                            self.plc_controller.write_status(station_idx, 'SCAN_OK', True)
                            logger.debug(f"Sent SCAN_OK signal to station {station_idx} (no scan mode, waiting_start)")
                elif current_scan_start:
                    # 如果scan_start为True，不发送SCAN_OK信号
                    logger.debug(f"scan_start is True, skipping SCAN_OK signal in no_scan_loop")
            except Exception as e:
                logger.error(f"Error in no scan loop: {e}")
            time.sleep(2)  # 每2秒发送一次信号
    
    def on_test_complete(self, station_idx, success, scan_result, test_results=None):
        """测试完成回调函数"""
        logger.info(f"=== Test complete for station {station_idx}: success={success}, scan_result={scan_result} ===")
        
        # 保存测试记录
        if test_results:
            logger.info(f"Saving test record for station {station_idx}")
            try:
                # 获取当前产品型号
                product_config = self.ui.get_current_product_config()
                product_model = product_config.get("name", "Unknown") if product_config else "Unknown"
                
                # 保存到数据库
                import database
                database.save_test_record(
                    product_model=product_model,
                    scan_result=scan_result,
                    station_id=station_idx,
                    data_dict=test_results,
                    fault_info=None # 故障信息可以在test_results中携带
                )
                logger.info(f"Test record saved successfully for station {station_idx}")
            except Exception as e:
                logger.error(f"Error saving test record: {e}")
                import traceback
                traceback.print_exc()

        # 无论测试成功还是失败，都重置工位状态
        self.station_status[station_idx] = 'waiting_start'
        
        # 如果测试失败，直接返回
        if not success:
            logger.info(f"Test failed for station {station_idx}, no label printing needed")
            # 重置UI
            self.thread_safe_update_ui(station_idx, 0, "准备就绪", "white")
            self.reset_test_ui(station_idx)
            return
        
        # 检查是否需要打印标签二维码
        if not self.print_label_qr:
            logger.info(f"Label QR printing disabled for station {station_idx}, sending PASS signal directly")
            # 不需要打印标签，直接发送合格信号
            if self.plc_controller:
                logger.info(f"Sending PASS signal to PLC for station {station_idx}")
                self.plc_controller.write_status(station_idx, 'PASS', True)
                logger.info(f"Sent PASS signal to PLC for station {station_idx}")
            # 更新状态
            self.station_status[station_idx] = 'waiting_start'
            return
        
        # 标记该工位需要打印标签
        logger.info(f"Marking station {station_idx} for label printing")
        self.need_label_print[station_idx] = {
            'scan_result': scan_result,
            'timestamp': time.time()
        }
        
        # 打印标签
        logger.info(f"Calling print_label for station {station_idx}")
        try:
            self.print_label(station_idx, scan_result)
            logger.info(f"print_label called successfully for station {station_idx}")
        except Exception as e:
            logger.error(f"Error calling print_label for station {station_idx}: {e}")
            import traceback
            traceback.print_exc()
        
        # 更新UI状态
        self.thread_safe_update_ui(station_idx, 0, "等待扫码确认", "#FFA500")  # 橙色
        self.thread_safe_log_message(f"工位{station_idx}测试完成，等待扫码确认标签")
        logger.info(f"Station {station_idx} UI updated to waiting for scan confirmation")
    
    def on_fault_stop_test(self, station_idx, fault):
        """故障停止测试回调函数"""
        logger.info(f"=== Fault detected for station {station_idx}, stopping test: {fault['name']} ===")
        
        # 停止测试
        if station_idx in self.runners:
            logger.info(f"Stopping test for station {station_idx} due to fault")
            self.runners[station_idx].stop()
        
        # 更新状态
        self.station_status[station_idx] = 'waiting_start'
        
        # 更新UI
        fault_info = f"故障: {fault['name']} (代码: {fault['code']})"
        self.thread_safe_update_ui(station_idx, 0, fault_info, "#FF0000")  # 红色
        
        # 发送停止信号给PLC
        if self.plc_controller:
            if self.scan_start:
                self.plc_controller.write_status(station_idx, 'SCAN_OK', False)
            self.plc_controller.write_status(station_idx, 'PASS', False)
            self.plc_controller.write_status(station_idx, 'FAIL', False)
        
        # 记录日志
        self.thread_safe_log_message(f"工位{station_idx}因故障停止测试: {fault['name']}")
        logger.info(f"Station {station_idx} test stopped due to fault: {fault['name']}")
    
    def print_label(self, station_idx, scan_result):
        """打印标签，将打印请求添加到队列"""
        try:
            logger.info(f"=== Adding print request for station {station_idx}, scan_result: {scan_result} ===")
            
            # 将打印任务添加到队列
            print_task = {
                'station_idx': station_idx,
                'scan_result': scan_result
            }
            
            with self.print_queue_lock:
                self.print_queue.append(print_task)
                logger.info(f"Print task added to queue for station {station_idx}, queue length: {len(self.print_queue)}")
            
            # 通知用户打印任务已添加到队列
            self.thread_safe_log_message(f"工位{station_idx}标签打印任务已添加到队列")
            
        except Exception as e:
            logger.error(f"Error adding print task for station {station_idx}: {e}")
            import traceback
            traceback.print_exc()
            self.thread_safe_log_message(f"工位{station_idx}添加打印任务失败: {str(e)[:50]}")
    
    def _print_label_internal(self, station_idx, scan_result):
        """内部打印标签方法，实际执行打印操作"""
        try:
            logger.info(f"=== Internal printing label for station {station_idx}, scan_result: {scan_result} ===")
            
            # 获取产品名称和Part Number
            product_config = self.ui.get_current_product_config()
            product_name = product_config.get("name", "Unknown") if product_config else "Unknown"
            part_number = product_config.get("part_number", "H081683084") if product_config else "H081683084"
            
            logger.info(f"Station {station_idx} - Product: {product_name}, Part Number: {part_number}")
            
            # 构建标签内容
            label_data = {
                'station': station_idx,
                'product': product_name,
                'sn': scan_result,
                'part_number': part_number
            }
            
            # 调用标签打印机
            if self.label_printer:
                logger.info(f"Calling label printer for station {station_idx}")
                qr_content = self.label_printer.print_label(label_data)
                logger.info(f"Label printer returned qr_content: {qr_content}")
                
                # 保存二维码内容
                if qr_content:
                    logger.info(f"Saving QR content for station {station_idx}: {qr_content}")
                    self.label_qr_contents[station_idx] = qr_content
                    
                    # 更新need_label_print中的scan_result为标签二维码内容
                    if station_idx in self.need_label_print:
                        logger.info(f"Updating expected scan result for station {station_idx} to: {qr_content}")
                        self.need_label_print[station_idx]['scan_result'] = qr_content
                    
                    # 立即更新数据库中的记录，添加标签二维码内容
                    logger.info(f"Updating database record with label QR code for station {station_idx}")
                    try:
                        # 更新数据库记录
                        import database
                        # 首先查询该工位的最新记录，不依赖扫码结果
                        records = database.query_records(station_id=station_idx)
                        if records:
                            # 获取最新的记录
                            latest_record = records[0]
                            record_id = latest_record['id']
                            
                            # 更新记录，添加标签二维码内容
                            import sqlite3
                            from database import DB_FILE
                            
                            conn = sqlite3.connect(DB_FILE, timeout=20)
                            c = conn.cursor()
                            c.execute("UPDATE test_records SET label_qr = ? WHERE id = ?", (qr_content, record_id))
                            conn.commit()
                            conn.close()
                            
                            logger.info(f"Database record updated successfully for station {station_idx}, record ID: {record_id}")
                        else:
                            logger.warning(f"No database record found for station {station_idx}")
                    except Exception as e:
                        logger.error(f"Error updating database record with label QR code: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    logger.info(f"Label printed for station {station_idx}")
                    self.thread_safe_log_message(f"工位{station_idx}标签打印完成")
                else:
                    logger.error(f"Failed to get QR content for station {station_idx}")
                    self.thread_safe_log_message(f"工位{station_idx}标签打印失败: 二维码内容为空")
            else:
                logger.error(f"Label printer not initialized for station {station_idx}")
                self.thread_safe_log_message(f"工位{station_idx}标签打印机未初始化")
                
        except Exception as e:
            logger.error(f"Error printing label for station {station_idx}: {e}")
            import traceback
            traceback.print_exc()
            self.thread_safe_log_message(f"工位{station_idx}标签打印失败: {str(e)[:50]}")

if __name__ == "__main__":
    root = tk.Tk()
    
    # Hide the main window initially
    root.withdraw()
    
    # Show loading screen
    loader = LoadingWindow(root)
    
    try:
        app = MainApp(root, loader=loader)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        # Show error in messagebox before exiting if possible
        try:
            from tkinter import messagebox
            messagebox.showerror("Startup Error", f"Failed to start application:\n{e}")
        except:
            pass
        loader.destroy()
        root.destroy()
        sys.exit(1)
    
    # Close loading screen and show main window
    loader.destroy()
    root.deiconify()
    
    # Handle window close to stop all threads
    def on_closing():
        # 导入必要的模块
        import tkinter as tk
        from tkinter import ttk
        import sys
        
        # 创建退出倒计时弹窗
        countdown_window = tk.Toplevel(root)
        countdown_window.title("退出系统")
        countdown_window.geometry("300x150")
        countdown_window.resizable(False, False)
        countdown_window.transient(root)
        countdown_window.grab_set()
        
        # 设置弹窗位置
        root_x = root.winfo_x()
        root_y = root.winfo_y()
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        
        window_width = 300
        window_height = 150
        x = root_x + (root_width // 2) - (window_width // 2)
        y = root_y + (root_height // 2) - (window_height // 2)
        countdown_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 添加标签
        label = tk.Label(countdown_window, text="系统正在退出...", font=("SimHei", 12))
        label.pack(pady=20)
        
        countdown_label = tk.Label(countdown_window, text="5秒后自动退出", font=("SimHei", 14, "bold"))
        countdown_label.pack(pady=10)
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(countdown_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        # 倒计时变量
        countdown = 5
        
        # 倒计时函数
        def update_countdown():
            nonlocal countdown
            if countdown > 0:
                countdown -= 1
                countdown_label.config(text=f"{countdown}秒后自动退出")
                # 更新进度条
                progress = (5 - countdown) * 20  # 5秒 -> 100%
                progress_var.set(progress)
                countdown_window.after(1000, update_countdown)
            else:
                # 倒计时结束，执行清理操作
                countdown_window.destroy()
                # 立即退出，不执行复杂的清理操作
                logger.info("Application closing, exiting immediately...")
                # 销毁主窗口
                try:
                    root.destroy()
                except Exception as e:
                    logger.error(f"Error destroying root window: {e}")
                # 退出系统
                logger.info("Exiting system...")
                sys.exit(0)
        
        # 开始倒计时
        update_countdown()
        
        # 禁止关闭弹窗
        countdown_window.protocol("WM_DELETE_WINDOW", lambda: None)
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
