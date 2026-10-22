from lin_device_manager import lin_device_manager
import time

lin_device_manager.close_all()
time.sleep(0.1)

# Pre-open all 6 SNs at once (no probe interference)
all_sns = [
    '30415455003330355300035A',
    '30415455003330355300021B',
    '30415455003330355300023E',
    '304154550033303553000239',
    '30415455003330355300023B',
    '30415455003330355300023C',
]
lin_device_manager.open_all_devices(all_sns)

STATIONS = [
    (1, "30415455003330355300035A", 0),
    (2, "30415455003330355300035A", 1),
    (3, "30415455003330355300021B", 0),
    (4, "30415455003330355300021B", 1),
    (5, "30415455003330355300023E", 0),
    (6, "304154550033303553000239", 1),
    (7, "30415455003330355300023B", 0),
    (8, "30415455003330355300023B", 1),
    (9, "30415455003330355300023C", 0),
    (10, "30415455003330355300023C", 1),
]

ok = []; fail = []
for slot, sn, idx in STATIONS:
    try:
        svc = lin_device_manager.ensure_channel_initialized(sn, idx, 19200)
        s = svc.exchange_status(100, 0.15)
        print(f"  [{slot:2d}] {sn[-4:]}/{idx}  OK  run={s.run_status_text}  left={s.left_power_w}W  hv={s.hv_voltage_v}V")
        ok.append(slot)
    except Exception as e:
        print(f"  [{slot:2d}] {sn[-4:]}/{idx}  FAIL  {str(e)[:80]}")
        fail.append(slot)

lin_device_manager.close_all()
print(f"\nResult: {len(ok)}/10 OK ({ok}), {len(fail)}/10 FAIL ({fail})")
