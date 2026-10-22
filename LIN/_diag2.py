from lin_device_manager import lin_device_manager

lin_device_manager.close_all()
all_sns = [
    '30415455003330355300035A','30415455003330355300021B',
    '30415455003330355300023E','304154550033303553000239',
    '30415455003330355300023B','30415455003330355300023C',
]
lin_device_manager.open_all_devices(all_sns)

# 先启动工位 1（35A Index 0）
print('Starting station 1 (35A/0)...')
svc1 = lin_device_manager.ensure_channel_initialized('30415455003330355300035A', 0, 19200)
s1 = svc1.exchange_status(100, 0.08)
print(f'  OK run={s1.run_status_text} left_power={s1.left_power_w}W')

# 工位 1 运行中，再启动工位 5（23E Index 0）
print('Starting station 5 (23E/0) while station 1 is up...')
svc5 = lin_device_manager.ensure_channel_initialized('30415455003330355300023E', 0, 19200)
s5 = svc5.exchange_status(100, 0.08)
print(f'  OK run={s5.run_status_text} left_power={s5.left_power_w}W')

lin_device_manager.close_all()
