import unittest
from unittest.mock import patch

import usb2lin_ex
from a050_protocol import A050Status
# Load the local manager before the USB wrapper adds the CAN project path.
from lin_device_manager import LinDeviceManager  # noqa: F401
from lin_service import LinDeviceConfig, LinService
from usb2lin_ex import LIN_EX_MSG


class A050LinServiceTests(unittest.TestCase):
    def test_project_usb2lin_compatibility_wrapper_is_loaded(self):
        self.assertTrue(hasattr(usb2lin_ex, "_MODULE"))

    def test_initialize_passes_channel_and_12v_to_power_control(self):
        service = LinService(
            LinDeviceConfig("SN_A", 1, 19200, "A050"),
            handle=123,
        )
        calls = []

        def fake_call(operation, _func, *args):
            calls.append((operation, args))
            return 0

        with patch("lin_service._call_native", side_effect=fake_call):
            with patch("lin_service.time.sleep"):
                service.initialize()

        self.assertTrue(service.is_ready)
        self.assertEqual(calls[0][0], "LIN_EX_CtrlPowerOut")
        self.assertEqual(calls[0][1], (123, 1, 1))

    def test_read_status_combines_measurement_and_fault_frames(self):
        service = LinService(
            LinDeviceConfig("SN_A", 0, 19200, "A050"),
            handle=1,
        )
        service._initialized = True
        service.send_break = lambda: None  # type: ignore[method-assign]
        requested_pids = []

        def fake_master_sync(pid, _payload, _msg_type):
            requested_pids.append(pid)
            out_msg = LIN_EX_MSG()
            data = [100, 50, 45, 55, 60, 65, 8, 0x73] if pid == 0x37 else [0] * 8
            out_msg.DataLen = len(data)
            for index, value in enumerate(data):
                out_msg.Data[index] = value
            return 1, out_msg

        service._master_sync = fake_master_sync  # type: ignore[method-assign]

        status = service.read_status()

        self.assertIsInstance(status, A050Status)
        self.assertEqual(status.measurement.power_feedback_w, 400)
        self.assertFalse(status.fault.has_fault)
        self.assertEqual(requested_pids, [0x37, 0x39])

    def test_exchange_status_writes_command_then_reads_both_status_frames(self):
        service = LinService(
            LinDeviceConfig("SN_A", 0, 19200, "A050"),
            handle=1,
        )
        service._initialized = True
        service.send_break = lambda: None  # type: ignore[method-assign]
        requested_pids = []

        def fake_master_sync(pid, _payload, _msg_type):
            requested_pids.append(pid)
            out_msg = LIN_EX_MSG()
            if pid == 0x37:
                data = [100, 50, 45, 55, 60, 65, 8, 0x73]
            elif pid == 0x39:
                data = [0] * 8
            else:
                data = []
            out_msg.DataLen = len(data)
            for index, value in enumerate(data):
                out_msg.Data[index] = value
            return 1, out_msg

        service._master_sync = fake_master_sync  # type: ignore[method-assign]

        status = service.exchange_status(1, 0)

        self.assertIsInstance(status, A050Status)
        self.assertEqual(requested_pids, [0x36, 0x37, 0x39])


if __name__ == "__main__":
    unittest.main()
