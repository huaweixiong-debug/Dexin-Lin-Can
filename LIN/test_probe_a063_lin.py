import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Load the local manager before the USB wrapper adds the CAN project path.
from lin_device_manager import LinDeviceManager  # noqa: F401
from lin_service import LinDeviceConfig, LinService
from probe_a063_lin import OFF_PAYLOAD, VARIANTS, Tee, exchange_raw, run_phase, summarize
from usb2lin_ex import LIN_EX_MSG


def _spec_firmware(payload):
    return payload[1] | (payload[2] << 8), payload[3] | (payload[4] << 8)


def _u8_adjacent_firmware(payload):
    return payload[1], payload[2]


class FakeA063:
    """Simulated part: heats each zone from its own reading of 0x07, reports via 0x08/0x0A."""

    def __init__(self, firmware):
        self.firmware = firmware
        self.command = list(OFF_PAYLOAD)

    def zone_powers(self):
        if not self.command[0]:
            return 0, 0
        return tuple(1500 * ratio // 100 if 0 < ratio <= 100 else 0 for ratio in self.firmware(self.command))

    def master_sync(self, pid, payload, _msg_type):
        out_msg = LIN_EX_MSG()
        power_1, power_2 = self.zone_powers()
        if pid == 0x07:
            self.command = list(payload)
            data = []
        elif pid == 0x08:
            current = round((power_1 + power_2) / 440)
            data = [int(power_1 + power_2 > 0), 0x00, 0x78, 0xD2, current, power_1 & 0xFF, power_1 >> 8, 0x00]
        else:
            data = [0x78, power_2 & 0xFF, power_2 >> 8, 0x78, 0x0A, 0x0A, 0x78, 0x00]
        out_msg.DataLen = len(data)
        for index, value in enumerate(data):
            out_msg.Data[index] = value
        return 1, out_msg


def _service_for(device):
    service = LinService(LinDeviceConfig("SN_A", 0, 19200, "A063"), handle=1)
    service._initialized = True
    service.send_break = lambda: None  # type: ignore[method-assign]
    service._master_sync = device.master_sync  # type: ignore[method-assign]
    return service


def _zones_by_variant(firmware):
    device = FakeA063(firmware)
    service = _service_for(device)
    with tempfile.TemporaryDirectory() as tmp:
        log = Tee(Path(tmp) / "probe.txt")
        with patch("builtins.print"), patch("probe_a063_lin.time.sleep"):
            results = [run_phase(service, variant, 100, 0.05, log) for variant in VARIANTS]
            summarize(results, 100, log)
        log.close()
        text = (Path(tmp) / "probe.txt").read_text(encoding="utf-8")
    zones = {}
    for variant in VARIANTS:
        match = re.search(rf"^{variant.name}\s+\S+\s+\S+\s+(\S+)", text, re.MULTILINE)
        zones[variant.name] = round(float(match.group(1)))
    return zones


class ProbeA063Tests(unittest.TestCase):
    def test_exchange_raw_writes_07_then_reads_08_and_0a(self):
        device = FakeA063(_spec_firmware)
        service = _service_for(device)
        requested = []
        original = device.master_sync

        def recording_sync(pid, payload, msg_type):
            requested.append(pid)
            return original(pid, payload, msg_type)

        service._master_sync = recording_sync  # type: ignore[method-assign]
        with patch("probe_a063_lin.time.sleep"):
            status_payload, aux_payload = exchange_raw(service, [0x01, 0x64, 0x00, 0x64, 0x00, 0, 0, 0], 0)

        self.assertEqual(requested, [0x07, 0x08, 0x0A])
        self.assertEqual(status_payload[5:7], [0xDC, 0x05])
        self.assertEqual(aux_payload[1:3], [0xDC, 0x05])

    def test_variant_frames(self):
        frames = {variant.name: variant.build(100) for variant in VARIANTS}
        self.assertEqual(frames["spec_le16"], [0x01, 0x64, 0x00, 0x64, 0x00, 0, 0, 0])
        self.assertEqual(frames["left_only"], [0x01, 0x64, 0x00, 0x00, 0x00, 0, 0, 0])
        self.assertEqual(frames["right_only"], [0x01, 0x00, 0x00, 0x64, 0x00, 0, 0, 0])
        self.assertEqual(frames["u8_adjacent"], [0x01, 0x64, 0x64, 0x00, 0x00, 0, 0, 0])
        self.assertEqual(frames["be16"], [0x01, 0x00, 0x64, 0x00, 0x64, 0, 0, 0])

    def test_summary_identifies_requirement_table_firmware(self):
        zones = _zones_by_variant(_spec_firmware)
        self.assertEqual(zones["spec_le16"], 2)
        self.assertEqual(zones["left_only"], 1)
        self.assertEqual(zones["right_only"], 1)

    def test_summary_identifies_u8_adjacent_firmware(self):
        # The suspected field symptom: the requirement-table frame only heats the left zone.
        zones = _zones_by_variant(_u8_adjacent_firmware)
        self.assertEqual(zones["spec_le16"], 1)
        self.assertEqual(zones["right_only"], 0)
        self.assertEqual(zones["u8_adjacent"], 2)


if __name__ == "__main__":
    unittest.main()
