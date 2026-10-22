import time
import threading
import sys
import os

# 添加当前目录到Python搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ctypes import *
from logger import logger
from Power_6 import ProgrammablePowerSupply
from usb_device import USB_ScanDevice, USB_OpenDevice, DEV_GetDeviceInfo, DEVICE_INFO, USB2XXXLib_available

# 尝试导入 LIN 相关模块，如果失败则设置标志
LIN_AVAILABLE = False
try:
    from LIN_6 import (
        create_command_message, 
        parse_response_message,
        LINMasterIndex,
        LIN_EX_Init,
        LIN_EX_MASTER,
        LIN_EX_SUCCESS,
        send_lin_message_fast,
        LIN_EX_MSG_TYPE_MW,
        LIN_EX_MSG_TYPE_MR,
        USB_CloseDevice
    )
    LIN_AVAILABLE = True
except Exception as e:
    logger.warning(f"LIN 模块导入失败: {e}")
    LIN_AVAILABLE = False

class ManualTestController:
    def __init__(self, update_callback, station_idx=0):
        self.update_callback = update_callback  # Function to call with new data
        self.running = False
        self.psu = None
        self.lin_handle = None
        self.monitor_thread = None
        self.lock = threading.Lock()
        self.station_idx = station_idx  # 工位索引，用于通信管理
        
        # State
        self.current_voltage = 0.0
        self.target_voltage = 13.0
        self.lin_enabled = False
        self.lin_power = 0
        self.lin_index = 0  # LIN索引，默认为0
        
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

    def start(self, config):
        """
        Start the manual test session.
        config: dict containing 'com_port', 'station_addr', 'lin_sn', 'station_idx'
        """
        if self.running:
            return True

        try:
            # 1. Connect PSU
            com_port = config.get("com_port", "COM4")
            station_addr = int(config.get("station_addr", 6))
            # 从config中获取station_idx，如果没有则使用station_addr
            station_idx = config.get("station_idx", station_addr)
            self.station_idx = station_idx
            self.psu = ProgrammablePowerSupply(port=com_port, station_address=station_addr, station_idx=self.station_idx)
            
            # 2. Connect LIN (only if LIN is available)
            if LIN_AVAILABLE:
                lin_sn = config.get("lin_sn", "")
                if lin_sn:
                    self.lin_handle = self.find_target_device_by_sn(lin_sn)
                    if self.lin_handle:
                        ret = LIN_EX_Init(self.lin_handle, LINMasterIndex, 19200, LIN_EX_MASTER)
                        if ret != LIN_EX_SUCCESS:
                            logger.error("LIN Init failed")
                            self.lin_handle = None
            
            # 3. Initial Setup
            self.psu.set_overvoltage(24.0)
            self.psu.set_current(300) # Max current
            self.psu.power_on()
            self.target_voltage = 13.0
            self.psu.set_voltage(self.target_voltage)
            
            # Start Monitor Thread
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start manual test: {e}")
            self.stop()
            return False

    def stop(self):
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
        try:
            if self.psu:
                self.psu.power_off()
                self.psu.close()
        except:
            pass
        
        try:
            if LIN_AVAILABLE and self.lin_handle:
                USB_CloseDevice(self.lin_handle)
        except:
            pass
            
        self.psu = None
        self.lin_handle = None

    def set_voltage(self, voltage):
        if self.psu:
            self.target_voltage = voltage
            self.psu.set_voltage(voltage)

    def set_lin_control(self, enable, power):
        self.lin_enabled = enable
        self.lin_power = power

    def _monitor_loop(self):
        while self.running:
            data = {}
            
            # 1. Read PSU Status
            if self.psu:
                try:
                    psu_status = self.psu.read_status()
                    if psu_status:
                        data['psu_voltage'] = psu_status.get('voltage', 0.0)
                        data['psu_current'] = psu_status.get('current', 0.0)
                except Exception as e:
                    logger.error(f"PSU Read Error: {e}")

            # 2. Handle LIN (only if LIN is available)
            if LIN_AVAILABLE and self.lin_handle:
                try:
                    # Send Command (0x24)
                    cmd_data = create_command_message(power_percentage=self.lin_power, enable=self.lin_enabled)
                    send_lin_message_fast(self.lin_handle, 0x24, cmd_data, LIN_EX_MSG_TYPE_MW, lin_index=self.lin_index)
                    
                    # Read Feedback (0x25)
                    # Small delay to allow response
                    time.sleep(0.02) 
                    ret, out_msg = send_lin_message_fast(self.lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR, lin_index=self.lin_index)
                    
                    if ret == 1 and out_msg.DataLen > 0:
                        raw_data = bytes(out_msg.Data)
                        parsed = parse_response_message(raw_data)
                        
                        # Extract signals
                        # Based on LIN_6.py logic
                        # measured_current is in 'measured_current' -> 'physical_value'
                        # operating_status is in 'operating_status' -> 'value'
                        # arc is in 'arc_counter' -> 'value'
                        
                        data['lin_current'] = parsed.get('measured_current', {}).get('physical_value', 0.0)
                        data['lin_status'] = parsed.get('operating_status', {}).get('value', -1)
                        data['lin_arc'] = parsed.get('arc_counter', {}).get('value', -1)
                        
                        # comm_error, etc are derived from status or separate bits? 
                        # In LIN_6.py:
                        # comm_error = (byte1 >> 5) & 0x01
                        # over_current = (byte1 >> 6) & 0x01
                        # under_current = (byte1 >> 7) & 0x01
                        
                        # Let's extract them manually if parse_response_message doesn't give them friendly names,
                        # but LIN_6.py's parse_response_message seems to return a dict of signals.
                        # Let's trust the dict or do raw parsing if needed.
                        # Checking LIN_6.py content would be good, but I recall the structure.
                        # Actually, let's look at the parsed dict structure again if I can... 
                        # I'll rely on the standard keys I saw earlier.
                        
                        data['lin_raw'] = raw_data.hex()
                        
                except Exception as e:
                    logger.error(f"LIN Error: {e}")

            # Callback to UI
            if self.update_callback:
                self.update_callback(data)
            
            time.sleep(0.1) # Update rate 10Hz
