import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from config_store import delete_template, load_template, rename_template, save_template, validate_config


class MainConfigTests(unittest.TestCase):
    def test_validate_config_accepts_known_product_for_settings(self):
        config = validate_config(
            {
                "product": "A050",
                "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "step_plan": {
                    "cooldown_duration_sec": 2,
                    "steps": [{"name": "100%", "power_ratio": 100, "duration_sec": 1}],
                },
            }
        )

        self.assertEqual(config["product"], "A050")

    def test_validate_config_accepts_step_plan_and_expands_sequence(self):
        config = validate_config(
            {
                "product": "A045",
                "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "step_plan": {
                    "cooldown_duration_sec": 2,
                    "steps": [
                        {"name": "100%", "power_ratio": 100, "duration_sec": 1},
                        {"name": "80%", "power_ratio": 80, "duration_sec": 1},
                        {"name": "50%", "power_ratio": 50, "duration_sec": 1},
                        {"name": "30%", "power_ratio": 30, "duration_sec": 1},
                        {"name": "10%", "power_ratio": 10, "duration_sec": 1},
                    ],
                },
            }
        )

        self.assertEqual(len(config["step_plan"]["steps"]), 5)
        self.assertEqual(len(config["sequence"]), 9)
        self.assertEqual(config["sequence"][0]["power_ratio"], 100)
        self.assertEqual(config["sequence"][1]["power_ratio"], 0)
        self.assertEqual(config["sequence"][1]["duration_sec"], 2)
        self.assertEqual(config["sequence"][4]["power_ratio"], 50)
        self.assertEqual(config["sequence"][8]["power_ratio"], 10)

    def test_validate_config_requires_non_empty_step_plan(self):
        with self.assertRaisesRegex(Exception, "at least one test step"):
            validate_config(
                {
                    "product": "A045",
                    "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
                    "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                    "step_plan": {"cooldown_duration_sec": 3, "steps": []},
                }
            )

    def test_validate_config_derives_step_plan_from_legacy_sequence(self):
        config = validate_config(
            {
                "product": "A045",
                "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "sequence": [
                    {"name": "100%", "power_ratio": 100, "duration_sec": 1},
                    {"name": "cooling", "power_ratio": 0, "duration_sec": 2},
                    {"name": "80%", "power_ratio": 80, "duration_sec": 1},
                ],
            }
        )

        self.assertEqual(config["step_plan"]["cooldown_duration_sec"], 2)
        self.assertEqual(len(config["step_plan"]["steps"]), 2)
        self.assertEqual(config["step_plan"]["steps"][1]["power_ratio"], 80)

    def test_validate_config_supports_ten_station_mapping_and_active_station(self):
        config = validate_config(
            {
                "product": "A045",
                "active_station_slot": 3,
                "device": {"lin_sn": "", "lin_index": 0, "baud_rate": 19200},
                "plc": {"enabled": True, "plc1_ip": "192.168.10.180", "plc2_ip": "192.168.10.181"},
                "scan": {"scan_start": True},
                "stations": [
                    {"slot": 1, "name": "工位 1", "lin_sn": "SN001", "lin_index": 0, "scanner_ip": "192.168.10.164:8888"},
                    {"slot": 3, "name": "工位 3", "lin_sn": "SN003", "lin_index": 1, "scanner_ip": "192.168.10.166:8888"},
                ],
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "step_plan": {
                    "cooldown_duration_sec": 3,
                    "steps": [{"name": "100%", "power_ratio": 100, "duration_sec": 1}],
                },
            }
        )

        self.assertEqual(config["active_station_slot"], 3)
        self.assertEqual(len(config["stations"]), 10)
        self.assertEqual(config["stations"][2]["lin_sn"], "SN003")
        self.assertEqual(config["stations"][2]["scanner_ip"], "192.168.10.166:8888")
        self.assertEqual(config["device"]["lin_sn"], "SN003")
        self.assertEqual(config["device"]["lin_index"], 1)
        self.assertTrue(config["plc"]["enabled"])
        self.assertTrue(config["scan"]["scan_start"])

    def test_validate_config_derives_station_one_from_legacy_device(self):
        config = validate_config(
            {
                "product": "A045",
                "device": {"lin_sn": "SN123", "lin_index": 2, "baud_rate": 19200},
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "step_plan": {
                    "cooldown_duration_sec": 3,
                    "steps": [{"name": "80%", "power_ratio": 80, "duration_sec": 1}],
                },
            }
        )

        self.assertEqual(config["active_station_slot"], 1)
        self.assertEqual(len(config["stations"]), 10)
        self.assertEqual(config["stations"][0]["lin_sn"], "SN123")
        self.assertEqual(config["stations"][0]["lin_index"], 2)

    def test_template_can_be_renamed_and_loaded(self):
        config = validate_config(
            {
                "product": "A045",
                "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "step_plan": {
                    "cooldown_duration_sec": 3,
                    "steps": [{"name": "100%", "power_ratio": 100, "duration_sec": 1}],
                },
            }
        )

        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            save_template(base_dir, "product_a", config)
            renamed_path = rename_template(base_dir, "product_a", "product_b")
            reloaded = load_template(base_dir, "product_b")

        self.assertTrue(renamed_path.name.endswith("product_b.json"))
        self.assertEqual(reloaded["step_plan"]["steps"][0]["power_ratio"], 100)

    def test_template_can_be_deleted(self):
        config = validate_config(
            {
                "product": "A045",
                "device": {"lin_sn": "SN123", "lin_index": 0, "baud_rate": 19200},
                "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
                "step_plan": {
                    "cooldown_duration_sec": 3,
                    "steps": [{"name": "80%", "power_ratio": 80, "duration_sec": 1}],
                },
            }
        )

        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            save_template(base_dir, "product_a", config)
            delete_template(base_dir, "product_a")

            with self.assertRaisesRegex(Exception, "Template not found"):
                load_template(base_dir, "product_a")


if __name__ == "__main__":
    unittest.main()
