
import time
from ctypes import *
from usb_device import *
from usb2canfd import *

def log(msg):
    print(f"[Verify] {msg}")

def verify_ptc():
    # 1. Scan Device
    DevHandles = (c_uint * 20)()
    ret = USB_ScanDevice(byref(DevHandles))
    if ret <= 0:
        log("No device found")
        return
    
    dev_handle = DevHandles[0]
    log(f"Opened device: {dev_handle}")
    
    if not USB_OpenDevice(dev_handle):
        log("Failed to open device")
        return

    try:
        # 2. Initialize Channel 0 (Found active in diagnose)
        CHANNEL = 0
        log(f"Initializing Channel {CHANNEL}...")
        
        CANFDConfig = CANFD_INIT_CONFIG()
        CANFDConfig.Mode = 0 # Normal
        CANFDConfig.ISOCRCEnable = 1
        CANFDConfig.RetrySend = 1
        CANFDConfig.ResEnable = 1
        
        # 40MHz Clock, 500k Baud (BRP=10)
        CANFDConfig.NBT_BRP = 10
        CANFDConfig.NBT_SEG1 = 6
        CANFDConfig.NBT_SEG2 = 1
        CANFDConfig.NBT_SJW = 1
        
        CANFDConfig.DBT_BRP = 10
        CANFDConfig.DBT_SEG1 = 6
        CANFDConfig.DBT_SEG2 = 1
        CANFDConfig.DBT_SJW = 1
        
        ret = CANFD_Init(dev_handle, CHANNEL, byref(CANFDConfig))
        if ret != CANFD_SUCCESS:
            log(f"Init failed: {ret}")
            return

        # 3. Filter Config
        CANFDFilter = CANFD_FILTER_CONFIG()
        CANFDFilter.Enable = 1
        CANFDFilter.Index = 0
        CANFDFilter.ID_Accept = 0
        CANFDFilter.ID_Mask = 0 # Accept All
        ret = CANFD_SetFilter(dev_handle, CHANNEL, byref(CANFDFilter), 1)
        if ret != CANFD_SUCCESS:
            log(f"Filter failed: {ret}")
            return
            
        # 4. Start Receiving (CRITICAL STEP)
        ret = CANFD_StartGetMsg(dev_handle, CHANNEL)
        if ret != CANFD_SUCCESS:
            log(f"StartGetMsg failed: {ret}")
            return
            
        log("Listening for PTC Data (0x524, 0x525)...")
        
        # 5. Loop
        start_time = time.time()
        msg_count_524 = 0
        msg_count_525 = 0
        
        # Buffer
        CanMsgBuffer = (CANFD_MSG * 100)()
        
        # Send Keep-Alive (0x4E0) every 100ms
        last_send = 0
        
        while time.time() - start_time < 10: # Run for 10 seconds
            # Send 0x4E0
            if time.time() - last_send > 0.1:
                SendMsg = (CANFD_MSG * 1)()
                SendMsg[0].ID = 0x4E0
                SendMsg[0].DLC = 8
                SendMsg[0].Flags = 0x00 # Standard CAN
                # Enable=1, Power=0 for test
                SendMsg[0].Data[6] = 0x40 
                CANFD_SendMsg(dev_handle, CHANNEL, SendMsg, 1)
                last_send = time.time()
            
            # Read
            num = CANFD_GetMsg(dev_handle, CHANNEL, byref(CanMsgBuffer), 100)
            if num > 0:
                for i in range(num):
                    msg = CanMsgBuffer[i]
                    
                    if msg.ID == 0x524:
                        msg_count_524 += 1
                        # Parse Power (Bytes 4-5) - Big Endian
                        # Data[4] MSB, Data[5] LSB
                        raw_pwr = (msg.Data[4] << 8) | msg.Data[5]
                        log(f"RX 0x524 | Power Raw: {msg.Data[4]:02X} {msg.Data[5]:02X} -> {raw_pwr} W")
                        
                    elif msg.ID == 0x525:
                        msg_count_525 += 1
                        # Parse Temp (Byte 2)
                        raw_temp = msg.Data[2]
                        val_temp = raw_temp - 48
                        
                        # Parse Current (Bytes 3-4) - Big Endian
                        # Data[3] MSB, Data[4] LSB
                        raw_cur = (msg.Data[3] << 8) | msg.Data[4]
                        val_cur = raw_cur * 0.001
                        
                        # Parse Voltage (Bytes 6-7) - Big Endian
                        # Data[6] MSB, Data[7] LSB
                        raw_vol = (msg.Data[6] << 8) | msg.Data[7]
                        val_vol = raw_vol
                        
                        log(f"RX 0x525 | Temp: {val_temp} C | Curr: {val_cur:.3f} A | Volt: {val_vol} V")
                        # log(f"   Raw 525: {' '.join([f'{b:02X}' for b in msg.Data[:8]])}")

            time.sleep(0.01)
            
            if msg_count_524 > 5 and msg_count_525 > 5:
                log("Received sufficient messages!")
                break
                
        if msg_count_524 == 0:
            log("Warning: No 0x524 received")
        if msg_count_525 == 0:
            log("Warning: No 0x525 received")

    finally:
        USB_CloseDevice(dev_handle)
        log("Device Closed")

if __name__ == "__main__":
    verify_ptc()
