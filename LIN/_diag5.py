from lin_device_manager import lin_device_manager

lin_device_manager.close_all()

# 同时打开所有
all_sns = ['30415455003330355300035A','30415455003330355300021B',
           '30415455003330355300023E','304154550033303553000239',
           '30415455003330355300023B','30415455003330355300023C']
lin_device_manager.open_all_devices(all_sns)

# 测 35A
svc1 = lin_device_manager.ensure_channel_initialized('30415455003330355300035A', 0, 19200)
s1 = svc1.exchange_status(100, 0.15)
print(f'35A: OK run={s1.run_status_text} left_power={s1.left_power_w}W hv={s1.hv_voltage_v}V')

# 测 23E（35A 保持打开）
svc5 = lin_device_manager.ensure_channel_initialized('30415455003330355300023E', 0, 19200)
s5 = svc5.exchange_status(100, 0.15)
print(f'23E: OK run={s5.run_status_text} left_power={s5.left_power_w}W hv={s5.hv_voltage_v}V')

lin_device_manager.close_all()
