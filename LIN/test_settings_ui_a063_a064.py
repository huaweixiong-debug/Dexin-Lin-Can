import unittest

from a063_protocol import combine_status, parse_aux_status_payload, parse_status_payload
from a064_protocol import parse_status_payload as parse_a064_status_payload
from product_presenter import adapt_status, build_command, present_status, present_summary
from settings_ui import SettingsApp

A063_08 = [0x01, 0x00, 0x78, 0xD2, 0x07, 0xDC, 0x05, 0x00]
A063_0A = [0x50, 0x00, 0x00, 0x78, 0x0A, 0x0A, 0x78, 0x00]
A064_16 = [0x6E, 0x82, 0x78, 0x64, 0x01, 0x00, 0x78, 0x00]


class A063A064DashboardParsingTests(unittest.TestCase):
    def test_extracts_a063_status_fields_from_presented_line(self):
        raw = combine_status(parse_status_payload(A063_08), parse_aux_status_payload(A063_0A))
        line = present_status(adapt_status(raw, "A063"), build_command(100, "A063"), "A063")

        values = SettingsApp._extract_status_fields(None, line)

        self.assertEqual(values["run"], "running")
        self.assertEqual(values["fault"], "normal/0x0")
        self.assertEqual(values["left_power"], "1500W")
        self.assertEqual(values["right_power"], "0W")
        self.assertEqual(values["left_temp"], "80C")
        self.assertEqual(values["right_temp"], "40C")
        self.assertEqual(values["hv"], "440V")

    def test_extracts_a064_status_fields_from_presented_line(self):
        line = present_status(adapt_status(parse_a064_status_payload(A064_16), "A064"), build_command(100, "A064"), "A064")

        values = SettingsApp._extract_status_fields(None, line)

        self.assertEqual(values["run"], "running")
        self.assertEqual(values["fault"], "normal/0x0")
        self.assertEqual(values["left_power"], "5720W")
        self.assertEqual(values["pcb_temp"], "80C")
        self.assertEqual(values["hv"], "440V")

    def test_parses_a063_and_a064_step_summaries(self):
        raw = combine_status(parse_status_payload(A063_08), parse_aux_status_payload(A063_0A))
        cases = (
            ("A063", adapt_status(raw, "A063"), 1500, 0),
            ("A064", adapt_status(parse_a064_status_payload(A064_16), "A064"), 5720, 5720),
        )
        for code, status, max_left, max_right in cases:
            line = present_summary(2, {"name": f"{code} Step", "power_ratio": 100}, status, max_left, max_right, code)

            values = SettingsApp._parse_summary_line(None, line)

            self.assertIsNotNone(values, code)
            assert values is not None
            self.assertEqual(values["step"], "2")
            self.assertEqual(values["max_left"], f"{max_left}W")
            self.assertEqual(values["max_right"], f"{max_right}W")
            self.assertEqual(values["end_run"], "running")
            self.assertEqual(values["end_hv"], "440V")


if __name__ == "__main__":
    unittest.main()
