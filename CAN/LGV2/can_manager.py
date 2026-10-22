#coding:utf-8
from ctypes import *
import platform
import os
import threading
import time
import logging

logger = logging.getLogger(__name__)
from datetime import datetime

# 导入USB2XXX相关模块
try:
    # 确保当前目录在path中，以便找到usb_device.py
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)

    from usb_device import *
    from usb2can import *
    USB2CAN_AVAILABLE = True
    print("Successfully imported usb2can modules")
except ImportError as e:
    print(f"Error importing usb2can modules: {e}")
    USB2CAN_AVAILABLE = False
    
    # 定义占位类和函数
    class DEVICE_INFO(Structure):
        _fields_ = [
            ("SerialNumber", c_uint * 3),
            ("Description", c_char * 64)
        ]
    
    class CAN_INIT_CONFIG(Structure):
        _fields_ = [
            ("AccCode", c_uint),
            ("AccMask", c_uint),
            ("Filter", c_ubyte),
            ("Timing0", c_ubyte),
            ("Timing1", c_ubyte),
            ("Mode", c_ubyte)
        ]
    
    class CAN_MSG(Structure):
        _fields_ = [
            ("ExternFlag", c_ubyte),
            ("RemoteFlag", c_ubyte),
            ("ID", c_uint),
            ("DataLen", c_ubyte),
            ("Data", c_ubyte * 8)
        ]
    
    class CANFD_MSG(Structure):
        _fields_ = [
            ("ID", c_uint),
            ("DLC", c_ubyte),
            ("Flags", c_ubyte),
            ("TimeStamp", c_uint),
            ("Data", c_ubyte * 64)
        ]
    
    def USB_ScanDevice(num):
        return 0
    
    def USB_OpenDevice(index):
        return 0
    
    def USB_CloseDevice(handle):
        pass
    
    def CAN_Init(handle, channel, config):
        return -1
    
    def CAN_SendMsg(handle, channel, msg, count):
        return -1
    
    def CAN_GetMsg(handle, channel, msg, count, timeout):
        return 0
    
    def CANFD_Init(handle, channel, config):
        return -1
    
    def CANFD_SendMsg(handle, channel, msg, count):
        return -1
    
    def CANFD_GetMsg(handle, channel, msg, count, timeout):
        return 0

# 尝试导入CANFD相关模块
try:
    from usb2canfd import *
    CANFD_AVAILABLE = True
except ImportError:
    CANFD_AVAILABLE = False
    print("CANFD module not found")

# 故障代码定义
FAULT_CODES = {
    0x01: {"name": "过压", "level": 2},
    0x02: {"name": "欠压", "level": 1},
    0x03: {"name": "IGBT短路", "level": 3},
    0x04: {"name": "芯体短路", "level": 3},
    0x05: {"name": "IGBT开路", "level": 2},
    0x06: {"name": "PTC过温", "level": 1},
    0x07: {"name": "IGBT过温", "level": 1},
    0x08: {"name": "PTC温度传感器故障", "level": 2},
    0x09: {"name": "IGBT温度传感器故障", "level": 2},
    0x0A: {"name": "PTC CAN通讯故障", "level": 1},
    0x0B: {"name": "PTC过流故障", "level": 3}
}

class CANManager:
    def __init__(self):
        """初始化CAN管理器"""
        self.handles = {}  # format: {serial_number: handle}
        self.management_lock = threading.RLock() # Lock for device open/scan
        self.device_locks = {} # format: {serial_number: RLock}
        self.device_info_map = {} # format: {serial_number: info_dict}
        self.can_initialized = {} # format: {serial_number_channel: {'initialized': bool, 'baud_rate': int}}
        self.use_canfd = {} # format: {serial_number: bool}
        self.running = False
        self.callbacks = {}
        self.scanned = False  # Flag to indicate if devices have been scanned
        
        # 自动初始化
        if USB2CAN_AVAILABLE:
            self.scan_devices()

    def scan_devices(self):
        """扫描CAN设备"""
        if not USB2CAN_AVAILABLE:
            return []
            
        # Only scan once to avoid invalidating existing handles
        if self.scanned:
            print("Devices already scanned, skipping")
            return list(self.device_info_map.values())
            
        try:
            # 使用正确的扫描方式: 传入数组指针
            DevHandles = (c_uint * 20)()
            DevNum = USB_ScanDevice(byref(DevHandles))
            
            if DevNum == 0:
                print("No USB device found")
                return []
            
            print(f"Found {DevNum} devices")
            
            devices = []
            
            for i in range(DevNum):
                handle = DevHandles[i]
                # 尝试打开设备以获取信息
                if USB_OpenDevice(handle):
                    try:
                        USB2XXXInfo = DEVICE_INFO()
                        USB2XXXFunctionString = (c_char * 256)()
                        ret_info = DEV_GetDeviceInfo(handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                        
                        if ret_info:
                            serial_parts = [f"{USB2XXXInfo.SerialNumber[j]:08X}" for j in range(3)]
                            serial = ''.join(serial_parts)
                            desc = bytes(USB2XXXFunctionString.value).decode('ascii', errors='ignore')
                            
                            device_info = {
                                "handle": handle,
                                "serial": serial,
                                "description": desc,
                                "index": i
                            }
                            devices.append(device_info)
                            # Update local map
                            self.device_info_map[serial] = device_info
                            print(f"Device {i}: {serial} - {desc}")
                    except Exception as e:
                        print(f"Error getting info for device {i}: {e}")
                    finally:
                        USB_CloseDevice(handle)
                        # Add delay to ensure device is fully released
                        time.sleep(0.1)
                
            # Mark as scanned
            self.scanned = True
            return devices
        except Exception as e:
            print(f"Error scanning devices: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_device_handle(self, serial_number):
        """根据序列号获取设备句柄，如果未打开则打开"""
        if not serial_number:
            return None
            
        # Check if already open
        if serial_number in self.handles:
            print(f"Device {serial_number} already open, reusing handle")
            return self.handles[serial_number]
        
        # Use management lock to prevent race conditions during device opening
        with self.management_lock:
            # Double-check after acquiring lock
            if serial_number in self.handles:
                print(f"Device {serial_number} already open (double-check), reusing handle")
                return self.handles[serial_number]
            
            # We need to scan to get the handle, but this will invalidate existing handles
            # So we need to re-open all devices after scanning
            print(f"Scanning devices to find {serial_number}...")
            DevHandles = (c_uint * 20)()
            DevNum = USB_ScanDevice(byref(DevHandles))
            
            if DevNum == 0:
                print("No USB device found")
                return None
            
            print(f"Found {DevNum} devices")
            
            # Find the target device and all existing devices
            target_handle = None
            device_map = {}
            opened_devices = []
            
            try:
                for i in range(DevNum):
                    handle = DevHandles[i]
                    # Check if this device is already open in our handles
                    device_already_open = False
                    for serial, existing_handle in self.handles.items():
                        if existing_handle == handle:
                            device_already_open = True
                            break
                    
                    # Only open devices that aren't already open
                    if not device_already_open and USB_OpenDevice(handle):
                        opened_devices.append(handle)
                        try:
                            USB2XXXInfo = DEVICE_INFO()
                            USB2XXXFunctionString = (c_char * 256)()
                            ret_info = DEV_GetDeviceInfo(handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                            
                            if ret_info:
                                serial_parts = [f"{USB2XXXInfo.SerialNumber[j]:08X}" for j in range(3)]
                                serial = ''.join(serial_parts)
                                device_map[serial] = handle
                                
                                if serial == serial_number:
                                    target_handle = handle
                                    print(f"Found target device {serial_number} with handle {handle}")
                        except Exception as e:
                            print(f"Error getting info for device {i}: {e}")
                    else:
                        # Device is already open, try to get its info without reopening
                        try:
                            USB2XXXInfo = DEVICE_INFO()
                            USB2XXXFunctionString = (c_char * 256)()
                            ret_info = DEV_GetDeviceInfo(handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                            
                            if ret_info:
                                serial_parts = [f"{USB2XXXInfo.SerialNumber[j]:08X}" for j in range(3)]
                                serial = ''.join(serial_parts)
                                device_map[serial] = handle
                                
                                if serial == serial_number:
                                    target_handle = handle
                                    print(f"Found target device {serial_number} with handle {handle} (already open)")
                        except Exception as e:
                            print(f"Error getting info for already open device {i}: {e}")
                
                if target_handle is None:
                    print(f"Device {serial_number} not found after scan")
                    return None
                
                # Re-open all previously open devices
                current_handles = list(self.handles.keys())
                for serial in current_handles:
                    if serial in device_map:
                        handle = device_map[serial]
                        # If the device is already open, just update the handle
                        if handle in opened_devices:
                            self.handles[serial] = handle
                            print(f"Updated handle for device {serial} to {handle}")
                        else:
                            # Device is already open, just update the handle reference
                            self.handles[serial] = handle
                            print(f"Updated handle reference for device {serial} to {handle}")
                
                # If target device is already open, just use it
                if target_handle in opened_devices:
                    self.handles[serial_number] = target_handle
                    if serial_number not in self.device_locks:
                        self.device_locks[serial_number] = threading.RLock()
                    print(f"Successfully opened device {serial_number}")
                    return target_handle
                else:
                    # Try to open the target device if it's not already open
                    if USB_OpenDevice(target_handle):
                        self.handles[serial_number] = target_handle
                        if serial_number not in self.device_locks:
                            self.device_locks[serial_number] = threading.RLock()
                        print(f"Successfully opened device {serial_number}")
                        return target_handle
                    else:
                        print(f"Failed to open device {serial_number}")
                        return None
            finally:
                # Close only the devices that were opened during this scan
                for handle in opened_devices:
                    if handle != target_handle:
                        USB_CloseDevice(handle)
                        time.sleep(0.1)

    def initialize_can(self, serial_number, channel=0, baud_rate=500000):
        """初始化指定设备的CAN通道"""
        # Fast check without getting handle first
        key = f"{serial_number}_{channel}"
        # Check outside lock for quick exit
        if self.can_initialized.get(key) and \
           self.can_initialized[key]['initialized'] and \
           self.can_initialized[key]['baud_rate'] == baud_rate:
            logger.info(f"CAN channel {key} already initialized with matching baud rate {baud_rate}.")
            return True

        handle = self.get_device_handle(serial_number)
        if handle is None:
            logger.error(f"Failed to get device handle for {serial_number}")
            return False

        lock = self.device_locks.get(serial_number)
        if lock:
            lock.acquire()
        try:
            # Check inside lock to prevent race conditions during initialization
            current_init_state = self.can_initialized.get(key)
            if current_init_state and \
               current_init_state['initialized'] and \
               current_init_state['baud_rate'] == baud_rate:
                logger.info(f"CAN channel {key} already initialized by another thread with matching baud rate {baud_rate}.")
                return True

            # If not initialized, or baud rate mismatch, proceed with initialization
            logger.info(f"Initializing CAN channel {key} with baud rate {baud_rate}.")
            success = self._initialize_can_impl(handle, serial_number, channel, key, baud_rate)
            if success:
                self.can_initialized[key] = {'initialized': True, 'baud_rate': baud_rate}
            else:
                self.can_initialized[key] = {'initialized': False, 'baud_rate': baud_rate} # Record failure
            return success
        finally:
            if lock:
                lock.release()

    def _initialize_can_impl(self, handle, serial_number, channel, key, baud_rate):
        try:
            # 检查handle是否有效
            if not handle:
                logger.error("Error: Invalid handle provided to _initialize_can_impl")
                return False
                
            logger.info(f"Initializing CAN for Ch{channel} with baud rate {baud_rate}")
            
            # 1. 优先尝试CANFD初始化
            if 'CANFD_Init' in globals():
                print(f"Attempting CANFD Init on {serial_number} Ch{channel}...")
                try:
                    CANFDConfig = CANFD_INIT_CONFIG()
                    CANFDConfig.Mode = 0
                    CANFDConfig.ISOCRCEnable = 1
                    CANFDConfig.RetrySend = 1
                    CANFDConfig.ResEnable = 1
                    
                    # 500kbps @ 40MHz
                    CANFDConfig.NBT_BRP = 10
                    CANFDConfig.NBT_SEG1 = 6
                    CANFDConfig.NBT_SEG2 = 1
                    CANFDConfig.NBT_SJW = 1
                    
                    CANFDConfig.DBT_BRP = 10
                    CANFDConfig.DBT_SEG1 = 6
                    CANFDConfig.DBT_SEG2 = 1
                    CANFDConfig.DBT_SJW = 1
                    
                    ret = CANFD_Init(handle, channel, byref(CANFDConfig))
                    print(f"CANFD_Init returned: {ret} (CANFD_SUCCESS={CANFD_SUCCESS})")
                    if ret == CANFD_SUCCESS:
                        logger.info(f"CANFD Init Success: {serial_number} Ch{channel}")
                        self.use_canfd[serial_number] = True
                        self.can_initialized[key] = {'initialized': True, 'baud_rate': baud_rate}
                        
                        try:
                            CANFDFilter = CANFD_FILTER_CONFIG()
                            CANFDFilter.Enable = 1
                            CANFDFilter.Index = 0
                            CANFDFilter.ID_Accept = 0
                            CANFDFilter.ID_Mask = 0
                            ret_filter = CANFD_SetFilter(handle, channel, byref(CANFDFilter), 1)
                            print(f"CANFD_SetFilter returned: {ret_filter}")
                            
                            CANFD_StartGetMsg(handle, channel)
                        except Exception as e:
                            print(f"Error setting CANFD filter: {e}")
                            # 过滤器设置失败不影响CAN初始化
                            
                        return True
                    else:
                        print(f"CANFD Init failed with return code: {ret}")
                except Exception as e:
                    print(f"Error during CANFD initialization: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 2. Fallback to Classic CAN
            print(f"Attempting Classic CAN Init on {serial_number} Ch{channel}...")
            try:
                CANConfig = CAN_INIT_CONFIG()
                CANConfig.CAN_Mode = 0
                CANConfig.CAN_ABOM = 0
                CANConfig.CAN_NART = 1
                CANConfig.CAN_RFLM = 0
                CANConfig.CAN_TXFP = 1
                CANConfig.CAN_BRP_CFG3 = 25
                CANConfig.CAN_BS1_CFG1 = 6
                CANConfig.CAN_BS2_CFG2 = 1
                CANConfig.CAN_SJW = 1
                
                ret = CAN_Init(handle, channel, byref(CANConfig))
                print(f"CAN_Init returned: {ret} (CAN_SUCCESS={CAN_SUCCESS})")
                if ret == CAN_SUCCESS:
                    print(f"Classic CAN Init Success: {serial_number} Ch{channel}")
                    self.use_canfd[serial_number] = False
                    self.can_initialized[key] = {'initialized': True, 'baud_rate': baud_rate}
                    
                    try:
                        CANFilter = CAN_FILTER_CONFIG()
                        CANFilter.Enable = 1
                        CANFilter.ExtFrame = 0
                        CANFilter.FilterIndex = 0
                        CANFilter.FilterMode = 0
                        CANFilter.MASK_IDE = 0
                        CANFilter.MASK_RTR = 0
                        CANFilter.MASK_Std_Ext = 0
                        ret_filter = CAN_Filter_Init(handle, channel, byref(CANFilter))
                        print(f"CAN_Filter_Init returned: {ret_filter}")
                        
                        if 'CAN_StartGetMsg' in globals():
                            CAN_StartGetMsg(handle, channel)
                    except Exception as e:
                        print(f"Error setting CAN filter: {e}")
                        # 过滤器设置失败不影响CAN初始化
                        
                    return True
                else:
                    print(f"Classic CAN Init failed with return code: {ret}")
            except Exception as e:
                print(f"Error during Classic CAN initialization: {e}")
                import traceback
                traceback.print_exc()
                
            return False
        except Exception as e:
            print(f"Error initializing CAN {serial_number} Ch{channel}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def auto_connect(self):
        """兼容旧接口: 扫描设备"""
        self.scan_devices()

    def send_power_command(self, power_watt, channel=0, serial_number=None):
        """发送功率控制命令 (0x4E0)"""
        # 如果没有指定SN，使用第一个可用的 (兼容旧代码，但不推荐)
        if not serial_number:
            if not self.handles:
                return False
            serial_number = list(self.handles.keys())[0]

        handle = self.get_device_handle(serial_number)
        if not handle:
            return False
            
        # Ensure initialized
        if not self.initialize_can(serial_number, channel):
            return False
            
        lock = self.device_locks.get(serial_number)
        if not lock:
            return False
            
        lock.acquire()
        try:
            return self._send_power_impl(handle, channel, serial_number, power_watt)
        finally:
            lock.release()

    def _send_power_impl(self, handle, channel, serial_number, power_watt):
        try:
            enable_cmd = 1 if power_watt > 0 else 0
            power_value = min(int(power_watt), 10000)
            
            data = [0]*8
            data[2] = (power_value >> 8) & 0xFF
            data[3] = power_value & 0xFF
            data[6] = 0x40 if enable_cmd else 0x00
            
            use_fd = self.use_canfd.get(serial_number, False)
            
            if use_fd:
                CanMsg = (CANFD_MSG*1)()
                CanMsg[0].ID = 0x4E0
                CanMsg[0].DLC = 8
                CanMsg[0].Flags = 0x00
                for i in range(8):
                    CanMsg[0].Data[i] = data[i]
                ret = CANFD_SendMsg(handle, channel, CanMsg, 1)
            else:
                CanMsg = (CAN_MSG*1)()
                CanMsg[0].ExternFlag = 0
                CanMsg[0].RemoteFlag = 0
                CanMsg[0].ID = 0x4E0
                CanMsg[0].DataLen = 8
                for i in range(8):
                    CanMsg[0].Data[i] = data[i]
                ret = CAN_SendMsg(handle, channel, CanMsg, 1)
                
            return ret > 0
        except Exception as e:
            print(f"Send error: {e}")
            return False

    def receive_message(self, channel=0, serial_number=None):
        """接收CAN消息 (兼容旧接口，但建议改用 receive_messages)"""
        msgs = self.receive_messages(channel, serial_number)
        if msgs and len(msgs) > 0:
            return msgs[0] # Return first message only (WARNING: Potential data loss if caller doesn't handle burst)
        return None

    def receive_messages(self, channel=0, serial_number=None):
        """接收CAN消息（批量）"""
        # 如果没有指定SN，使用第一个可用的 (兼容旧代码，但不推荐)
        if not serial_number:
            if not self.handles:
                return []
            serial_number = list(self.handles.keys())[0]

        handle = self.get_device_handle(serial_number)
        if not handle:
            return []
            
        # Use RLock to prevent race conditions during receive
        lock = self.device_locks.get(serial_number)
        if not lock:
            print(f"Error: Lock not found for device {serial_number}")
            return []
            
        lock.acquire()
        try:
            return self._receive_messages_impl(handle, channel, serial_number)
        finally:
            lock.release()

    def receive_messages_non_blocking(self, channel=0, serial_number=None):
        """非阻塞接收CAN消息，减少锁持有时间"""
        # 如果没有指定SN，使用第一个可用的
        if not serial_number:
            if not self.handles:
                return []
            serial_number = list(self.handles.keys())[0]

        # 直接从handles字典中获取句柄，不调用get_device_handle
        # 这样可以避免在接收消息时重新打开设备
        handle = self.handles.get(serial_number)
        if not handle:
            # 如果句柄不存在，才调用get_device_handle
            handle = self.get_device_handle(serial_number)
            if not handle:
                return []
            
        # 尝试获取锁，如果锁被占用则立即返回空列表
        lock = self.device_locks.get(serial_number)
        if not lock:
            # 如果锁不存在，创建一个新的锁
            lock = threading.RLock()
            self.device_locks[serial_number] = lock
            
        if not lock.acquire(blocking=False):
            # 锁被占用，不等待，直接返回空列表
            return []
            
        try:
            return self._receive_messages_impl(handle, channel, serial_number)
        except Exception as e:
            print(f"Error in non-blocking receive: {e}")
            # 如果发生异常，可能是句柄失效，尝试重新获取句柄
            try:
                # 释放锁后重新获取句柄
                lock.release()
                # 重新获取句柄
                new_handle = self.get_device_handle(serial_number)
                if new_handle:
                    # 重新获取锁
                    if lock.acquire(blocking=False):
                        try:
                            return self._receive_messages_impl(new_handle, channel, serial_number)
                        finally:
                            lock.release()
            except Exception as e2:
                print(f"Error recovering from handle failure: {e2}")
            return []
        finally:
            # 确保锁被释放
            if lock._is_owned():
                lock.release()

    def _receive_messages_impl(self, handle, channel, serial_number):
        messages = []
        try:
            use_fd = self.use_canfd.get(serial_number, False)
            
            if use_fd:
                CanMsgBuffer = (CANFD_MSG*100)() # Increase buffer size
                CanNum = CANFD_GetMsg(handle, channel, byref(CanMsgBuffer), 100)
                if CanNum > 0:
                    for i in range(CanNum):
                        messages.append({
                            "id": CanMsgBuffer[i].ID,
                            "data": list(CanMsgBuffer[i].Data[:CanMsgBuffer[i].DLC]),
                            "length": CanMsgBuffer[i].DLC,
                            "timestamp": datetime.now()
                        })
            else:
                CanMsgBuffer = (CAN_MSG*100)() # Increase buffer size
                CanNum = CAN_GetMsg(handle, channel, byref(CanMsgBuffer), 100, 0) # No timeout inside lock
                if CanNum > 0:
                    for i in range(CanNum):
                        messages.append({
                            "id": CanMsgBuffer[i].ID,
                            "data": list(CanMsgBuffer[i].Data[:CanMsgBuffer[i].DataLen]),
                            "length": CanMsgBuffer[i].DataLen,
                            "timestamp": datetime.now()
                        })
        except Exception as e:
            print(f"Error receiving messages: {e}")
            # 如果发生异常，可能是句柄失效，尝试从handles中移除该设备
            if serial_number in self.handles:
                print(f"Removing invalid handle for device {serial_number}")
                del self.handles[serial_number]
            pass
        return messages

    # Properties for backward compatibility (pointing to first device)
    @property
    def device_connected(self):
        return len(self.handles) > 0


    def parse_ptc_message(self, message):
        """解析PTC相关消息 (Motorola / Big Endian)"""
        if not message:
            return None
        
        can_id = message["id"]
        data = message["data"]
        
        try:
            if can_id == 0x524:
                # 解析0x524消息 (Big Endian)
                error_level = (data[2] >> 6) & 0x03
                error_code = data[2] & 0x3F
                actual_power = (data[4] << 8) | data[5]
                ptc_temp = data[6] - 48
                ptc_init_status = (data[7] >> 0) & 0x01
                ptc_hv_power_status = (data[7] >> 1) & 0x01
                
                return {
                    "type": "PTC_524",
                    "error_level": error_level,
                    "error_code": error_code,
                    "actual_power": actual_power,
                    "temperature": ptc_temp,
                    "init_status": ptc_init_status,
                    "hv_power_status": ptc_hv_power_status
                }
        
            elif can_id == 0x525:
                # 解析0x525消息 (Big Endian)
                ptc_pcbt = data[2] - 48
                actual_current = ((data[3] << 8) | data[4]) * 0.001
                actual_voltage = (data[6] << 8) | data[7]
                
                return {
                    "type": "PTC_525",
                    "pcbt": ptc_pcbt,
                    "current": actual_current,
                    "voltage": actual_voltage
                }
        except Exception as e:
            print(f"Parse error: {e}")
            
        return None

    def check_fault(self, ptc_data):
        if not ptc_data: return None
        error_code = ptc_data.get("error_code", 0)
        error_level = ptc_data.get("error_level", 0)
        if error_code > 0:
            fault_info = FAULT_CODES.get(error_code, {"name": f"未知故障 {error_code}", "level": error_level})
            return {"code": error_code, "level": error_level, "name": fault_info["name"], "timestamp": datetime.now()}
        return None

    def close(self):
        """关闭所有打开的设备"""
        for serial, handle in self.handles.items():
            try:
                USB_CloseDevice(handle)
                print(f"Closed device {serial}")
            except:
                pass
        self.handles.clear()
        self.can_initialized.clear()

# 全局CAN管理器实例
can_manager = None

def init_can_manager():
    global can_manager
    can_manager = CANManager()
    return can_manager

def get_can_manager():
    global can_manager
    if can_manager is None:
        can_manager = CANManager()
    return can_manager
