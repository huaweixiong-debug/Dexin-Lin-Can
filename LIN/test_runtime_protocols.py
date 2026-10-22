import unittest

from runtime_protocols import RuntimeProtocolError, get_runtime_protocol


class RuntimeProtocolTests(unittest.TestCase):
    def test_a045_runtime_protocol_is_available(self):
        protocol = get_runtime_protocol("A045")

        self.assertEqual(protocol.product_code, "A045")
        self.assertEqual(protocol.command_pid, 0x26)
        self.assertEqual(protocol.status_pid, 0x27)
        self.assertEqual(protocol.frame_size, 8)

    def test_a050_runtime_protocol_is_available(self):
        protocol = get_runtime_protocol("A050")

        self.assertEqual(protocol.product_code, "A050")
        self.assertEqual(protocol.command_pid, 0x36)
        self.assertEqual(protocol.status_pid, 0x37)
        self.assertEqual(protocol.aux_status_pid, 0x39)
        self.assertEqual(protocol.frame_size, 8)
        self.assertEqual(protocol.build_command_payload(100)[:2], [0x01, 0xFF])
        self.assertIsNotNone(protocol.parse_aux_status_payload)
        self.assertIsNotNone(protocol.combine_status)

    def test_unknown_runtime_protocol_is_rejected(self):
        with self.assertRaises(RuntimeProtocolError):
            get_runtime_protocol("A099")


if __name__ == "__main__":
    unittest.main()
