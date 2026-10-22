import time
import threading
import datetime
import json
import os
from ctypes import *
from logger import logger
from Power_6 import ProgrammablePowerSupply
from LIN_6 import (
    create_command_message, 
    parse_response_message,
    LIN_EX_Init,
    LIN_EX_MASTER,
    LIN_EX_SUCCESS,
    send_lin_message_fast,
    LIN_EX_MSG_TYPE_MW,
    LIN_EX_MSG_TYPE_MR,
    LIN_EX_MasterRead,
    USB_CloseDevice
)
from usb_device import USB_ScanDevice, USB_OpenDevice, DEV_GetDeviceInfo, DEVICE_INFO

class CalibrationStatus:
    IDLE = "idle"
    WAITING_PLC = "waiting_plc"
    CALIBRATING = "calibrating"
    COMPLETED = "completed"
    FAILED = "failed"

class CalibrationRunner:
    def __init__(self, station_idx, station_config, ui_callback, log_callback, plc_controller, config_manager, current_callback=None):
        self.station_idx = station_idx
        self.config = station_config
        self.ui_callback = ui_callback
        self.log_callback = log_callback
        self.plc_controller = plc_controller
        self.config_manager = config_manager
        self.current_callback = current_callback
        self.running = False
        self.psu = None
        self.lin_handle = None
        self.lin_index = int(self.config.get("lin_index", 0))
        self.status = CalibrationStatus.IDLE
        self.calibrated_voltage = 0.0
        self.last_error = ""
        
    def log(self, message):
        if self.log_callback:
            self.log_callback(f"工位{self.station_idx}校准: {message}")
        logger.info(f"Station {self.station_idx} calibration: {message}")
    
    def update_status(self, status):
        self.status = status
        if self.ui_callback:
            self.ui_callback(self.station_idx, status, self.calibrated_voltage, "")
    
    def stop(self):
        self.running = False
        self.log("Stopping calibration...")
    
    def find_target_device_by_sn(self, target_sn):
        DevHandles = (c_uint * 20)()
        ret = USB_ScanDevice(byref(DevHandles))
        if ret == 0:
            return None

        for i in range(ret):
            ret_open = USB_OpenDevice(DevHandles[i])
            if ret_open:
                USB2XXXInfo = DEVICE_INFO()
                USB2XXXFunctionString = (c_char * 256)()
                ret_info = DEV_GetDeviceInfo(DevHandles[i], byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                
                if ret_info:
                    serial_parts = []
                    for j in range(len(USB2XXXInfo.SerialNumber)):
                        serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                    device_serial = ''.join(serial_parts)
                    
                    if device_serial == target_sn:
                        return DevHandles[i]
                    else:
                        USB_CloseDevice(DevHandles[i])
                else:
                    USB_CloseDevice(DevHandles[i])
        return None
    
    def _find_fault_voltage_for_stage(self, power_percent):
        """
        为指定功率百分比阶段查找故障电压
        
        参数:
            power_percent: 功率百分比 (70, 50, 30, 10)
        
        返回:
            故障电压值，如果未找到则返回None
        """
        if not self.running:
            return None
        
        self.log(f"开始查找{power_percent}%功率的故障电压...")
        
        # 创建当前阶段的命令数据
        stage_cmd_data = create_command_message(power_percentage=power_percent, enable=True)
        
        # 从15.2V开始扫描
        current_voltage = 15.2
        max_voltage = 24.0  # 安全上限
        step_voltage = 0.1
        fault_voltage = None
        
        while self.running and current_voltage <= max_voltage:
            # 1. 设置当前电压
            self.psu.set_voltage(current_voltage)
            
            # 2. 等待电流稳定
            wait_start = time.time()
            current_history = []
            current_stable = False
            
            while self.running and time.time() - wait_start < 20.0:  # 20秒超时
                # 发送心跳
                send_lin_message_fast(self.lin_handle, 0x24, stage_cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
                
                # 读取LIN反馈电流
                ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
                if ret == 1 and out_msg.DataLen > 0:
                    data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                    signals = parse_response_message(data_bytes)
                    if 'measured_current' in signals:
                        curr = signals['measured_current'].get('physical_value', 0)
                        
                        # Update real-time current to UI immediately
                        if self.current_callback:
                            self.current_callback(self.station_idx, curr, current_voltage)
                        
                        now = time.time()
                        current_history.append((now, curr))
                        
                        # 保留最近3秒的数据
                        current_history = [(t, c) for t, c in current_history if now - t <= 3.0]
                        
                        if len(current_history) > 10:
                            time_span = current_history[-1][0] - current_history[0][0]
                            if time_span >= 2.8:
                                currents = [c for t, c in current_history]
                                diff = max(currents) - min(currents)
                                if diff <= 0.4:  # ±0.2A means max-min <= 0.4
                                    current_stable = True
                                    break
                time.sleep(0.05)
            
            if not self.running:
                break
            
            # 3. 检查LIN反馈状态 (连续5次0x2)
            consecutive_0x2_count = 0
            check_count = 5
            is_fault_confirmed = False
            
            for _ in range(check_count):
                ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
                if ret == 1 and out_msg.DataLen > 0:
                    data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                    signals = parse_response_message(data_bytes)
                    if 'operating_status' in signals:
                        ptc_status_code = signals['operating_status'].get('value', -1)
                        if ptc_status_code == 0x2:
                            consecutive_0x2_count += 1
                        else:
                            break  # 只要有一次不是0x2，就跳出当前电压的检查
                time.sleep(0.1)
            
            if consecutive_0x2_count == check_count:
                fault_voltage = current_voltage
                self.log(f"{power_percent}%功率: 连续5次收到0x2报警，故障电压: {fault_voltage:.2f}V")
                is_fault_confirmed = True
                break  # 跳出电压扫描循环
            
            self.log(f"{power_percent}%功率: 电压: {current_voltage:.2f}V, 未检测到连续0x2 (计数: {consecutive_0x2_count})")
            
            # 4. 增加电压
            current_voltage += step_voltage
        
        if fault_voltage is None:
            self.log(f"{power_percent}%功率: 电压扫描完成，未检测到连续5次0x2报警，最大电压: {current_voltage:.2f}V")
        
        return fault_voltage
    
    def run(self):
        self.running = True
        self.update_status(CalibrationStatus.WAITING_PLC)
        self.log("等待PLC启动信号...")
        
        try:
            # 等待PLC启动信号
            start_time = time.time()
            timeout = 60  # 60秒超时
            
            while self.running and time.time() - start_time < timeout:
                if self.plc_controller:
                    # 检查PLC是否发送了启动信号
                    # 这里需要根据实际PLC信号定义进行修改
                    # 假设PLC会发送一个启动校准的信号
                    if self.plc_controller.get_calibration_start_signal(self.station_idx):
                        self.log("收到PLC启动信号，开始校准")
                        break
                time.sleep(0.5)
            
            if not self.running:
                self.update_status(CalibrationStatus.FAILED)
                return
            
            if time.time() - start_time >= timeout:
                self.log("等待PLC信号超时")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            # 初始化硬件
            self.update_status(CalibrationStatus.CALIBRATING)
            
            # 连接电源
            com_port = self.config.get("com_port", "COM4")
            station_address = int(self.config.get("station_addr", 6))
            
            self.log(f"连接电源: {com_port}, 地址: {station_address}")
            self.psu = ProgrammablePowerSupply(port=com_port, station_address=station_address, station_idx=station_idx)
            
            # 连接LIN
            lin_sn = self.config.get("lin_sn", "")
            self.log(f"查找LIN设备: {lin_sn}")
            self.lin_handle = self.find_target_device_by_sn(lin_sn)
            
            if not self.lin_handle:
                self.log("LIN设备未找到")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            ret = LIN_EX_Init(self.lin_handle, self.lin_index, 19200, LIN_EX_MASTER)
            if ret != LIN_EX_SUCCESS:
                self.log(f"LIN初始化失败: {ret}")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            # 校准开始
            self.log("开始电压校准...")
            
            # 初始化电源参数
            self.psu.set_overvoltage(24.0)
            self.psu.set_current(300)
            self.psu.power_on()
            time.sleep(1)

            # 1. 设置电源电压到15.2V
            initial_voltage = 15.2
            self.psu.set_voltage(initial_voltage)
            time.sleep(1)
            
            # 1.1 确认电压反馈是15.2V
            self.log("等待电压稳定在15.2V...")
            voltage_stable = False
            check_start = time.time()
            while time.time() - check_start < 10: # 10秒超时
                status = self.psu.read_status()
                if status and abs(status['voltage'] - initial_voltage) < 0.5:
                    voltage_stable = True
                    self.log(f"电压已稳定: {status['voltage']:.2f}V")
                    break
                time.sleep(0.5)
                
            if not voltage_stable:
                self.log("电压无法稳定在15.2V，校准终止")
                self.update_status(CalibrationStatus.FAILED)
                return

            # 2. 确认LIN通讯成功
            test_cmd_data = create_command_message(power_percentage=0, enable=False)
            ret, out_msg = send_lin_message_fast(self.lin_handle, 0x24, test_cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
            if ret != 1:
                self.log("LIN通讯测试失败")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            self.log("LIN通讯测试成功")
            
            # 3. LIN设置功率100%，使能=1
            cmd_data = create_command_message(power_percentage=100, enable=True)
            ret, out_msg = send_lin_message_fast(self.lin_handle, 0x24, cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
            if ret != 1:
                self.log("设置LIN 100%功率失败")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            self.log("LIN设置为100%功率，使能=1")
            
            # 4. 验证LIN设置是否正确
            self.log("验证LIN功率设置和使能状态...")
            time.sleep(0.5)  # 等待设置生效
            
            # 读取LIN反馈确认设置
            ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
            if ret == 1 and out_msg.DataLen > 0:
                data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                signals = parse_response_message(data_bytes)
                
                # 检查PTC运行状态
                if 'operating_status' in signals:
                    status_val = signals['operating_status'].get('value', -1)
                    status_desc = signals['operating_status'].get('description', 'Unknown')
                    self.log(f"LIN反馈状态: 0x{status_val:X} ({status_desc})")
                    # 只要能读到状态，就认为通讯正常
                else:
                    self.log("警告: 无法解析运行状态")
                
                self.log("LIN功率设置和使能状态验证完成")
            else:
                self.log("无法读取LIN反馈进行验证")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            # 4. 等待LIN反馈电流稳定
            self.log("等待LIN反馈电流稳定(3秒内偏差<=0.4A)...")
            current_stable = False
            check_start = time.time()
            current_history = []  # List of (timestamp, current)
            current_psu_v = 0.0
            
            while self.running and time.time() - check_start < 1000: # 1000秒超时
                # 读取电源状态
                try:
                    psu_sts = self.psu.read_status()
                    if psu_sts:
                        current_psu_v = psu_sts.get('voltage', 0.0)
                except:
                    pass
                
                # 发送心跳
                send_lin_message_fast(self.lin_handle, 0x24, cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
                
                # 读取LIN反馈电流
                ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
                if ret == 1 and out_msg.DataLen > 0:
                    data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                    signals = parse_response_message(data_bytes)
                    if 'measured_current' in signals:
                        curr = signals['measured_current'].get('physical_value', 0)
                        
                        # Update real-time current to UI immediately
                        if self.current_callback:
                            self.log(f"调用current_callback: station_idx={self.station_idx}, current={curr:.2f}A, voltage={current_psu_v:.2f}V")
                            self.current_callback(self.station_idx, curr, current_psu_v)
                        else:
                            self.log(f"警告: current_callback为None，无法更新实时数据")
                        
                        # 调试日志：打印解析到的电流和状态
                        if int(time.time()) % 2 == 0 and abs(time.time() - int(time.time())) < 0.1:
                             status_val = signals.get('operating_status', {}).get('value', -1)
                             comm_err = signals.get('communication_error', {}).get('value', 0)
                             over_curr = signals.get('over_current_fault', {}).get('value', 0)
                             under_curr = signals.get('under_current_fault', {}).get('value', 0)
                             arc = signals.get('arc_counter', {}).get('value', 0)
                             self.log(f"LIN 0x25: 电源={current_psu_v:.2f}V, 电流={curr:.2f}A, 状态=0x{status_val:X}, 通讯误={comm_err}, 过流={over_curr}, 欠流={under_curr}, ARC={arc}")

                        now = time.time()
                        current_history.append((now, curr))
                        
                        # Keep recent 3 seconds data
                        current_history = [(t, c) for t, c in current_history if now - t <= 3.0]
                        
                        # Check stability: time span close to 3s, and fluctuation within 0.4A
                        if len(current_history) > 10: # Ensure enough data points
                            time_span = current_history[-1][0] - current_history[0][0]
                            if time_span >= 2.8: # Close to 3s
                                currents = [c for t, c in current_history]
                                avg = sum(currents) / len(currents)
                                diff = max(currents) - min(currents)
                                
                                # 每隔2秒打印一次调试信息
                                if int(now) % 2 == 0 and abs(now - int(now)) < 0.1:
                                     # self.log(f"当前电流: {curr:.2f}A, 3秒波动: {diff:.2f}A (阈值0.4A)")
                                     pass

                                if diff <= 0.4: # ±0.2A means max-min <= 0.4
                                    current_stable = True
                                    self.log(f"电流已稳定: {avg:.2f}A (波动: {diff:.2f}A)")
                                    break
                time.sleep(0.05) # 50ms interval
                
            if not current_stable:
                 self.log("电流无法稳定，校准终止")
                 self.update_status(CalibrationStatus.FAILED)
                 return
            
            # 4.5 检查15.2V时的PTC状态
            self.log("检查15.2V时的PTC状态...")
            ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
            if ret == 1 and out_msg.DataLen > 0:
                data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                signals = parse_response_message(data_bytes)
                if 'operating_status' in signals:
                    status_val = signals['operating_status'].get('value', -1)
                    status_desc = signals['operating_status'].get('description', 'Unknown')
                    self.log(f"15.2V时PTC状态: 0x{status_val:X} ({status_desc})")
                    if status_val != 0:
                        self.log("警告: 15.2V时状态非0x0 (Normal)!")
            
            # 5. 每次增加0.1V直到LIN连续5次收到0x2报警
            current_voltage = initial_voltage
            max_voltage = 24.0  # 安全上限
            step_voltage = 0.1
            
            # 这里的逻辑是：逐步升高电压，在每个电压点等待电流稳定，
            # 然后检查状态。如果状态为0x2，则连续读取5次确认。
            # 如果5次都是0x2，则记录当前电压为故障电压。
            
            self.log("开始电压扫描...")
            
            while self.running and current_voltage <= max_voltage:
                # 1. 设置当前电压
                self.psu.set_voltage(current_voltage)
                
                # 2. 等待电流稳定
                wait_start = time.time()
                current_history_scan = []
                current_stable_scan = False
                last_psu_read_time = 0
                current_psu_v = 0.0
                
                while self.running and time.time() - wait_start < 1000.0: # 1000秒超时
                     # Update PSU voltage every 0.5s
                     if time.time() - last_psu_read_time > 0.5:
                         try:
                             psu_sts = self.psu.read_status()
                             if psu_sts:
                                 current_psu_v = psu_sts.get('voltage', 0.0)
                                 last_psu_read_time = time.time()
                         except:
                             pass

                     # 发送心跳
                     send_lin_message_fast(self.lin_handle, 0x24, cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
                     
                     # 读取LIN反馈电流
                     ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
                     if ret == 1 and out_msg.DataLen > 0:
                        data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                        signals = parse_response_message(data_bytes)
                        if 'measured_current' in signals:
                            curr = signals['measured_current'].get('physical_value', 0)
                            
                            # 更新实时电流到UI
                            if self.current_callback:
                                self.log(f"电压扫描阶段调用current_callback: station_idx={self.station_idx}, current={curr:.2f}A, voltage={current_psu_v:.2f}V")
                                self.current_callback(self.station_idx, curr, current_psu_v)
                            else:
                                self.log(f"电压扫描阶段警告: current_callback为None")

                            # 每2秒打印一次调试日志
                            if int(time.time()) % 2 == 0 and abs(time.time() - int(time.time())) < 0.1:
                                status_val = signals.get('operating_status', {}).get('value', -1)
                                comm_err = signals.get('communication_error', {}).get('value', 0)
                                over_curr = signals.get('over_current_fault', {}).get('value', 0)
                                under_curr = signals.get('under_current_fault', {}).get('value', 0)
                                arc = signals.get('arc_counter', {}).get('value', 0)
                                self.log(f"LIN 0x25: 电源={current_psu_v:.2f}V, 电流={curr:.2f}A, 状态=0x{status_val:X}, 通讯误={comm_err}, 过流={over_curr}, 欠流={under_curr}, ARC={arc}")

                            now = time.time()
                            current_history_scan.append((now, curr))
                            
                            # 保留最近3秒的数据
                            current_history_scan = [(t, c) for t, c in current_history_scan if now - t <= 3.0]
                            
                            if len(current_history_scan) > 10:
                                time_span = current_history_scan[-1][0] - current_history_scan[0][0]
                                if time_span >= 2.8:
                                    currents = [c for t, c in current_history_scan]
                                    diff = max(currents) - min(currents)
                                    if diff <= 0.4: # ±0.2A means max-min <= 0.4
                                        current_stable_scan = True
                                        break
                     time.sleep(0.05)
                
                if not self.running:
                    break

                if not current_stable_scan:
                    # 记录不稳定的情况，但继续检查故障
                    pass
                
                # 3. 检查LIN反馈状态 (连续5次0x2)
                consecutive_0x2_count = 0
                check_count = 5
                is_fault_confirmed = False
                
                for _ in range(check_count):
                    ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
                    if ret == 1 and out_msg.DataLen > 0:
                        data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                        signals = parse_response_message(data_bytes)
                        if 'operating_status' in signals:
                            ptc_status_code = signals['operating_status'].get('value', -1)
                            if ptc_status_code == 0x2:
                                consecutive_0x2_count += 1
                            else:
                                break # 只要有一次不是0x2，就跳出当前电压的检查
                    time.sleep(0.1) # 间隔100ms
                
                if consecutive_0x2_count == check_count:
                    fault_voltage = current_voltage
                    self.log(f"连续5次收到0x2报警，故障电压: {fault_voltage:.2f}V")
                    is_fault_confirmed = True
                    break # 跳出电压扫描循环
                
                self.log(f"电压: {current_voltage:.2f}V, 未检测到连续0x2 (计数: {consecutive_0x2_count})")

                # 4. 增加电压
                current_voltage += step_voltage
            
            if not self.running:
                self.update_status(CalibrationStatus.FAILED)
                return
            
            if fault_voltage is None:
                self.log(f"电压扫描完成，未检测到连续5次0x2报警，最大电压: {current_voltage:.2f}V")
                self.update_status(CalibrationStatus.FAILED)
                return
            
            # 计算100%功率的补偿值和电压设定值
            # 补偿值 = 第一次出现0x2对应的电压 - 16V
            compensation_100 = fault_voltage - 16.0
            # 100%功率的电源电压设定值 = 13V + 补偿值
            voltage_setting_100 = 13.0 + compensation_100
            
            self.calibrated_voltage = voltage_setting_100
            self.log(f"100%功率校准完成: 故障电压={fault_voltage:.2f}V, 补偿值={compensation_100:.2f}V, 设定电压={voltage_setting_100:.2f}V")
            
            # 立即保存100%功率校准结果并更新UI
            initial_calibration_results = {
                "100%": {
                    "fault_voltage": fault_voltage,
                    "compensation": compensation_100,
                    "voltage_setting": voltage_setting_100
                }
            }
            self.config_manager.save_calibration_result(
                self.station_idx,
                initial_calibration_results,
                initial_voltage
            )
            self.update_status(CalibrationStatus.CALIBRATING)
            
            # 现在需要为其他百分比阶段进行校准
            # 定义要校准的百分比阶段
            calibration_stages = [
                ("70%", 70),
                ("50%", 50),
                ("30%", 30),
                ("10%", 10)
            ]
            
            calibration_results = {
                "100%": {
                    "fault_voltage": fault_voltage,
                    "compensation": compensation_100,
                    "voltage_setting": voltage_setting_100
                }
            }
            
            # 为每个百分比阶段进行校准
            for stage_name, power_percent in calibration_stages:
                self.log(f"开始{stage_name}功率校准...")
                
                # 设置当前阶段的功率百分比
                stage_cmd_data = create_command_message(power_percentage=power_percent, enable=True)
                ret, out_msg = send_lin_message_fast(self.lin_handle, 0x24, stage_cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
                if ret != 1:
                    self.log(f"设置{stage_name}功率百分比失败")
                    continue
                
                # 等待电流稳定
                time.sleep(2)
                
                # 重新进行电压扫描，找到当前阶段的故障电压
                stage_fault_voltage = self._find_fault_voltage_for_stage(power_percent)
                
                if stage_fault_voltage:
                    # 计算当前阶段的补偿值
                    stage_compensation = stage_fault_voltage - 16.0
                    # 计算当前阶段的电压设定值（使用13V作为基准）
                    stage_voltage_setting = 13.0 + stage_compensation
                    
                    calibration_results[stage_name] = {
                        "fault_voltage": stage_fault_voltage,
                        "compensation": stage_compensation,
                        "voltage_setting": stage_voltage_setting
                    }
                    
                    self.log(f"{stage_name}功率校准完成: 故障电压={stage_fault_voltage:.2f}V, 补偿值={stage_compensation:.2f}V, 设定电压={stage_voltage_setting:.2f}V")
                    
                    # 触发UI更新
                    self.update_status(CalibrationStatus.CALIBRATING)
                    
                else:
                    self.log(f"{stage_name}功率校准失败，未找到故障电压")
            
            # 调试日志：打印校准结果
            self.log(f"校准完成，准备保存结果: {calibration_results}")
            for stage, data in calibration_results.items():
                self.log(f"{stage}: fault_voltage={data.get('fault_voltage', 'N/A')}, "
                        f"compensation={data.get('compensation', 'N/A')}, "
                        f"voltage_setting={data.get('voltage_setting', 'N/A')}")
            
            # 保存校准结果
            self.config_manager.save_calibration_result(
                self.station_idx, 
                calibration_results,
                initial_voltage
            )
            
            # 恢复到安全电压
            self.psu.set_voltage(initial_voltage)
            time.sleep(1)
            
            self.update_status(CalibrationStatus.COMPLETED)
            self.log(f"校准成功，保存100%设定电压: {self.calibrated_voltage:.2f}V")
            
        except Exception as e:
            self.log(f"校准异常: {e}")
            self.last_error = str(e)
            self.update_status(CalibrationStatus.FAILED)
            import traceback
            traceback.print_exc()
        finally:
            # 清理资源
            if self.psu:
                try:
                    self.psu.set_voltage(0)
                    self.psu.power_off()
                except:
                    pass
            if self.lin_handle:
                try:
                    USB_CloseDevice(self.lin_handle)
                except:
                    pass

class CalibrationManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.runners = {}
        self.config = self._load_config()
    
    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
                return {"calibration_settings": {}}
        return {"calibration_settings": {}}
    
    def _save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def start_calibration(self, station_idx, station_config, ui_callback, log_callback, plc_controller, current_callback=None):
        if station_idx in self.runners and self.runners[station_idx].running:
            log_callback(f"工位{station_idx}正在校准中")
            return False
        
        runner = CalibrationRunner(
            station_idx=station_idx,
            station_config=station_config,
            ui_callback=ui_callback,
            log_callback=log_callback,
            plc_controller=plc_controller,
            config_manager=self,
            current_callback=current_callback
        )
        
        self.runners[station_idx] = runner
        
        # 启动校准线程
        t = threading.Thread(target=runner.run, daemon=True)
        t.start()
        
        return True
    
    def stop_calibration(self, station_idx):
        if station_idx in self.runners:
            runner = self.runners[station_idx]
            runner.stop()
            return True
        return False
    
    def save_calibration_result(self, station_idx, calibration_results, initial_voltage=15.2):
        # 重新加载配置以获取最新数据
        self.config = self._load_config()

        station_key = f"工位{station_idx}"
        if "calibration_settings" not in self.config:
            self.config["calibration_settings"] = {}
        
        if station_key not in self.config["calibration_settings"]:
            self.config["calibration_settings"][station_key] = {}
        
        # 保存基本校准信息
        self.config["calibration_settings"][station_key]["initial_voltage"] = initial_voltage
        self.config["calibration_settings"][station_key]["last_calibrated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存各阶段的校准结果
        stage_voltages = {}
        compensation_values = {}
        fault_voltages = {}
        voltage_settings = {}
        
        # 定义所有可能的阶段
        all_stages = ["100%", "70%", "50%", "30%", "10%"]
        
        # 调试日志：打印传入的校准结果
        logger.info(f"保存校准结果 - 工位{station_idx}: calibration_results keys = {list(calibration_results.keys())}")
        
        for stage in all_stages:
            if stage in calibration_results:
                result = calibration_results[stage]
                logger.info(f"保存{stage}阶段数据: fault_voltage={result.get('fault_voltage', 'N/A')}, "
                          f"compensation={result.get('compensation', 'N/A')}, "
                          f"voltage_setting={result.get('voltage_setting', 'N/A')}")
                # 保存故障电压
                fault_voltages[f"fault_voltage_{stage.replace('%', '')}"] = result["fault_voltage"]
                # 保存补偿值
                compensation_values[f"compensation_value_{stage.replace('%', '')}"] = result["compensation"]
                # 保存电压设定值
                voltage_settings[f"voltage_setting_{stage.replace('%', '')}"] = result["voltage_setting"]
                # 保存阶段电压（用于UI显示）
                stage_voltages[stage] = result["voltage_setting"]
            else:
                logger.warning(f"{stage}阶段不在calibration_results中，使用已有的值或默认值")
                # 如果某个阶段没有校准结果，使用配置中已有的值或默认值
                stage_key_num = stage.replace('%', '')
                # 从配置中获取已有的值
                existing_fault_voltage = self.config["calibration_settings"][station_key].get(f"fault_voltage_{stage_key_num}", 0.0)
                existing_compensation = self.config["calibration_settings"][station_key].get(f"compensation_value_{stage_key_num}", 0.0)
                existing_voltage_setting = self.config["calibration_settings"][station_key].get(f"voltage_setting_{stage_key_num}", 0.0)
                existing_stage_voltage = self.config["calibration_settings"][station_key].get("stage_voltages", {}).get(stage, 0.0)
                
                # 保存已有的值
                fault_voltages[f"fault_voltage_{stage_key_num}"] = existing_fault_voltage
                compensation_values[f"compensation_value_{stage_key_num}"] = existing_compensation
                voltage_settings[f"voltage_setting_{stage_key_num}"] = existing_voltage_setting
                stage_voltages[stage] = existing_stage_voltage
        
        # 合并所有数据到配置
        self.config["calibration_settings"][station_key].update(fault_voltages)
        self.config["calibration_settings"][station_key].update(compensation_values)
        self.config["calibration_settings"][station_key].update(voltage_settings)
        self.config["calibration_settings"][station_key]["stage_voltages"] = stage_voltages
        
        # 为了向后兼容，保留旧的字段
        if "100%" in calibration_results:
            result_100 = calibration_results["100%"]
            self.config["calibration_settings"][station_key]["calibrated_voltage"] = result_100["voltage_setting"]
            self.config["calibration_settings"][station_key]["fault_voltage"] = result_100["fault_voltage"]
            logger.info(f"保存向后兼容字段: calibrated_voltage={result_100['voltage_setting']}, fault_voltage={result_100['fault_voltage']}")
        
        # 调试日志：打印最终保存的数据
        logger.info(f"最终保存的补偿值: {compensation_values}")
        logger.info(f"最终保存的电压设定值: {voltage_settings}")
        
        return self._save_config()
    
    def get_calibrated_voltage(self, station_idx):
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                return self.config["calibration_settings"][station_key].get("calibrated_voltage", 0.0)
        return 0.0
    
    def get_last_calibrated(self, station_idx):
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                return self.config["calibration_settings"][station_key].get("last_calibrated", "")
        return ""
    
    def get_initial_voltage(self, station_idx):
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                return self.config["calibration_settings"][station_key].get("initial_voltage", 15.2)
        return 15.2
    
    def get_fault_voltage(self, station_idx):
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                return self.config["calibration_settings"][station_key].get("fault_voltage", 0.0)
        return 0.0
    
    def get_stage_voltages(self, station_idx):
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                stage_voltages = self.config["calibration_settings"][station_key].get("stage_voltages", {})
                # 确保所有阶段都有值
                default_stages = {"100%": 0.0, "70%": 0.0, "50%": 0.0, "30%": 0.0, "10%": 0.0}
                return {**default_stages, **stage_voltages}
        return {"100%": 0.0, "70%": 0.0, "50%": 0.0, "30%": 0.0, "10%": 0.0}
    
    def get_compensation_value(self, station_idx, stage):
        """
        获取指定阶段的补偿值
        
        参数:
            station_idx: 工位索引
            stage: 阶段名称，如 "100%", "70%", "50%", "30%", "10%"
        
        返回:
            补偿值
        """
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                key = f"compensation_value_{stage.replace('%', '')}"
                return self.config["calibration_settings"][station_key].get(key, 0.0)
        return 0.0
    
    def get_voltage_setting(self, station_idx, stage):
        """
        获取指定阶段的电压设定值
        
        参数:
            station_idx: 工位索引
            stage: 阶段名称，如 "100%", "70%", "50%", "30%", "10%"
        
        返回:
            电压设定值
        """
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                key = f"voltage_setting_{stage.replace('%', '')}"
                return self.config["calibration_settings"][station_key].get(key, 0.0)
        return 0.0
    
    def get_fault_voltage_for_stage(self, station_idx, stage):
        """
        获取指定阶段的故障电压
        
        参数:
            station_idx: 工位索引
            stage: 阶段名称，如 "100%", "70%", "50%", "30%", "10%"
        
        返回:
            故障电压
        """
        station_key = f"工位{station_idx}"
        if "calibration_settings" in self.config:
            if station_key in self.config["calibration_settings"]:
                key = f"fault_voltage_{stage.replace('%', '')}"
                return self.config["calibration_settings"][station_key].get(key, 0.0)
        return 0.0
    
    def get_all_calibration_data(self, station_idx):
        """
        获取所有校准数据
        
        参数:
            station_idx: 工位索引
        
        返回:
            包含所有校准数据的字典
        """
        # 重新加载配置以获取最新数据
        self.config = self._load_config()
        
        station_key = f"工位{station_idx}"
        result = {
            "stages": ["100%", "70%", "50%", "30%", "10%"],
            "data": {}
        }
        
        if "calibration_settings" in self.config and station_key in self.config["calibration_settings"]:
            config_data = self.config["calibration_settings"][station_key]
            
            for stage in result["stages"]:
                stage_key = stage.replace('%', '')
                result["data"][stage] = {
                    "fault_voltage": config_data.get(f"fault_voltage_{stage_key}", 0.0),
                    "compensation": config_data.get(f"compensation_value_{stage_key}", 0.0),
                    "voltage_setting": config_data.get(f"voltage_setting_{stage_key}", 0.0)
                }
        
        return result
    
    def get_calibration_status(self, station_idx):
        if station_idx in self.runners:
            return self.runners[station_idx].status
        return CalibrationStatus.IDLE
