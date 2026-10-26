import unittest
from unittest.mock import patch

from a063_protocol import A063Status, combine_status, parse_aux_status_payload, parse_status_payload
from a064_protocol import A064Status, parse_status_payload as parse_a064_status_payload
# Load the local manager before the USB wrapper adds the CAN project path.
from lin_device_manager import LinDeviceManager  # noqa: F401
from lin_service import LinDeviceConfig, LinService
from main import ProductFaultError, SequenceRunner
from product_catalog import get_product_definition
from product_presenter import adapt_status, build_command, present_status, present_summary
from runtime_protocols import get_runtime_protocol
from usb2lin_ex import LIN_EX_MSG

A063_08 = [0x01, 0x00, 0x78, 0xD2, 0x07, 0xDC, 0x05, 0x00]
A063_0A = [0x50, 0x00, 0x00, 0x78, 0x0A, 0x0A, 0x78, 0x00]
A064_16 = [0x6E, 0x82, 0x78, 0x64, 0x01, 0x00, 0x78, 0x00]


def _fake_master_sync_factory(frames, requested_pids):
    def fake_master_sync(pid, _payload, _msg_type):
        requested_pids.append(pid)
        out_msg = LIN_EX_MSG()
        data = frames.get(pid, [])
        out_msg.DataLen = len(data)
        for index, value in enumerate(data):
            out_msg.Data[index] = value
        return 1, out_msg

    return fake_master_sync


def _make_service(product_code):
    service = LinService(LinDeviceConfig("SN_A", 0, 19200, product_code), handle=1)
    service._initialized = True
    service.send_break = lambda: None  # type: ignore[method-assign]
    return service


class CatalogAndRuntimeTests(unittest.TestCase):
    def test_products_are_registered(self):
        a063 = get_product_definition("A063")
        a064 = get_product_definition("A064")
        assert a063 is not None and a064 is not None
        self.assertEqual((a063.command_pid, a063.status_pid, a063.aux_status_pid), (0x07, 0x08, 0x0A))
        self.assertEqual((a064.command_pid, a064.status_pid, a064.aux_status_pid), (0x15, 0x16, None))
        self.assertTrue(a063.runtime_supported and a064.runtime_supported)

    def test_runtime_protocols_match_catalog(self):
        a063 = get_runtime_protocol("A063")
        a064 = get_runtime_protocol("a064")
        self.assertEqual((a063.command_pid, a063.status_pid, a063.aux_status_pid), (0x07, 0x08, 0x0A))
        self.assertEqual((a064.command_pid, a064.status_pid, a064.aux_status_pid), (0x15, 0x16, None))
        self.assertEqual(a063.build_command_payload(100)[:5], [0x01, 0x64, 0x64, 0x00, 0x00])
        self.assertEqual(a064.build_command_payload(100)[:2], [0x64, 0x02])


class LinServiceTests(unittest.TestCase):
    def test_a063_exchange_writes_07_then_reads_08_and_0a(self):
        service = _make_service("A063")
        requested = []
        service._master_sync = _fake_master_sync_factory({0x08: A063_08, 0x0A: A063_0A}, requested)  # type: ignore[method-assign]

        status = service.exchange_status(100, 0)

        self.assertIsInstance(status, A063Status)
        self.assertEqual(requested, [0x07, 0x08, 0x0A])
        self.assertEqual(status.main.power_1_w, 1500)
        self.assertEqual(status.aux.temperature_2_c, 40)

    def test_a064_exchange_writes_15_then_reads_16(self):
        service = _make_service("A064")
        requested = []
        service._master_sync = _fake_master_sync_factory({0x16: A064_16}, requested)  # type: ignore[method-assign]

        status = service.exchange_status(100, 0)

        self.assertIsInstance(status, A064Status)
        self.assertEqual(requested, [0x15, 0x16])
        self.assertEqual(status.bus_voltage_v, 440)


class PresenterTests(unittest.TestCase):
    def test_a063_runtime_status_and_log_line(self):
        raw = combine_status(parse_status_payload(A063_08), parse_aux_status_payload(A063_0A))
        status = adapt_status(raw, "A063")

        self.assertEqual((status.left_power_w, status.right_power_w), (1500, 0))
        self.assertEqual((status.left_temperature_c, status.right_temperature_c), (80, 40))
        self.assertEqual(status.pcb_igbt_temperature_c, 80)
        self.assertEqual(status.hv_voltage_v, 440)

        line = present_status(status, build_command(100, "A063"), "A063")
        self.assertIn("run=running", line)
        self.assertIn("fault=normal/0x0 ", line)
        self.assertIn("current=7A", line)
        self.assertIn("igbt_temp=80C", line)
        self.assertIn("tx07=01 64 64 00 00 00 00 00", line)
        self.assertIn("rx08=01 00 78 D2 07 DC 05 00", line)

    def test_a063_fault_line_lists_fault_names(self):
        main = list(A063_08)
        main[0] |= 0x02
        main[1] = 0x40
        raw = combine_status(parse_status_payload(main), parse_aux_status_payload(A063_0A))
        status = adapt_status(raw, "A063")

        line = present_status(status, build_command(0, "A063"), "A063")
        self.assertIn("run=fault", line)
        self.assertIn("fault=fault/0x", line)
        self.assertIn(":overcurrent+error_state", line)

    def test_a064_runtime_status_and_log_line(self):
        status = adapt_status(parse_a064_status_payload(A064_16), "A064")

        self.assertEqual((status.left_power_w, status.right_power_w), (5720, 5720))
        self.assertEqual(status.pcb_igbt_temperature_c, 80)
        line = present_status(status, build_command(100, "A064"), "A064")
        self.assertIn("run=running", line)
        self.assertIn("heat_pwr=100%", line)
        self.assertIn("tx15=64 02 00 00 00 00 00 00", line)
        self.assertIn("rx16=6E 82 78 64 01 00 78 00", line)

    def test_summary_uses_dual_zone_layout(self):
        status = adapt_status(parse_a064_status_payload(A064_16), "A064")
        summary = present_summary(1, {"name": "Step 1", "power_ratio": 100}, status, 5720, 5720, "A064")
        self.assertIn("max_left=5720W max_right=5720W", summary)
        self.assertIn("end_run=running", summary)


class RunnerFaultTests(unittest.TestCase):
    def _runner(self, product_code):
        config = {
            "product": product_code,
            "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
            "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
            "sequence": [],
        }
        return SequenceRunner(
            config,
            channel_binding={"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
            log_callback=lambda _: None,
        )

    def test_a064_fault_stops_after_three_consecutive_frames(self):
        runner = self._runner("A064")
        faulty = list(A064_16)
        faulty[4] |= 0x08  # OverCurrentFault
        status = parse_a064_status_payload(faulty)

        with patch("main.lin_device_manager.exchange_status", return_value=status):
            runner._exchange_and_log_status(0.08)
            runner._exchange_and_log_status(0.08)
            with self.assertRaises(ProductFaultError):
                runner._exchange_and_log_status(0.08)

    def test_a063_single_fault_frame_is_debounced(self):
        runner = self._runner("A063")
        main = list(A063_08)
        main[0] |= 0x80  # ResponseError
        faulty = combine_status(parse_status_payload(main), parse_aux_status_payload(A063_0A))
        healthy = combine_status(parse_status_payload(A063_08), parse_aux_status_payload(A063_0A))

        with patch("main.lin_device_manager.exchange_status", side_effect=[faulty, healthy, faulty, faulty]):
            for _ in range(4):
                runner._exchange_and_log_status(0.08)


if __name__ == "__main__":
    unittest.main()
