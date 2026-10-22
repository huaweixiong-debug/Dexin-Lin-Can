import unittest

from settings_ui import SettingsApp


class A050DashboardParsingTests(unittest.TestCase):
    def test_extracts_a050_status_using_dashboard_fields(self):
        line = (
            "[STATUS] run=normal_operation fault=normal/0x0 "
            "left_power=250W right_power=250W left_temp=35C right_temp=36C "
            "pcb_temp=34C hv=452.0V"
        )

        values = SettingsApp._extract_status_fields(None, line)

        self.assertEqual(values["run"], "normal_operation")
        self.assertEqual(values["left_power"], "250W")
        self.assertEqual(values["right_temp"], "36C")
        self.assertEqual(values["pcb_temp"], "34C")

    def test_parses_a050_step_summary(self):
        line = (
            "[STEP_SUMMARY] step=1 name=A050 Step power_ratio=100 "
            "max_power=12750W end_power=12000W end_hv=450.0V "
            "end_temp1=95C end_temp2=96C"
        )

        values = SettingsApp._parse_summary_line(None, line)

        self.assertIsNotNone(values)
        self.assertEqual(values["max_left"], "12750W")
        self.assertEqual(values["end_right"], "12000W")
        self.assertEqual(values["end_hv"], "450.0V")


if __name__ == "__main__":
    unittest.main()
