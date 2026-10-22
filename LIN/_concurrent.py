from lin_device_manager import lin_device_manager
from a045_protocol import build_command_payload
import threading, time

lin_device_manager.close_all()
time.sleep(0.3)

all_sns = [
    '30415455003330355300035A','30415455003330355300021B',
    '30415455003330355300023E','304154550033303553000239',
    '30415455003330355300023B','30415455003330355300023C',
]
lin_device_manager.open_all_devices(all_sns)
for sn in all_sns:
    e = lin_device_manager.device_catalog.get(sn, {})
    print(f'  {sn[-4:]}: opened={e.get("opened")}')

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

results = {}
errors = {}
lock = threading.Lock()

def run_station(slot, sn, idx, count):
    ok = 0
    err = 0
    try:
        svc = lin_device_manager.ensure_channel_initialized(sn, idx, 19200)
        for i in range(count):
            try:
                s = svc.exchange_status(100, 0.08)
                ok += 1
            except Exception as e:
                err += 1
                if err == 1:
                    with lock:
                        print(f'  [{slot:2d}] {sn[-4:]}/{idx}  ERR #{i+1}: {str(e)[:80]}')
    except Exception as e:
        with lock:
            print(f'  [{slot:2d}] {sn[-4:]}/{idx}  INIT FAIL: {str(e)[:80]}')
    results[slot] = ok
    errors[slot] = err

print('\nRunning 10 stations x 50 exchanges in parallel...\n')

threads = []
for slot, sn, idx in STATIONS:
    t = threading.Thread(target=run_station, args=(slot, sn, idx, 50), daemon=True)
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print()
for slot, sn, idx in STATIONS:
    ok = results.get(slot, 0)
    err = errors.get(slot, 0)
    status = 'OK' if err == 0 else f'{err} ERRORS'
    print(f'  [{slot:2d}] {sn[-4:]}/{idx}  {ok}/50 OK  {status}')

lin_device_manager.close_all()
