import unittest

from a064_protocol import (
    FAULT_BITS,
    ProtocolError,
    build_command_payload,
    describe_fault_code,
    parse_status_payload,
)

# Sample frame from A063_A064_老化信号定义表.xlsx sheet "报文示例".
STATUS_16_SAMPLE = [0x6E, 0x82, 0x78, 0x64, 0x02, 0x00, 0x78, 0x00]


class A064ProtocolTests(unittest.TestCase):
    def test_build_command_payload_matches_sample_frames(self):
        self.assertEqual(build_command_payload(0), [0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(build_command_payload(100), [0x64, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(build_command_payload(50), [0x32, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def test_build_command_payload_rejects_out_of_range(self):
        with self.assertRaises(ProtocolError):
            build_command_payload(101)
        with self.assertRaises(ProtocolError):
            build_command_payload(-1)

    def test_parse_status_payload_decodes_sample(self):
        # Data[4]=0x02 sets bit33 (FaultState) per the bit layout, so the
        # sample's "Status=1, no fault" note is checked with 0x01 instead.
        payload = list(STATUS_16_SAMPLE)
        payload[4] = 0x01
        status = parse_status_payload(payload)

        self.assertEqual(status.bus_voltage_v, 440)
        self.assertEqual(status.bus_current_a, 13.0)
        self.assertEqual(status.temperature_c, 80)
        self.assertEqual(status.heat_power_ratio, 100)
        self.assertEqual(status.status, 1)
        self.assertEqual(status.igbt_temperature_c, 80)
        self.assertFalse(status.has_fault)
        self.assertEqual(status.run_status_text, "running")
        self.assertEqual(status.measured_power_w, 5720)

    def test_sample_byte4_0x02_decodes_as_fault_state(self):
        status = parse_status_payload(STATUS_16_SAMPLE)

        self.assertEqual(status.status, 0)
        self.assertEqual(status.fault_names, ["fault_state"])

    def test_each_fault_bit_maps_to_its_name(self):
        for index, (start_bit, name) in enumerate(FAULT_BITS):
            payload = [0x00] * 8
            payload[start_bit // 8] |= 1 << (start_bit % 8)
            status = parse_status_payload(payload)
            self.assertEqual(status.fault_code, 1 << index, name)
            self.assertEqual(status.fault_names, [name])
            self.assertEqual(status.run_status_text, "fault")

    def test_describe_fault_code_handles_zero(self):
        self.assertEqual(describe_fault_code(0), [])

    def test_parse_rejects_wrong_length(self):
        with self.assertRaises(ProtocolError):
            parse_status_payload([0] * 9)


if __name__ == "__main__":
    unittest.main()
