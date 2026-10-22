from lin_device_manager import lin_device_manager
from lin_service import _call_native
from usb2lin_ex import LIN_EX_Init, LIN_EX_MASTER, LIN_EX_SUCCESS
from usb2lin_ex import LIN_EX_MSG, LIN_EX_MSG_TYPE_BK, LIN_EX_MasterSync
from ctypes import byref
import time

lin_device_manager.close_all()
devs = lin_device_manager.scan_devices_once(force=True)

for d in devs:
    sn = d['serial']
    lin_device_manager.close_all()
    time.sleep(0.1)
    handle = lin_device_manager.get_or_open_device(sn)
    print(f'\n{sn[-4:]}:')
    
    ret = _call_native('LIN_EX_Init', LIN_EX_Init, handle, 0, 19200, LIN_EX_MASTER)
    print(f'  Init idx=0: {ret}')
    
    tx = LIN_EX_MSG(); tx.MsgType = LIN_EX_MSG_TYPE_BK
    rx = LIN_EX_MSG()
    ret2 = _call_native('BREAK', LIN_EX_MasterSync, handle, 0, byref(tx), byref(rx), 1)
    print(f'  BREAK idx=0: {ret2}')

lin_device_manager.close_all()
