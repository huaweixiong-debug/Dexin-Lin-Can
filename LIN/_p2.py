from lin_device_manager import lin_device_manager
import time
lin_device_manager.close_all()
time.sleep(0.1)
svc = lin_device_manager.ensure_channel_initialized('30415455003330355300035A', 1, 19200)
s = svc.exchange_status(100, 0.15)
print(f"35A/1: OK run={s.run_status_text} left={s.left_power_w}W hv={s.hv_voltage_v}V")
lin_device_manager.close_all()
