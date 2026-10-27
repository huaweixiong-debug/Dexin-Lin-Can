"""PLC connectivity test — run on remote D:\老化LIN通讯"""
import sys
sys.path.insert(0, r'D:\老化LIN通讯')
import time

from plc_service import PLCController

plc1_ip = "192.168.8.180"
plc2_ip = "192.168.8.181"

print("=== PLC Connectivity Test ===")
plc = PLCController(plc1_ip, plc2_ip)

# Test 1: TCP layer check
import socket
for ip, name in [(plc1_ip, "PLC1"), (plc2_ip, "PLC2")]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((ip, 102))
        sock.close()
        print(f"[TCP]  {name} {ip}:102 OK")
    except Exception as e:
        print(f"[TCP]  {name} {ip}:102 FAIL ({e})")

# Test 2: snap7 connect
print("\n--- snap7 connect ---")
plc.connect()
time.sleep(1)

# Test 3: verify connection
print(f"PLC1 connected: {plc.connected1}")
print(f"PLC2 connected: {plc.connected2}")

# Test 4: read a byte from each PLC
if plc.connected1:
    try:
        data = plc.client1.read_area(plc.plc_mem_area, 0, 1, 1)
        print(f"PLC1 read station 1 byte: {data.hex() if hasattr(data,'hex') else list(data)}")
    except Exception as e:
        print(f"PLC1 read FAIL: {e}")

if plc.connected2:
    try:
        data = plc.client2.read_area(plc.plc_mem_area, 0, 1, 1)
        print(f"PLC2 read station 6 byte: {data.hex() if hasattr(data,'hex') else list(data)}")
    except Exception as e:
        print(f"PLC2 read FAIL: {e}")

# Test 5: write SCAN_OK to station 1 and read back
if plc.connected1:
    print("\n--- Write/Read test (Station 1) ---")
    from snap7.util import get_bool, set_bool
    import snap7
    mem = snap7.types.Areas.MK if hasattr(snap7.types, 'Areas') else snap7.Area.MK

    # Read current
    data = plc.client1.read_area(mem, 0, 1, 1)
    print(f"Before: SCAN_OK={get_bool(data, 0, 0)}")

    # Write True
    set_bool(data, 0, 0, True)
    plc.client1.write_area(mem, 0, 1, data)
    time.sleep(0.2)

    # Read back
    data2 = plc.client1.read_area(mem, 0, 1, 1)
    print(f"After:  SCAN_OK={get_bool(data2, 0, 0)}")

    # Restore
    set_bool(data, 0, 0, False)
    plc.client1.write_area(mem, 0, 1, data)

plc.disconnect()
print("\nDone.")
