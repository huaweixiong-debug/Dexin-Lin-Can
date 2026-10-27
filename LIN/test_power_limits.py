import unittest

from config_store import ConfigError, _build_sequence_from_step_plan, _normalize_step_plan
from power_limits import check_power_lower, check_power_upper


class StepPlanLimitTests(unittest.TestCase):
    def test_limits_are_normalized_and_default_to_zero(self):
        plan = _normalize_step_plan(
            {
                "step_plan": {
                    "cooldown_duration_sec": 2,
                    "steps": [
                        {
                            "name": "S1",
                            "power_ratio": 100,
                            "duration_sec": 10,
                            "power_min_w": 1300,
                            "power_max_w": 1700,
                        },
                        {"name": "S2", "power_ratio": 50, "duration_sec": 10},
                    ],
                }
            }
        )

        self.assertEqual(plan["steps"][0]["power_min_w"], 1300)
        self.assertEqual(plan["steps"][0]["power_max_w"], 1700)
        self.assertEqual(plan["steps"][1]["power_min_w"], 0)
        self.assertEqual(plan["steps"][1]["power_max_w"], 0)

    def test_limits_are_carried_into_runtime_sequence(self):
        plan = _normalize_step_plan(
            {
                "step_plan": {
                    "cooldown_duration_sec": 2,
                    "steps": [
                        {
                            "name": "S1",
                            "power_ratio": 100,
                            "duration_sec": 10,
                            "power_min_w": 1300,
                            "power_max_w": 1700,
                        }
                    ],
                }
            }
        )

        sequence = _build_sequence_from_step_plan(plan)

        self.assertEqual(sequence[0]["power_min_w"], 1300)
        self.assertEqual(sequence[0]["power_max_w"], 1700)

    def test_inverted_limits_are_rejected(self):
        with self.assertRaises(ConfigError):
            _normalize_step_plan(
                {
                    "step_plan": {
                        "steps": [
                            {
                                "name": "S1",
                                "power_ratio": 100,
                                "duration_sec": 10,
                                "power_min_w": 2000,
                                "power_max_w": 1000,
                            }
                        ]
                    }
                }
            )

    def test_negative_limits_are_rejected(self):
        with self.assertRaises(ConfigError):
            _normalize_step_plan(
                {
                    "step_plan": {
                        "steps": [
                            {
                                "name": "S1",
                                "power_ratio": 100,
                                "duration_sec": 10,
                                "power_min_w": -1,
                            }
                        ]
                    }
                }
            )


class PowerLimitCheckTests(unittest.TestCase):
    def test_upper_limit(self):
        step = {"power_max_w": 1600}

        self.assertIsNone(check_power_upper(step, 1500, 1500))
        self.assertIn("左区", check_power_upper(step, 1700, 1500))
        self.assertIn("右区", check_power_upper(step, 1500, 1700))
        self.assertIsNone(check_power_upper({}, 9999, 9999))

    def test_lower_limit_uses_steady_average(self):
        step = {"power_min_w": 1300}

        self.assertIsNone(check_power_lower(step, 1300, 1300, 10))
        self.assertIn("左区", check_power_lower(step, 1200, 1400, 10))
        self.assertIn("右区", check_power_lower(step, 1400, 1200, 10))
        self.assertIsNone(check_power_lower(step, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
