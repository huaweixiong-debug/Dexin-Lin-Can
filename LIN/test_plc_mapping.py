import unittest

from plc_service import PLC_STATUS_BITS, decode_station_signals, get_station_plc_mapping


class PLCMappingTests(unittest.TestCase):
    def test_station_status_and_start_mapping_matches_opc_tags(self):
        self.assertEqual(get_station_plc_mapping(1), ("PLC1", 0, 0))
        self.assertEqual(get_station_plc_mapping(5), ("PLC1", 4, 4))
        self.assertEqual(get_station_plc_mapping(6), ("PLC2", 0, 0))
        self.assertEqual(get_station_plc_mapping(10), ("PLC2", 4, 4))

    def test_status_bits_match_opc_tags(self):
        self.assertEqual(
            PLC_STATUS_BITS,
            {
                "SCAN_OK": 0,
                "PASS": 1,
                "FAIL": 2,
                "COMM_RESTART": 3,
                "COMM_RESTART_DONE": 4,
                "RESET": 5,
            },
        )

    def test_station_signal_bits_are_decoded_from_m0_m17_m20(self):
        m_data = bytearray(21)
        m_data[0] = (1 << 3) | (1 << 5)  # M0.3 communication restart, M0.5 reset
        m_data[17] = 1 << 0  # M17.0 heartbeat
        m_data[20] = 1 << 0  # M20.0 start

        self.assertEqual(
            decode_station_signals(m_data, 0),
            {"start": True, "reset": True, "comm_restart": True, "heartbeat": True},
        )

    def test_invalid_station_is_rejected(self):
        with self.assertRaises(ValueError):
            get_station_plc_mapping(0)
        with self.assertRaises(ValueError):
            get_station_plc_mapping(11)


if __name__ == "__main__":
    unittest.main()
