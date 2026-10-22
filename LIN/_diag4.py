from lin_device_manager import lin_device_manager

print('=== State before close_all ===')
for sn, entry in lin_device_manager.device_catalog.items():
    print(f'  {sn[-4:]}: opened={entry.get("opened")} handle={entry.get("handle")}')
print('Has open:', lin_device_manager._has_open_devices_locked())
print('Channels:', list(lin_device_manager.channel_state.keys()))

print()
print('=== close_all ===')
lin_device_manager.close_all()

print()
print('=== State after close_all ===')
for sn, entry in lin_device_manager.device_catalog.items():
    print(f'  {sn[-4:]}: opened={entry.get("opened")} handle={entry.get("handle")}')
print('Has open:', lin_device_manager._has_open_devices_locked())
print('Channels:', list(lin_device_manager.channel_state.keys()))

print()
print('=== Testing 35A direct ===')
svc = lin_device_manager.ensure_channel_initialized('30415455003330355300035A', 0, 19200)
status = svc.exchange_status(100, 0.08)
print(f'OK run={status.run_status_text} left_power={status.left_power_w}W')

lin_device_manager.close_all()
