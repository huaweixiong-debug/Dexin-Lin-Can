import json
import tempfile
import unittest
from pathlib import Path

from config_store import ConfigError, load_config, save_config, switch_product, validate_config


def _base_config(product="A045"):
    return {
        "product": product,
        "active_station_slot": 1,
        "device": {"lin_sn": "SN_A", "lin_index": 0, "baud_rate": 19200},
        "plc": {"enabled": True, "plc1_ip": "192.168.10.180", "plc2_ip": "192.168.10.181"},
        "scan": {"scan_start": True},
        "stations": [
            {"slot": 1, "name": "工位 1", "enabled": True, "lin_sn": "SN_A", "lin_index": 0, "scanner_ip": "192.168.10.164:8888"},
            {"slot": 2, "name": "工位 2", "enabled": True, "lin_sn": "SN_A", "lin_index": 1, "scanner_ip": "192.168.10.165:8888"},
        ],
        "timing": {"send_interval_ms": 100, "read_interval_ms": 20, "watchdog_sec": 5},
        "step_plan": {
            "cooldown_duration_sec": 10,
            "steps": [{"name": "A045 Step", "power_ratio": 100, "duration_sec": 70}],
        },
    }


class ProductProfileTests(unittest.TestCase):
    def test_legacy_config_gets_active_product_profile(self):
        config = validate_config(_base_config())

        self.assertEqual(list(config["product_profiles"].keys()), ["A045"])
        profile = config["product_profiles"]["A045"]
        self.assertEqual(profile["baud_rate"], 19200)
        self.assertEqual(profile["timing"]["send_interval_ms"], 100)
        self.assertEqual(profile["step_plan"]["steps"][0]["name"], "A045 Step")

    def test_top_level_values_override_stale_active_profile(self):
        raw = _base_config()
        raw["product_profiles"] = {
            "A045": {
                "baud_rate": 9600,
                "timing": {"send_interval_ms": 500, "read_interval_ms": 50, "watchdog_sec": 9},
                "step_plan": {"cooldown_duration_sec": 1, "steps": [{"name": "old", "power_ratio": 10, "duration_sec": 1}]},
            }
        }

        config = validate_config(raw)

        self.assertEqual(config["product_profiles"]["A045"]["baud_rate"], 19200)
        self.assertEqual(config["product_profiles"]["A045"]["step_plan"]["steps"][0]["name"], "A045 Step")

    def test_switch_to_new_product_keeps_current_values_and_stores_outgoing_profile(self):
        config = switch_product(_base_config(), "A063")

        self.assertEqual(config["product"], "A063")
        self.assertEqual(config["step_plan"]["steps"][0]["name"], "A045 Step")
        self.assertEqual(set(config["product_profiles"]), {"A045", "A063"})

    def test_switching_restores_each_products_own_steps_and_timing(self):
        a063 = switch_product(_base_config(), "A063")
        a063["timing"]["send_interval_ms"] = 200
        a063["step_plan"] = {
            "cooldown_duration_sec": 5,
            "steps": [
                {"name": "A063 双区 100%", "power_ratio": 100, "duration_sec": 600},
                {"name": "A063 双区 50%", "power_ratio": 50, "duration_sec": 300},
            ],
        }
        a063.pop("sequence")

        a064 = switch_product(a063, "A064")
        a064["device"]["baud_rate"] = 9600
        a064["step_plan"] = {"cooldown_duration_sec": 0, "steps": [{"name": "A064 100%", "power_ratio": 100, "duration_sec": 900}]}
        a064.pop("sequence")

        back_to_a063 = switch_product(a064, "A063")
        self.assertEqual(back_to_a063["timing"]["send_interval_ms"], 200)
        self.assertEqual(back_to_a063["device"]["baud_rate"], 19200)
        self.assertEqual([step["name"] for step in back_to_a063["step_plan"]["steps"]], ["A063 双区 100%", "A063 双区 50%"])
        self.assertEqual(back_to_a063["sequence"][1], {"name": "Cooldown 1", "power_ratio": 0, "duration_sec": 5.0})

        back_to_a064 = switch_product(back_to_a063, "A064")
        self.assertEqual(back_to_a064["device"]["baud_rate"], 9600)
        self.assertEqual(back_to_a064["step_plan"]["steps"][0]["name"], "A064 100%")

        back_to_a045 = switch_product(back_to_a064, "A045")
        self.assertEqual(back_to_a045["timing"]["send_interval_ms"], 100)
        self.assertEqual(back_to_a045["step_plan"]["steps"][0]["name"], "A045 Step")

    def test_switch_keeps_shared_station_plc_and_scan_settings(self):
        original = validate_config(_base_config())
        switched = switch_product(_base_config(), "A064")

        self.assertEqual(switched["stations"], original["stations"])
        self.assertEqual(switched["plc"], original["plc"])
        self.assertEqual(switched["scan"], original["scan"])
        self.assertEqual(switched["active_station_slot"], original["active_station_slot"])

    def test_switch_rejects_unknown_product(self):
        with self.assertRaises(ConfigError):
            switch_product(_base_config(), "A099")

    def test_invalid_profile_is_rejected_and_unknown_codes_are_dropped(self):
        raw = _base_config()
        raw["product_profiles"] = {"A099": {"timing": {}}, "A064": {"baud_rate": 19200, "timing": {"send_interval_ms": 0}}}
        with self.assertRaises(ConfigError):
            validate_config(raw)

        raw["product_profiles"] = {"A099": {"timing": {}}}
        self.assertEqual(set(validate_config(raw)["product_profiles"]), {"A045"})

    def test_profiles_survive_save_and_load(self):
        config = switch_product(switch_product(_base_config(), "A063"), "A064")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(path, config)
            stored = json.loads(path.read_text(encoding="utf-8"))
            reloaded = validate_config(load_config(path))

        self.assertEqual(list(stored["product_profiles"].keys()), ["A045", "A063", "A064"])
        self.assertEqual(reloaded["product_profiles"], config["product_profiles"])


if __name__ == "__main__":
    unittest.main()
