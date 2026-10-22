import threading
import time
from ctypes import *
from usb_device import USB_ScanDevice, USB_OpenDevice, USB_CloseDevice, DEV_GetDeviceInfo, DEVICE_INFO
from logger import logger

class LINDeviceManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LINDeviceManager, cls).__new__(cls)
                    cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        
        self.device_map = {}  # Serial Number -> Device Handle
        self.scan_lock = threading.Lock()
        self.communication_lock = threading.Lock()
        self.initialized = True
        self.log("LINDeviceManager initialized")

    def log(self, message):
        logger.info(f"[LINDeviceManager] {message}")

    def get_device_handle(self, target_sn):
        """
        Get a device handle for the given Serial Number.
        If not found in cache, performs a scan.
        """
        if not target_sn:
            return None

        # First check cache (optimistic read)
        if target_sn in self.device_map:
            return self.device_map[target_sn]

        with self.scan_lock:
            # Double check inside lock
            if target_sn in self.device_map:
                return self.device_map[target_sn]

            self.log(f"Device {target_sn} not in cache, scanning USB devices...")
            self._scan_devices()
            
            if target_sn in self.device_map:
                self.log(f"Found device {target_sn} after scan. Handle: {self.device_map[target_sn]}")
                return self.device_map[target_sn]
            else:
                self.log(f"Device {target_sn} not found after scan.")
                return None

    def _scan_devices(self):
        """
        Scans all connected USB devices and updates the cache.
        Existing handles are preserved if possible.
        """
        DevHandles = (c_uint * 20)()
        ret = USB_ScanDevice(byref(DevHandles))
        self.log(f"USB Scan found {ret} devices")

        if ret == 0:
            return

        for i in range(ret):
            handle = DevHandles[i]
            
            # Check if this handle is already mapped to a known SN
            # Note: Handle values (indices) might shift if devices are replugged, 
            # so ideally we should re-verify SN. But USB_OpenDevice on an already 
            # open device might be tricky.
            # Assuming for now we can call OpenDevice safely.
            
            ret_open = USB_OpenDevice(handle)
            if ret_open:
                # Get Info
                USB2XXXInfo = DEVICE_INFO()
                USB2XXXFunctionString = (c_char * 256)()
                ret_info = DEV_GetDeviceInfo(handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                
                if ret_info:
                    serial_parts = []
                    for j in range(len(USB2XXXInfo.SerialNumber)):
                        serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                    device_serial = ''.join(serial_parts)
                    
                    # self.log(f"Device at handle {handle}: SN={device_serial}")
                    
                    # Update map
                    self.device_map[device_serial] = handle
                else:
                    self.log(f"Failed to get info for handle {handle}")
                    # Only close if we failed to identify it
                    USB_CloseDevice(handle)
            else:
                self.log(f"Failed to open handle {handle}")

    def invalidate_cache(self, sn):
        """
        Remove a device from cache, e.g. if communication fails.
        """
        with self.scan_lock:
            if sn in self.device_map:
                handle = self.device_map[sn]
                self.log(f"Invalidating cache for SN {sn} (Handle {handle})")
                try:
                    USB_CloseDevice(handle)
                except:
                    pass
                del self.device_map[sn]

# Global instance
lin_device_manager = LINDeviceManager()
