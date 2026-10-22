import unittest

from a050_protocol import (
    MAX_POWER_REQUEST_W,
    POWER_STEP_W,
    ProtocolError,
    build_command_payload,
    build_command_payload_from_ratio,
    parse_fault_payload,
    parse_measurement_payload,
)


class A050ProtocolTests(unittest.TestCase):
    def test_build_command_payload_encodes_engage_and_power_steps(self):
        payload = build_command_payload(500)

        self.assertEqual(len(payload), 8)
        self.assertEqual(payload[0], 0x01)
        self.assertEqual(payload[1], 10)
        self.assertEqual(payload[2:], [0x00] * 6)

    def test_build_command_payload_disengages_at_zero_power(self):
        payload = build_command_payload(0)

        self.assertEqual(payload[0], 0x00)
        self.assertEqual(payload[1], 0x00)

    def test_build_command_payload_from_ratio_maps_shared_sequence_values(self):
        self.assertEqual(build_command_payload_from_ratio(0)[:2], [0x00, 0x00])
        self.assertEqual(build_command_payload_from_ratio(1)[:2], [0x01, 0x02])
        self.assertEqual(build_command_payload_from_ratio(50)[:2], [0x01, 0x7F])
        self.assertEqual(build_command_payload_from_ratio(100)[:2], [0x01, 0xFF])

        with self.assertRaises(ProtocolError):
            build_command_payload_from_ratio(101)

    def test_build_command_payload_rejects_invalid_power_requests(self):
        with self.assertRaises(ProtocolError):
            build_command_payload(-POWER_STEP_W)

        with self.assertRaises(ProtocolError):
            build_command_payload(125)

        with self.assertRaises(ProtocolError):
            build_command_payload(MAX_POWER_REQUEST_W + POWER_STEP_W)

    def test_parse_measurement_payload_decodes_scaled_values(self):
        status = parse_measurement_payload([100, 50, 45, 55, 60, 65, 8, 0x73])

        self.assertEqual(status.high_voltage_v, 250.0)
        self.assertEqual(status.electrical_current_a, 10.0)
        self.assertEqual(status.core_temperature_1_c, 5)
        self.assertEqual(status.core_temperature_2_c, 15)
        self.assertEqual(status.pcb_temperature_c, 20)
        self.assertEqual(status.igbt_temperature_c, 25)
        self.assertEqual(status.power_feedback_w, 400)
        self.assertEqual(status.software_version, 0x03)
        self.assertEqual(status.hardware_version, 0x07)

    def test_parse_fault_payload_decodes_bit_fields(self):
        # byte0: operation=1, hv_error=2, lv_error=1
        # byte1: bits 8,11,15 set
        # byte2: bits 16,17,18 set and igbt_error=2
        status = parse_fault_payload([0b00011001, 0b10001001, 0b00010111, 0, 0, 0, 0, 0])

        self.assertEqual(status.operation_status, 1)
        self.assertEqual(status.operation_status_text, "degraded_operation")
        self.assertEqual(status.hv_voltage_error_text, "undervoltage")
        self.assertEqual(status.lv_voltage_error_text, "overvoltage")
        self.assertTrue(status.overcurrent)
        self.assertFalse(status.core_temp_1_sensor_error)
        self.assertTrue(status.core_temp_1_overtemp)
        self.assertTrue(status.pcb_temp_overtemp)
        self.assertTrue(status.igbt_temp_overtemp)
        self.assertTrue(status.response_error)
        self.assertTrue(status.interlock_error)
        self.assertEqual(status.igbt_error, 2)
        self.assertEqual(status.igbt_error_text, "igbt_open_circuit")
        self.assertTrue(status.has_fault)
        self.assertNotEqual(status.fault_code, 0)

    def test_zero_fault_payload_is_normal(self):
        status = parse_fault_payload([0] * 8)

        self.assertFalse(status.has_fault)
        self.assertEqual(status.fault_code, 0)

    def test_reserved_operation_status_is_not_fault_by_itself(self):
        status = parse_fault_payload([0b00000010, 0, 0, 0, 0, 0, 0, 0])

        self.assertEqual(status.operation_status, 2)
        self.assertEqual(status.operation_status_text, "reserved_2")
        self.assertFalse(status.operation_status_has_fault)
        self.assertFalse(status.has_fault)
        self.assertEqual(status.fault_code, 0)


if __name__ == "__main__":
    unittest.main()
