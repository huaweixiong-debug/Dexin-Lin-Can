import unittest
from unittest.mock import patch

from a050_protocol import A050Status, parse_fault_payload, parse_measurement_payload
from main import ProductFaultError, SequenceRunner, _run_multi_station
from product_presenter import RuntimeStatus


class SequenceRunnerTests(unittest.TestCase):
    def test_multi_station_preopens_all_devices_before_initializing_channels(self):
        config = {
            "product": "A050",
            "device": {"baud_rate": 19200},
            "stations": [
                {"slot": 1, "lin_sn": "SN_A", "lin_index": 0},
                {"slot": 2, "lin_sn": "SN_A", "lin_index": 1},
                {"slot": 3, "lin_sn": "SN_B", "lin_index": 0},
            ],
        }
        events = []

        with patch(
            "main.lin_device_manager.open_all_devices",
            side_effect=lambda serials: events.append(("open", list(serials))),
        ):
            with patch(
                "main.lin_device_manager.ensure_channel_initialized",
                side_effect=lambda sn, index, baud, product: events.append(
                    ("init", sn, index, baud, product)
                ),
            ):
                with patch("main.lin_device_manager.close_all"):
                    with patch("main.SequenceRunner.run"):
                        result = _run_multi_station(config, [1, 2, 3])

        self.assertEqual(result, 0)
        self.assertEqual(events[0], ("open", ["SN_A", "SN_B"]))
        self.assertEqual([event[0] for event in events[1:]], ["init", "init", "init"])

    def test_run_sequence_uses_configured_product_code_for_step_power_extraction(self):
        config = {
            "product": "A045",
            "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
            "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
            "sequence": [{"name": "Step 1", "power_ratio": 100, "duration_sec": 0.05}],
        }
        runner = SequenceRunner(config, log_callback=lambda _: None)
        status = RuntimeStatus(
            left_power_w=500,
            right_power_w=480,
            left_temperature_c=25,
            right_temperature_c=26,
            pcb_igbt_temperature_c=27,
            run_status=1,
            run_status_text="running",
            error_level=0,
            error_level_text="normal",
            error_code=0,
            hv_voltage_v=440,
            raw_payload=[0] * 8,
        )

        with patch.object(runner, "_exchange_and_log_status", return_value=status):
            with patch("main.time.time", side_effect=[0.0, 0.0, 0.0, 0.2, 1.0, 1.0]):
                runner._run_sequence()

        self.assertEqual(runner.read_success_count, 1)
        self.assertEqual(len(runner.step_summaries), 1)
        self.assertIn("max_left=500W", runner.step_summaries[0])
        self.assertIn("max_right=480W", runner.step_summaries[0])

    def test_a050_fault_stops_the_sequence_immediately(self):
        config = {
            "product": "A050",
            "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
            "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
            "sequence": [],
        }
        runner = SequenceRunner(
            config,
            channel_binding={"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
            log_callback=lambda _: None,
        )
        status = A050Status(
            measurement=parse_measurement_payload([100, 10, 60, 60, 60, 60, 10, 0x11]),
            fault=parse_fault_payload([0, 0b00000001, 0, 0, 0, 0, 0, 0]),
        )

        with patch("main.lin_device_manager.exchange_status", return_value=status):
            with self.assertRaises(ProductFaultError):
                runner._exchange_and_log_status(0.08)


if __name__ == "__main__":
    unittest.main()
