import time
import threading
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger("HVTestRunner")

class HVTestRunner:
    def __init__(self, station_idx, station_config, duration_settings, power_settings, ui_callback, log_callback=None, product_name="Unknown", scan_result="", plc_controller=None, test_complete_callback=None, print_label_qr=True, label_qr=None, can_manager=None, fault_handler=None):
        self.can_manager = can_manager
        self.fault_handler = fault_handler
        self.station_idx = station_idx
        self.config = station_config
        self.duration_settings = duration_settings
        self.power_settings = power_settings
        self.ui_callback = ui_callback
        self.log_callback = log_callback
        self.product_name = product_name
        self.scan_result = scan_result
        self.plc_controller = plc_controller
        self.test_complete_callback = test_complete_callback
        self.print_label_qr = print_label_qr
        self.label_qr = label_qr
        
        self.running = False
        self.paused = False
        self.current_phase = 0
        self.remaining_time = 0
        self.start_time = 0
        # 0x4E0消息发送线程相关变量
        self.send_thread = None
        self.send_running = False
        self.current_power = 0
        # 阶段索引跟踪
        self.current_step_index = -1
        
        # UI Colors
        self.COLOR_PASS = "#90EE90" # Light Green
        self.COLOR_FAIL = "#FFCCCB" # Light Red
        self.COLOR_RUN = "#FFFFE0"  # Light Yellow
        self.COLOR_MONITOR_RUN = "yellow"
        self.COLOR_MONITOR_DONE = "#90EE90"
        
        # 读取CAN通道配置
        can_channel_str = self.config.get("can_channel", "0")
        try:
            self.can_channel = int(can_channel_str)
            self.log(f"读取到CAN通道配置: {self.can_channel}")
        except ValueError:
            self.can_channel = 0
            self.log(f"CAN通道配置无效: {can_channel_str}，使用默认值0")
        
        # 读取并解析CAN序列号
        self.can_device_str = self.config.get("can_device", "")
        if not self.can_device_str:
            self.can_device_str = self.config.get("can_sn", "")
            
        self.log(f"读取到CAN设备配置: {self.can_device_str}")
        self.can_sn = self._parse_sn(self.can_device_str)
        
        if self.can_sn:
            self.log(f"成功解析CAN序列号: {self.can_sn}")
        else:
            self.log("无法解析CAN序列号")
        
        self.test_data = {} # Store test results

        # UI Indices based on items_data in test_monitor_ui.py
        self.IDX_STATUS = 0
        self.IDX_VOLT = 1
        self.IDX_CURR = 2
        self.IDX_POWER = 20
        self.IDX_TEMP = 19
        self.IDX_COUNTDOWN = 21
        self.IDX_FAULT = 22
        self.IDX_LABEL_QR = 22  # 标签二维码
        self.IDX_FAULT_LEVEL = 20  # CAN设备状态 → PTC故障等级
        self.IDX_TEST_RESULT = 23  # 测试结果 → PTC故障代码
        # 阶段对应的方格索引
        self.STEP_INDICES = {
            0: {"power": 3, "voltage": 4, "current": 5},  # 100%功率阶段
            2: {"power": 7, "voltage": 8, "current": 9},  # 80%功率阶段
            4: {"power": 11, "voltage": 12, "current": 13}, # 60%功率阶段
            6: {"power": 15, "voltage": 16, "current": 17}, # 40%功率阶段
        }
        # 0%功率阶段对应的方格索引
        self.ZERO_POWER_INDICES = {
            1: 6,  # 0%功率（100%功率之后）
            3: 10, # 0%功率（80%功率之后）
            5: 14, # 0%功率（60%功率之后）
            7: 18, # 0%功率（40%功率之后）
        }
        
        # Logging rate limiters
        self.last_525_log_time = 0
        self.last_unparsed_log_time = 0

    def _parse_sn(self, device_str):
        """Parse Serial Number from device string"""
        # Format: "设备0: 序列号=3041... (功能: ...)"
        if not device_str:
            self.log("Empty device string")
            return None
            
        if "序列号=" in device_str:
            try:
                part = device_str.split("序列号=")[1]
                sn = part.split(" ")[0]
                sn = sn.strip()
                self.log(f"Parsed SN: {sn} from {device_str}")
                return sn
            except Exception as e:
                self.log(f"Error parsing SN from {device_str}: {e}")
                pass
        
        # 尝试其他格式
        try:
            # 直接提取16进制序列号（8个字符的16进制数，可能多个）
            import re
            matches = re.findall(r'[0-9A-Fa-f]{16,}', device_str)
            if matches:
                sn = matches[0].upper()
                self.log(f"Parsed SN using regex: {sn} from {device_str}")
                return sn
        except Exception as e:
            self.log(f"Error parsing SN with regex: {e}")
            pass
        
        # If parsing fails, return None
        self.log(f"Failed to parse SN from {device_str}")
        return None

    def log(self, message):
        full_msg = f"[Station {self.station_idx}] {message}"
        logger.info(full_msg)
        if self.log_callback:
            self.log_callback(full_msg)

    def update_ui(self, item_idx, text, color=None):
        self.test_data[item_idx] = text
        if self.ui_callback:
            try:
                self.ui_callback(self.station_idx, item_idx, text, color)
            except Exception as e:
                self.log(f"UI Update Error: {e}")

    def stop(self):
        self.running = False
        self.send_running = False
        self.log("Stopping test...")

    def run(self):
        self.running = True
        self.send_running = True
        self.log("Starting test sequence...")
        self.update_ui(self.IDX_STATUS, "Running", self.COLOR_MONITOR_RUN)
        
        # 更新第22行显示标签二维码内容
        if self.label_qr:
            self.update_ui(self.IDX_LABEL_QR, self.label_qr)
        else:
            self.update_ui(self.IDX_LABEL_QR, "无标签")

        try:
            # 0. Check CAN Manager
            if not self.can_manager:
                self.log("CAN Manager instance missing")
                self.update_ui(self.IDX_STATUS, "Sys Error", self.COLOR_FAIL)
                if self.test_complete_callback:
                    self.test_complete_callback(self.station_idx, False, "")
                return

            # 验证序列号
            if not self.can_sn:
                self.log("CAN device serial number not configured")
                self.update_ui(self.IDX_STATUS, "Config Err", self.COLOR_FAIL)
                if self.test_complete_callback:
                    self.test_complete_callback(self.station_idx, False, "")
                return

            # 检查CAN是否已初始化（避免重复连接）
            # key格式需与can_manager保持一致: {sn}_{channel}
            init_key = f"{self.can_sn}_{self.can_channel}"
            is_initialized = False
            if hasattr(self.can_manager, 'can_initialized'):
                 is_initialized = self.can_manager.can_initialized.get(init_key, False)
            
            if not is_initialized:
                self.log(f"CAN设备未就绪，正在初始化: {self.can_sn} Ch{self.can_channel}")
                # 显式初始化CAN设备
                try:
                    if not self.can_manager.initialize_can(self.can_sn, self.can_channel):
                        self.log(f"Failed to initialize CAN device {self.can_sn} Ch{self.can_channel}")
                        self.update_ui(self.IDX_STATUS, "Dev Err", self.COLOR_FAIL)
                        if self.test_complete_callback:
                            self.test_complete_callback(self.station_idx, False, "")
                        return
                    self.log(f"工位{self.station_idx}的CAN设备连接成功")
                except Exception as e:
                    self.log(f"Error initializing CAN device: {e}")
                    import traceback
                    traceback.print_exc()
                    self.update_ui(self.IDX_STATUS, "Dev Err", self.COLOR_FAIL)
                    if self.test_complete_callback:
                        self.test_complete_callback(self.station_idx, False, "")
                    return
            else:
                # 已连接，直接使用
                pass
                # self.log(f"CAN设备已就绪: {self.can_sn} Ch{self.can_channel}")

            # 1. Define Sequence Steps
            # Format: (StepName, PowerKey, TimeKey)
            steps = [
                ("Step 1 (100%)", "100%功率参数设置", "100%功率时间设置"),
                ("Step 2 (0%)", "0%功率参数设置_1", "0%功率时间设置_1"),
                ("Step 3 (80%)", "80%功率参数设置", "80%功率时间设置"),
                ("Step 4 (0%)", "0%功率参数设置_2", "0%功率时间设置_2"),
                ("Step 5 (60%)", "60%功率参数设置", "60%功率时间设置"),
                ("Step 6 (0%)", "0%功率参数设置_3", "0%功率时间设置_3"),
                ("Step 7 (40%)", "40%功率参数设置", "40%功率时间设置"),
                ("Step 8 (0%)", "0%功率参数设置_4", "0%功率时间设置_4"),
            ]

            # 2. Start send thread
            self.send_thread = threading.Thread(target=self.send_4e0_message, daemon=True)
            self.send_thread.start()
            self.log("Started 0x4E0 message send thread")

            total_steps = len(steps)
            
            for i, (step_name, power_key, time_key) in enumerate(steps):
                if not self.running:
                    break

                # 更新当前阶段索引
                self.current_step_index = i

                # Get Settings
                try:
                    target_power = float(self._get_setting(self.power_settings, power_key, 0))
                    duration = int(self._get_setting(self.duration_settings, time_key, 0))
                except (ValueError, TypeError):
                    self.log(f"Invalid settings for {step_name}, using defaults")
                    target_power = 0.0
                    duration = 5

                self.log(f"Starting {step_name}: Power={target_power}W, Time={duration}s")
                # 不更新第0行，保持显示扫码内容

                # Update current power for send thread
                self.current_power = target_power

                start_time = time.time()
                self.last_comm_time = time.time() # Initialize communication watchdog timer
                last_update_time = 0
                
                while time.time() - start_time < duration:
                    if not self.running:
                        break
                    
                    # Watchdog Check: If no communication for 5 seconds, abort
                    if time.time() - self.last_comm_time > 5.0:
                        self.log(f"Communication Watchdog Timeout: No data for 5 seconds")
                        self.update_ui(self.IDX_STATUS, "Comm Err", self.COLOR_FAIL)
                        # Stop the test
                        self.running = False
                        if self.test_complete_callback:
                            self.test_complete_callback(self.station_idx, False, self.scan_result, self.test_data)
                        break

                    # 2. Receive & Parse
                    # 持续读取CAN消息，直到缓冲区为空
                    message_received = False
                    messages_processed = 0
                    
                    while True:
                        # Use new batch receive method
                        msgs = self.can_manager.receive_messages_non_blocking(channel=self.can_channel, serial_number=self.can_sn)
                        
                        if not msgs:
                            # No more messages in buffer
                            break
                            
                        for msg in msgs:
                            messages_processed += 1
                            parsed = self.can_manager.parse_ptc_message(msg)
                            if parsed:
                                # Update watchdog timer
                                self.last_comm_time = time.time()
                                
                                # Log 0x525 reception periodically
                                if parsed["type"] == "PTC_525":
                                    if time.time() - self.last_525_log_time > 5.0:
                                        self.log(f"Received 0x525: Voltage={parsed['voltage']}V, Current={parsed['current']}A")
                                        self.last_525_log_time = time.time()
                                        
                                self._update_ui_from_can(parsed)
                                message_received = True
                            else:
                                # Log unparsed messages periodically (debug)
                                if time.time() - self.last_unparsed_log_time > 5.0:
                                    self.log(f"Received unparsed CAN ID: 0x{msg['id']:X}")
                                    self.last_unparsed_log_time = time.time()
                            
                        # Avoid infinite loop if buffer is flooded
                        if messages_processed > 200:
                            break

                    # 每50ms更新一次倒计时，避免过度更新
                    current_time = time.time()
                    if current_time - last_update_time >= 0.05:
                        # Update Countdown
                        remaining = int(duration - (current_time - start_time))
                        self.update_ui(self.IDX_COUNTDOWN, f"{remaining}s")
                        last_update_time = current_time

                    # 实时显示0%功率阶段的功率值
                    if self.current_step_index in self.ZERO_POWER_INDICES:
                        self.update_ui(self.ZERO_POWER_INDICES[self.current_step_index], f"{self.current_power}W")

                    # 减少循环间隔，提高更新频率
                    time.sleep(0.02) # 20ms cycle

            # End of Sequence
            if self.running:
                # Send 0 Power
                self.current_power = 0
                self.log("Test sequence completed successfully")
                self.update_ui(self.IDX_STATUS, "Pass", self.COLOR_PASS)
                self.update_ui(self.IDX_COUNTDOWN, "0s")
                
                if self.test_complete_callback:
                    self.test_complete_callback(self.station_idx, True, self.scan_result, self.test_data)
            else:
                self.update_ui(self.IDX_STATUS, "Stopped", self.COLOR_FAIL)
                if self.test_complete_callback:
                    self.test_complete_callback(self.station_idx, False, self.scan_result, self.test_data)

        except Exception as e:
            self.log(f"Test Error: {e}")
            import traceback
            traceback.print_exc()
            self.update_ui(self.IDX_STATUS, "Error", self.COLOR_FAIL)
            if self.test_complete_callback:
                self.test_complete_callback(self.station_idx, False, self.scan_result, self.test_data)
        
        finally:
            self.running = False
            self.send_running = False
            # Ensure 0 power on exit
            self.current_power = 0
            # Give send thread time to send 0 power command
            time.sleep(0.5)

    def send_4e0_message(self):
        """循环发送0x4E0消息"""
        while self.send_running:
            try:
                # 检查设备是否已连接且CAN是否已初始化
                if not self.can_manager or not self.can_manager.device_connected:
                    time.sleep(0.02)
                    continue
                
                # 发送功率命令
                self.can_manager.send_power_command(self.current_power, channel=self.can_channel, serial_number=self.can_sn)
                
                # 按照PTC_Power_Sequence.py中的设置，每100ms发送一次
                time.sleep(0.1)
                
            except Exception as e:
                self.log(f"发送0x4E0消息错误: {str(e)}")
                time.sleep(0.02)

    def _update_ui_from_can(self, data):
        if data["type"] == "PTC_524":
            # Update Power, Temp
            self.update_ui(self.IDX_POWER, f"{data['actual_power']}W")
            self.update_ui(self.IDX_TEMP, f"{data['temperature']}C")
            
            # Get fault information
            error_level = data.get('error_level', 0)
            error_code = data.get('error_code', 0)
            
            # Update fault level (CAN设备状态)
            fault_level_map = {
                0: "0x0: 无故障",
                1: "0x1: 轻微故障",
                2: "0x2: 一般故障",
                3: "0x3: 严重故障"
            }
            fault_level_text = fault_level_map.get(error_level, f"0x{error_level:X}: 未知等级")
            self.update_ui(self.IDX_FAULT_LEVEL, fault_level_text)
            
            # Update fault code (测试结果)
            fault_code_map = {
                0: "0x0: 无故障",
                1: "0x1: 过压(ErrorLevel=2)",
                2: "0x2: 欠压(ErrorLevel=1)",
                3: "0x3: IGBT短路(ErrorLevel=3)",
                4: "0x4: 芯体短路(ErrorLevel=3)",
                5: "0x5: IGBT开路(ErrorLevel=2)",
                6: "0x6: PTC过温(ErrorLevel=1)",
                7: "0x7: IGBT过温(ErrorLevel=1)",
                8: "0x8: PTC温度传感器故障(ErrorLevel=2)",
                9: "0x9: IGBT温度传感器故障(ErrorLevel=2)",
                10: "0xA: PTC CAN通讯故障(ErrorLevel=1)",
                11: "0xB: PTC过流故障(ErrorLevel=3)"
            }
            fault_code_text = fault_code_map.get(error_code, f"0x{error_code:X}: 未知故障")
            self.update_ui(self.IDX_TEST_RESULT, fault_code_text)
            
            # Update fault status
            if error_code > 0:
                fault_info = self.can_manager.check_fault(data)
                if fault_info:
                    self.update_ui(self.IDX_FAULT, f"{fault_info['name']}({fault_info['code']})", self.COLOR_FAIL)
                    # Save fault status
                    self.test_data[str(self.IDX_FAULT)] = f"{fault_info['name']}({fault_info['code']})"
            else:
                self.update_ui(self.IDX_FAULT, "无")
                self.test_data[str(self.IDX_FAULT)] = "无"
        
        elif data["type"] == "PTC_525":
            # Update Voltage, Current
            voltage = data['voltage']
            current = data['current']
            power = voltage * current
            
            self.update_ui(self.IDX_VOLT, f"{voltage}V")
            self.update_ui(self.IDX_CURR, f"{current:.3f}A")
            
            # 根据当前阶段更新对应的方格
            if self.current_step_index in self.STEP_INDICES:
                step_indices = self.STEP_INDICES[self.current_step_index]
                self.update_ui(step_indices["voltage"], f"{voltage}V")
                self.update_ui(step_indices["current"], f"{current:.3f}A")
                self.update_ui(step_indices["power"], f"{power:.1f}W")
                
                # Save to test_data for database
                self.test_data[str(step_indices["voltage"])] = f"{voltage}"
                self.test_data[str(step_indices["current"])] = f"{current:.3f}"
                self.test_data[str(step_indices["power"])] = f"{power:.1f}"

            # 实时显示0%功率阶段的功率值
            if self.current_step_index in self.ZERO_POWER_INDICES:
                self.update_ui(self.ZERO_POWER_INDICES[self.current_step_index], f"{self.current_power}W")

    def _get_setting(self, settings_dict, key, default):
        """Get setting with fallback to default"""
        return settings_dict.get(key, default)
