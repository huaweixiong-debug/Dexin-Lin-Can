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

lin_device_manager.close_all()
time.sleep(0.5)
all_sns = list(set(sn for _, sn, _ in STATIONS))
print(f'Opening {len(all_sns)} SNs...')
lin_device_manager.open_all_devices(all_sns)
for sn in all_sns:
    e = lin_device_manager.device_catalog.get(sn, {})
    print(f'  {sn[-4:]}: opened={e.get("opened")}')

print()
print('Probing (no close between)...')

for slot, sn, idx in STATIONS:
    tag = f'[{slot:2d}] {sn[-4:]}/{idx}'
    ok_attempt = None
    for attempt in range(1, 4):
        try:
            svc = lin_device_manager.ensure_channel_initialized(sn, idx, 19200)
            s = svc.exchange_status(100, 0.15)
            if ok_attempt is None:
                ok_attempt = attempt
            print(f'  {tag}  #{attempt}: OK  run={s.run_status_text}  left={s.left_power_w}W')
            break
        except Exception as e:
            print(f'  {tag}  #{attempt}: FAIL  {str(e)[:90]}')
    print()

lin_device_manager.close_all()
