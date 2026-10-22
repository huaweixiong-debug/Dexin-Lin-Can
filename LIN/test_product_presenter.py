"""Tests for product_presenter.py."""
from __future__ import annotations

import unittest

from a045_protocol import A045Status, build_command_payload, parse_status_payload
from a050_protocol import A050MeasurementStatus, A050Status, parse_fault_payload
from product_presenter import (
    RuntimeStatus,
    adapt_status,
    build_command,
    extract_step_power,
    present_status,
    present_summary,
    status_signature,
)
from runtime_protocols import RuntimeProtocolError

_UKN = "A099"  # truly unknown product


class Base:
    def setUp(self):
        self.a045_status = parse_status_payload([2, 3, 50, 60, 70, 0x21, 0x11, 30])
        self.a050_status = A050MeasurementStatus(
            high_voltage_v=448.0,
            electrical_current_a=12.5,
            core_temperature_1_c=35,
            core_temperature_2_c=38,
            pcb_temperature_c=42,
            igbt_temperature_c=55,
            power_feedback_w=2500,
            software_version=2,
            hardware_version=1,
            raw_payload=[0x70, 0x32, 0x4B, 0x4E, 0x4A, 0x4D, 0x50, 0x21],
        )
        self.command_payload = [0, 0, 100, 0, 100, 0, 1, 0]


# ------------------------------------------------------------------
# A045 tests (existing behavior preserved)
# ------------------------------------------------------------------

class A045PresenterTests(Base, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.code = "A045"

    def test_adapt_status(self):
        rs = adapt_status(self.a045_status, self.code)
        self.assertIsInstance(rs, RuntimeStatus)
        self.assertEqual(rs.left_power_w, 50)
        self.assertEqual(rs.right_power_w, 75)
        self.assertEqual(rs.hv_voltage_v, 120)

    def test_adapt_wrong_type_raises(self):
        with self.assertRaises(TypeError):
            adapt_status(self.a050_status, self.code)

    def test_build_command(self):
        result = build_command(50, self.code)
        self.assertEqual(result, build_command_payload(50))

    def test_present_status(self):
        rs = adapt_status(self.a045_status, self.code)
        line = present_status(rs, self.command_payload, self.code)
        self.assertIn("run=", line)
        self.assertIn("left_power=", line)
        self.assertIn("hv=", line)
        self.assertIn("tx26=", line)
        self.assertIn("rx27=", line)

    def test_present_summary(self):
        rs = adapt_status(self.a045_status, self.code)
        step = {"name": "Step1", "power_ratio": 80}
        line = present_summary(1, step, rs, 500, 600, self.code)
        self.assertIn("max_left=500W", line)
        self.assertIn("end_run=", line)

    def test_present_summary_none(self):
        step = {"name": "Step1", "power_ratio": 80}
        line = present_summary(1, step, None, 0, 0, self.code)
        self.assertIn("result=no_valid_status", line)

    def test_extract_step_power(self):
        rs = adapt_status(self.a045_status, self.code)
        left, right = extract_step_power(rs, self.code)
        self.assertEqual(left, 50)
        self.assertEqual(right, 75)

    def test_status_signature(self):
        rs = adapt_status(self.a045_status, self.code)
        sig = status_signature(rs, self.code)
        self.assertEqual(len(sig), 6)


# ------------------------------------------------------------------
# A050 tests
# ------------------------------------------------------------------

class A050PresenterTests(Base, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.code = "A050"

    # adapt_status
    def test_adapt_measurement_to_runtime(self):
        rs = adapt_status(self.a050_status, self.code)
        self.assertIsInstance(rs, RuntimeStatus)
        self.assertEqual(rs.left_power_w, 2500)
        self.assertEqual(rs.right_power_w, 2500)
        self.assertEqual(rs.left_temperature_c, 35)
        self.assertEqual(rs.right_temperature_c, 38)
        self.assertEqual(rs.pcb_igbt_temperature_c, 42)
        self.assertEqual(rs.hv_voltage_v, 448)
        self.assertEqual(rs.run_status_text, "unknown")

    def test_adapt_combined_status_includes_fault_frame(self):
        fault = parse_fault_payload([0, 0b00000001, 0, 0, 0, 0, 0, 0])
        rs = adapt_status(A050Status(self.a050_status, fault), self.code)

        self.assertEqual(rs.error_level, 1)
        self.assertEqual(rs.error_level_text, "fault")
        self.assertNotEqual(rs.error_code, 0)

    def test_adapt_wrong_type_raises(self):
        with self.assertRaises(TypeError):
            adapt_status(self.a045_status, self.code)

    # build_command
    def test_build_command_zero_power(self):
        result = build_command(0, self.code)
        self.assertEqual(result[0], 0x00)

    def test_build_command_positive_power(self):
        result = build_command(100, self.code)
        self.assertEqual(result[0], 0x01)
        self.assertGreater(result[1], 0)

    # present_status
    def test_present_status(self):
        rs = adapt_status(self.a050_status, self.code)
        line = present_status(rs, self.command_payload, self.code)
        self.assertIn("run=", line)
        self.assertIn("left_power=", line)
        self.assertIn("right_power=", line)
        self.assertIn("left_temp=", line)
        self.assertIn("right_temp=", line)
        self.assertIn("pcb_temp=", line)
        self.assertIn("hv=", line)
        self.assertIn("tx36=", line)
        self.assertIn("rx37=", line)

    def test_degraded_operation_is_named_without_zero_fault_code(self):
        fault = parse_fault_payload([0b00000001, 0, 0, 0, 0, 0, 0, 0])
        rs = adapt_status(A050Status(self.a050_status, fault), self.code)

        line = present_status(rs, self.command_payload, self.code)

        self.assertEqual(rs.error_level_text, "degraded_operation")
        self.assertIn("fault=degraded_operation ", line)
        self.assertNotIn("fault/0x0", line)

    def test_reserved_operation_status_is_not_presented_as_fault(self):
        fault = parse_fault_payload([0b00000010, 0, 0, 0, 0, 0, 0, 0])
        rs = adapt_status(A050Status(self.a050_status, fault), self.code)

        line = present_status(rs, self.command_payload, self.code)

        self.assertEqual(rs.run_status_text, "reserved_2")
        self.assertEqual(rs.error_level, 0)
        self.assertEqual(rs.error_level_text, "normal")
        self.assertIn("fault=normal/0x0", line)

    # present_summary
    def test_present_summary(self):
        rs = adapt_status(self.a050_status, self.code)
        step = {"name": "Step1", "power_ratio": 80}
        line = present_summary(1, step, rs, 3000, 3000, self.code)
        self.assertIn("max_power=3000W", line)
        self.assertIn("end_temp1=35C", line)

    def test_present_summary_none(self):
        step = {"name": "Step1", "power_ratio": 80}
        line = present_summary(1, step, None, 0, 0, self.code)
        self.assertIn("result=no_valid_status", line)

    # extract_step_power
    def test_extract_step_power(self):
        rs = adapt_status(self.a050_status, self.code)
        left, right = extract_step_power(rs, self.code)
        self.assertEqual(left, 2500)
        self.assertEqual(right, 2500)

    # status_signature
    def test_status_signature(self):
        rs = adapt_status(self.a050_status, self.code)
        sig = status_signature(rs, self.code)
        self.assertEqual(len(sig), 6)


# ------------------------------------------------------------------
# Unknown product tests
# ------------------------------------------------------------------

class UnknownPresenterTests(Base, unittest.TestCase):
    def test_adapt_unknown_raises(self):
        with self.assertRaises(RuntimeProtocolError):
            adapt_status(self.a045_status, _UKN)

    def test_build_command_unknown_raises(self):
        with self.assertRaises(RuntimeProtocolError):
            build_command(50, _UKN)

    def test_present_status_unknown_raises(self):
        rs = adapt_status(self.a045_status, "A045")
        with self.assertRaises(RuntimeProtocolError):
            present_status(rs, self.command_payload, _UKN)

    def test_present_summary_unknown_raises(self):
        rs = adapt_status(self.a045_status, "A045")
        with self.assertRaises(RuntimeProtocolError):
            present_summary(1, {"name":"x","power_ratio":0}, rs, 0, 0, _UKN)

    def test_extract_step_power_unknown_raises(self):
        rs = adapt_status(self.a045_status, "A045")
        with self.assertRaises(RuntimeProtocolError):
            extract_step_power(rs, _UKN)

    def test_signature_unknown_raises(self):
        rs = adapt_status(self.a045_status, "A045")
        with self.assertRaises(RuntimeProtocolError):
            status_signature(rs, _UKN)


if __name__ == "__main__":
    unittest.main()
