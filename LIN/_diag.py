from lin_device_manager import lin_device_manager

lin_device_manager.close_all()
print('All closed')

all_sns = [
    '30415455003330355300035A',
    '30415455003330355300021B',
    '30415455003330355300023E',
    '304154550033303553000239',
    '30415455003330355300023B',
    '30415455003330355300023C',
]
lin_device_manager.open_all_devices(all_sns)
print('open_all_devices done')

for sn in all_sns:
    entry = lin_device_manager.device_catalog.get(sn, {})
    print(f'  SN={sn[-4:]} opened={entry.get("opened")} handle={entry.get("handle")}')

print()
print('Trying 35A channel 0...')
svc = lin_device_manager.ensure_channel_initialized('30415455003330355300035A', 0, 19200)
status = svc.exchange_status(100, 0.08)
print(f'run={status.run_status_text} left_power={status.left_power_w}W')

lin_device_manager.close_all()
