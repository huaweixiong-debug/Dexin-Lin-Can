from lin_device_manager import lin_device_manager
from lin_service import _call_native
from usb2lin_ex import LIN_EX_MASTER, LIN_EX_SUCCESS, LIN_EX_Init
import time

lin_device_manager.close_all()
time.sleep(0.1)
devs = lin_device_manager.scan_devices_once(force=True)
print(f'Found {len(devs)} devices')

for d in devs:
    sn = d['serial']
    lin_device_manager.close_all()
    time.sleep(0.1)
    handle = lin_device_manager.get_or_open_device(sn)
    print(f'\n{sn[-4:]} handle={handle}:')
    for idx in [0, 1]:
        for baud in [19200, 9600, 10400]:
            ret = _call_native('LIN_EX_Init', LIN_EX_Init, handle, idx, baud, LIN_EX_MASTER)
            status = 'OK' if ret == LIN_EX_SUCCESS else f'FAIL({ret})'
            print(f'  idx={idx} baud={baud:5d} -> {status}')

lin_device_manager.close_all()
