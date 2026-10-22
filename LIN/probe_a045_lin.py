"""Probe USB2XXX devices/channels for A045 LIN status responses."""

from __future__ import annotations

import sys
import time

from a045_protocol import FRAME_SIZE, build_command_payload
from lin_device_manager import lin_device_manager
from lin_service import LinCommunicationError


def list_devices():
    return lin_device_manager.scan_devices_once(force=True)


def probe_device(serial: str, lin_index: int, settle_delay: float = 0.08, attempts: int = 3) -> None:
    print(f"\n[PROBE] SN={serial} lin_index={lin_index}")

    try:
        service = lin_device_manager.ensure_channel_initialized(serial, lin_index, 19200)
        for attempt in range(1, attempts + 1):
            try:
                payload = build_command_payload(100)
                status = service.exchange_status(100, settle_delay)
                print(
                    f"  attempt={attempt} OK "
                    f"payload={payload} raw={status.raw_payload} "
                    f"run={status.run_status_text} hv={status.hv_voltage_v}V "
                    f"left_power={status.left_power_w}W right_power={status.right_power_w}W"
                )
                return
            except LinCommunicationError as exc:
                print(f"  attempt={attempt} FAIL {exc}")
                time.sleep(0.05)
        print("  result=NO_RESPONSE")
    except Exception as exc:
        print(f"  init/probe failed: {exc}")


def main() -> int:
    devices = list_devices()
    if not devices:
        print("No USB2XXX devices found.")
        return 1

    print("Detected USB2XXX devices:")
    for device in devices:
        print(
            f"  scan_index={device['scan_index']} "
            f"serial={device['serial']} functions={device.get('description', '')}"
        )

    try:
        for device in devices:
            for lin_index in (0, 1):
                probe_device(device["serial"], lin_index)
    finally:
        lin_device_manager.close_all()

    return 0


if __name__ == "__main__":
    sys.exit(main())
