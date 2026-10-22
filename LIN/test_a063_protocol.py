import unittest

from a063_protocol import (
    ProtocolError,
    build_command_payload,
    build_command_payload_from_ratio,
    combine_status,
    describe_fault_code,
    parse_aux_status_payload,
    parse_status_payload,
)

# Sample frames from A063_A064_老化信号定义表.xlsx sheet "报文示例".
STATUS_08_SAMPLE = [0x01, 0x00, 0x78, 0xD2, 0x07, 0xDC, 0x05, 0x00]
STATUS_0A_SAMPLE = [0x50, 0x00, 0x00, 0x78, 0x0A, 0x0A, 0x78, 0x00]


class A063ProtocolTests(unittest.TestCase):
    def test_build_command_payload_matches_sample_frames(self):
        self.assertEqual(build_command_payload(0, 0), [0x00] * 8)
        self.assertEqual(build_command_payload(100, 100), [0x01, 0x64, 0x00, 0x64, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(build_command_payload(100, 0), [0x01, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(build_command_payload(0, 50), [0x01, 0x00, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00])

    def test_build_command_payload_from_ratio_drives_both_zones(self):
        self.assertEqual(build_command_payload_from_ratio(30)[:5], [0x01, 30, 0x00, 30, 0x00])
        self.assertEqual(build_command_payload_from_ratio(0)[:5], [0x00, 0x00, 0x00, 0x00, 0x00])

    def test_build_command_payload_rejects_out_of_range(self):
        with self.assertRaises(ProtocolError):
            build_command_payload_from_ratio(101)
        with self.assertRaises(ProtocolError):
            build_command_payload(-1, 0)

    def test_parse_status_payload_decodes_sample(self):
        status = parse_status_payload(STATUS_08_SAMPLE)

        self.assertEqual(status.state, 1)
        self.assertFalse(status.error_state)
        self.assertEqual(status.error_mode0, 0)
        self.assertEqual(status.error_mode1, 0)
        self.assertEqual(status.temperature_1_c, 80)
        self.assertEqual(status.bus_voltage_v, 440)
        self.assertEqual(status.bus_current_a, 7)
        self.assertEqual(status.power_1_w, 1500)
        self.assertFalse(status.lin_com_error)
        self.assertFalse(status.power_limited)

    def test_parse_aux_status_payload_decodes_sample(self):
        aux = parse_aux_status_payload(STATUS_0A_SAMPLE)

        self.assertEqual(aux.temperature_2_c, 40)
        self.assertEqual(aux.power_2_w, 0)
        self.assertEqual(aux.pcba_temperature_c, 80)
        self.assertEqual(aux.software_version, 1.0)
        self.assertEqual(aux.hardware_version, 1.0)
        self.assertEqual(aux.igbt_temperature_c, 80)
        self.assertEqual(aux.error_mode2, 0)
        self.assertFalse(aux.hv_interlock_open)

    def test_bus_voltage_special_values_read_as_zero(self):
        for raw in (0x00, 0x01):
            payload = list(STATUS_08_SAMPLE)
            payload[3] = raw
            self.assertEqual(parse_status_payload(payload).bus_voltage_v, 0)

    def test_combined_status_reports_no_fault_for_samples(self):
        status = combine_status(parse_status_payload(STATUS_08_SAMPLE), parse_aux_status_payload(STATUS_0A_SAMPLE))

        self.assertFalse(status.has_fault)
        self.assertEqual(status.run_status_text, "running")

    def test_fault_bits_are_mapped_by_name(self):
        main = list(STATUS_08_SAMPLE)
        main[0] |= 0x02 | (0x01 << 2) | 0x80  # ErrorState, ErrorMode0.bit0, ResponseError
        main[1] = 0x50  # ErrorMode1 bit4 hv_undervoltage, bit6 overcurrent
        main[7] = 0x02  # LinComError
        aux = list(STATUS_0A_SAMPLE)
        aux[7] = 0x12  # ErrorMode2 bit1 lv_overvoltage, HV_interlock open

        status = combine_status(parse_status_payload(main), parse_aux_status_payload(aux))

        self.assertTrue(status.has_fault)
        self.assertEqual(status.run_status_text, "fault")
        self.assertEqual(
            status.fault_names,
            [
                "left_igbt_short",
                "hv_undervoltage",
                "overcurrent",
                "lv_overvoltage",
                "response_error",
                "lin_com_error",
                "hv_interlock_open",
                "error_state",
            ],
        )

    def test_describe_fault_code_handles_zero(self):
        self.assertEqual(describe_fault_code(0), [])

    def test_parse_rejects_wrong_length(self):
        with self.assertRaises(ProtocolError):
            parse_status_payload([0] * 7)


if __name__ == "__main__":
    unittest.main()
