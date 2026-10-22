from lin_device_manager import lin_device_manager
import time

STATIONS = [
    (1, "30415455003330355300035A", 0),
    (2, "30415455003330355300035A", 1),
    (3, "30415455003330355300021B", 0),
    (4, "30415455003330355300021B", 1),
    (5, "30415455003330355300023E", 0),
    (6, "304154550033303553000239", 0),
    (7, "30415455003330355300023B", 0),
    (8, "30415455003330355300023B", 1),
    (9, "30415455003330355300023C", 0),
    (10, "30415455003330355300023C", 1),
]

ok = []; fail = []
for slot, sn, idx in STATIONS:
    lin_device_manager.close_all()
    time.sleep(0.2)
    try:
        svc = lin_device_manager.ensure_channel_initialized(sn, idx, 19200)
        s = svc.exchange_status(100, 0.15)
        print(f"  [{slot:2d}] {sn[-4:]}/{idx}  OK  run={s.run_status_text}  left={s.left_power_w}W  hv={s.hv_voltage_v}V")
        ok.append(slot)
    except Exception as e:
        print(f"  [{slot:2d}] {sn[-4:]}/{idx}  FAIL  {str(e)[:80]}")
        fail.append(slot)

print(f"\nResult: {len(ok)}/10 OK ({ok}), {len(fail)}/10 FAIL ({fail})")
