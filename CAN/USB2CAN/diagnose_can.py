
import time
from ctypes import *
from usb_device import *
from usb2canfd import *

def log(msg):
    print(f"[Diagnostic] {msg}")

def test_config(dev_handle, channel, clock_freq_mhz, baud_rate=500000, mode=0):
    mode_str = "Loopback" if mode == 1 else "Normal"
    log(f"Testing Channel {channel} with assumed Clock {clock_freq_mhz}MHz, Baud {baud_rate}, Mode {mode_str}...")
    
    # 1. Initialize
    CANFDConfig = CANFD_INIT_CONFIG()
    CANFDConfig.Mode = mode  # 0-Normal, 1-Loopback
    CANFDConfig.ISOCRCEnable = 1
    CANFDConfig.RetrySend = 1
    CANFDConfig.ResEnable = 1 # Enable Termination
    
    # Calculate BRP based on clock
    # Baud = Clock / BRP / (1 + SEG1 + SEG2)
    # Target 500k. Tq = 1 + 6 + 1 = 8.
    # BRP = Clock / 500k / 8
    # 40M: 40/0.5/8 = 10
    # 60M: 60/0.5/8 = 15
    
    if clock_freq_mhz == 40:
        if baud_rate == 500000:
            CANFDConfig.NBT_BRP = 10
        elif baud_rate == 250000:
            CANFDConfig.NBT_BRP = 20
        else:
            log("Unsupported baud for 40M")
            return False
    elif clock_freq_mhz == 60:
        if baud_rate == 500000:
            CANFDConfig.NBT_BRP = 15
        elif baud_rate == 250000:
            CANFDConfig.NBT_BRP = 30
        else:
            log("Unsupported baud for 60M")
            return False
    else:
        log("Unsupported clock")
        return False

    CANFDConfig.NBT_SEG1 = 6
    CANFDConfig.NBT_SEG2 = 1
    CANFDConfig.NBT_SJW = 1
    
    # Data bitrate (same for simplicity, though not used for standard frames)
    CANFDConfig.DBT_BRP = CANFDConfig.NBT_BRP
    CANFDConfig.DBT_SEG1 = 6
    CANFDConfig.DBT_SEG2 = 1
    CANFDConfig.DBT_SJW = 1
    
    ret = CANFD_Init(dev_handle, channel, byref(CANFDConfig))
    if ret != CANFD_SUCCESS:
        log(f"Init failed with error {ret}")
        return False
        
    log("Init Success. Configuring Filter...")
    
    # 2. Filter
    CANFDFilter = CANFD_FILTER_CONFIG()
    CANFDFilter.Enable = 1
    CANFDFilter.Index = 0
    CANFDFilter.ID_Accept = 0
    CANFDFilter.ID_Mask = 0 # Accept All
    ret = CANFD_SetFilter(dev_handle, channel, byref(CANFDFilter), 1)
    if ret != CANFD_SUCCESS:
        log(f"Filter config failed: {ret}")
        return False
        
    # Start Receiving
    ret = CANFD_StartGetMsg(dev_handle, channel)
    if ret != CANFD_SUCCESS:
        log(f"StartGetMsg failed: {ret}")
        return False
        
    log("Filter Configured. Starting Send/Receive Loop...")
    
    # 3. Send & Receive Loop (5 times)
    success_count = 0
    for i in range(5):
        # Send 0x4E0
        CanMsg = (CANFD_MSG*1)()
        CanMsg[0].ID = 0x4E0
        CanMsg[0].DLC = 8
        CanMsg[0].Flags = 0x00 # Standard Frame
        
        # Enable Command (Byte 6 = 0x40)
        CanMsg[0].Data[6] = 0x40 
        
        ret = CANFD_SendMsg(dev_handle, channel, CanMsg, 1)
        if ret < 0:
            log(f"Send failed: {ret}")
        else:
            log("Sent 0x4E0")
            
        # Wait a bit
        time.sleep(0.2)
        
        # Read
        CanMsgBuffer = (CANFD_MSG*100)()
        CanNum = CANFD_GetMsg(dev_handle, channel, byref(CanMsgBuffer), 100)
        if CanNum > 0:
            log(f"Received {CanNum} messages!")
            for j in range(CanNum):
                log(f"  ID: 0x{CanMsgBuffer[j].ID:X} DLC: {CanMsgBuffer[j].DLC} Data: {' '.join([f'{b:02X}' for b in CanMsgBuffer[j].Data[:CanMsgBuffer[j].DLC]])}")
                
                # Check for loopback success
                if mode == 1:
                    if CanMsgBuffer[j].ID == 0x4E0:
                        log("  -> Loopback Success! Device is healthy.")
                        return True
                        
                if CanMsgBuffer[j].ID in [0x524, 0x525]:
                    log("  -> Found Target ID!")
                    success_count += 1
        else:
            log("No messages received.")
            
    return success_count > 0

def main():
    log("Scanning for USB2XXX devices...")
    # Scan
    DevHandles = (c_uint * 20)()
    ret = USB_ScanDevice(byref(DevHandles))
    if ret <= 0:
        log("No device found")
        return
        
    handle = DevHandles[0]
    log(f"Opened device handle: {handle}")
    
    try:
        if not USB_OpenDevice(handle):
            log("Failed to open device")
            return
            
        # Test Channel 0, 40MHz, 500k, Loopback
        if test_config(handle, 0, 40, 500000, mode=1):
            log("SUCCESS with Loopback Test! Device is OK.")
        else:
            log("Loopback Test Failed! Device might be faulty or driver issue.")

        # Test Channel 0, 40MHz, 500k
        if test_config(handle, 0, 40, 500000):
            log("SUCCESS with Channel 0, 40MHz, 500k!")
            return
            
        # Test Channel 0, 60MHz, 500k
        if test_config(handle, 0, 60, 500000):
            log("SUCCESS with Channel 0, 60MHz, 500k!")
            return
            
        # Test Channel 0, 40MHz, 250k
        if test_config(handle, 0, 40, 250000):
            log("SUCCESS with Channel 0, 40MHz, 250k!")
            return

        # Test Channel 1, 40MHz, 500k
        if test_config(handle, 1, 40, 500000):
            log("SUCCESS with Channel 1, 40MHz, 500k!")
            return
            
        # Test Channel 1, 60MHz, 500k
        if test_config(handle, 1, 60, 500000):
            log("SUCCESS with Channel 1, 60MHz, 500k!")
            return

        log("All attempts failed to receive target IDs.")
        
    finally:
        USB_CloseDevice(handle)

if __name__ == "__main__":
    main()
