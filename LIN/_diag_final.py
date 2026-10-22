from lin_device_manager import lin_device_manager
import time

lin_device_manager.close_all()
time.sleep(0.5)

# Test: open each SN individually
for sn in ["30415455003330355300023B", "30415455003330355300023C"]:
    print(f'=== {sn[-4:]} individual open ===')
    lin_device_manager.close_all()
    time.sleep(0.3)
    try:
        handle = lin_device_manager.get_or_open_device(sn)
        print(f'  opened: handle={handle}')
        print(f'  catalog: {lin_device_manager.device_catalog.get(sn)}')
    except Exception as e:
        print(f'  FAIL: {e}')

print()

# Test: open_all with debug
lin_device_manager.close_all()
time.sleep(0.5)
print('=== open_all_devices debug ===')
all_sns = [
    '30415455003330355300035A', '30415455003330355300021B',
    '30415455003330355300023E', '304154550033303553000239',
    '30415455003330355300023B', '30415455003330355300023C',
]
for sn in all_sns:
    print(f'  Trying {sn[-4:]}...')
    try:
        lin_device_manager.close_all()
        time.sleep(0.3)
        h = lin_device_manager.get_or_open_device(sn)
        svc = lin_device_manager.ensure_channel_initialized(sn, 0, 19200)
        s = svc.exchange_status(100, 0.15)
        print(f'    OK handle={h} run={s.run_status_text}')
    except Exception as e:
        print(f'    FAIL: {str(e)[:120]}')

lin_device_manager.close_all()
