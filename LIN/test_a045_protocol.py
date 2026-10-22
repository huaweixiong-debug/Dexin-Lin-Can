import unittest

from a045_protocol import ProtocolError, build_command_payload, parse_status_payload


class A045ProtocolTests(unittest.TestCase):
    def test_build_command_payload_uses_same_ratio_on_left_and_right(self):
        payload = build_command_payload(55)

        self.assertEqual(len(payload), 8)
        self.assertEqual(payload[2], 55)
        self.assertEqual(payload[4], 55)
        self.assertEqual(payload[6], 0x01)

    def test_build_command_payload_disables_mode_when_ratio_is_zero(self):
        payload = build_command_payload(0)
        self.assertEqual(payload[2], 0)
        self.assertEqual(payload[4], 0)
        self.assertEqual(payload[6], 0x00)

    def test_build_command_payload_rejects_out_of_range_ratio(self):
        with self.assertRaises(ProtocolError):
            build_command_payload(-1)

        with self.assertRaises(ProtocolError):
            build_command_payload(101)

    def test_parse_status_payload_decodes_fields(self):
        status = parse_status_payload([2, 3, 50, 60, 70, 0x21, 0x11, 30])

        self.assertEqual(status.left_power_w, 50)
        self.assertEqual(status.right_power_w, 75)
        self.assertEqual(status.left_temperature_c, 10)
        self.assertEqual(status.right_temperature_c, 20)
        self.assertEqual(status.pcb_igbt_temperature_c, 30)
        self.assertEqual(status.run_status, 1)
        self.assertEqual(status.error_level, 2)
        self.assertEqual(status.error_code, 0x11)
        self.assertEqual(status.hv_voltage_v, 120)


if __name__ == "__main__":
    unittest.main()
