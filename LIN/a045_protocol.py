"""A045 LIN protocol encode/decode helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List

COMMAND_PID = 0x26
STATUS_PID = 0x27
FRAME_SIZE = 8
MIN_POWER_RATIO = 0
MAX_POWER_RATIO = 100


class ProtocolError(Exception):
    """Raised when payload data violates the A045 protocol contract."""


@dataclass
class A045Status:
    left_power_w: int
    right_power_w: int
    left_temperature_c: int
    right_temperature_c: int
    pcb_igbt_temperature_c: int
    run_status: int
    run_status_text: str
    error_level: int
    error_level_text: str
    error_code: int
    hv_voltage_v: int
    raw_payload: List[int]

    def to_dict(self) -> dict:
        return asdict(self)


RUN_STATUS_MAP = {
    0: "off",
    1: "running",
    2: "fault",
    3: "reserved",
}

ERROR_LEVEL_MAP = {
    0: "normal",
    1: "minor_fault",
    2: "general_fault",
    3: "critical_fault",
}

ERROR_CODE_MAP = {
    0x00: "no_fault",
    0x01: "high_voltage_undervoltage",
    0x02: "high_voltage_overvoltage",
    0x03: "low_voltage_undervoltage",
    0x04: "low_voltage_overvoltage",
    0x05: "pcb_temp_sensor_short",
    0x06: "pcb_temp_sensor_open",
    0x07: "pcb_temp_sensor_overtemp",
    0x08: "igbt_temp_sensor_short",
    0x09: "igbt_temp_sensor_open",
    0x0A: "igbt_temp_sensor_overtemp",
    0x0B: "left_ptc_temp_sensor_short",
    0x0C: "left_ptc_temp_sensor_open",
    0x0D: "left_ptc_temp_sensor_overtemp",
    0x0E: "right_ptc_temp_sensor_short",
    0x0F: "right_ptc_temp_sensor_open",
    0x10: "right_ptc_temp_sensor_overtemp",
    0x11: "communication_error",
    0x12: "left_igbt_short",
    0x13: "right_igbt_short",
    0x14: "left_igbt_open",
    0x15: "right_igbt_open",
    0x16: "overcurrent_fault",
    0x17: "left_ptc_overload_fault",
    0x18: "right_ptc_overload_fault",
}


def validate_power_ratio(power_ratio: int) -> int:
    if not isinstance(power_ratio, int):
        raise ProtocolError(f"power_ratio must be int, got {type(power_ratio).__name__}")
    if power_ratio < MIN_POWER_RATIO or power_ratio > MAX_POWER_RATIO:
        raise ProtocolError(
            f"power_ratio must be between {MIN_POWER_RATIO} and {MAX_POWER_RATIO}, got {power_ratio}"
        )
    return power_ratio


def build_command_payload(power_ratio: int) -> List[int]:
    validated_ratio = validate_power_ratio(power_ratio)
    payload = [0x00] * FRAME_SIZE
    payload[2] = validated_ratio
    payload[4] = validated_ratio
    payload[6] = 0x01 if validated_ratio > 0 else 0x00
    return payload


def parse_status_payload(payload: Iterable[int]) -> A045Status:
    data = [int(byte) & 0xFF for byte in payload]
    if len(data) != FRAME_SIZE:
        raise ProtocolError(f"status payload must be {FRAME_SIZE} bytes, got {len(data)}")

    run_status = data[5] & 0x03
    error_level = (data[5] >> 4) & 0x03
    error_code = data[6]

    return A045Status(
        left_power_w=data[0] * 25,
        right_power_w=data[1] * 25,
        left_temperature_c=data[2] - 40,
        right_temperature_c=data[3] - 40,
        pcb_igbt_temperature_c=data[4] - 40,
        run_status=run_status,
        run_status_text=RUN_STATUS_MAP.get(run_status, f"unknown_{run_status}"),
        error_level=error_level,
        error_level_text=ERROR_LEVEL_MAP.get(error_level, f"unknown_{error_level}"),
        error_code=error_code,
        hv_voltage_v=data[7] * 4,
        raw_payload=data,
    )


def describe_error_code(error_code: int) -> str:
    return ERROR_CODE_MAP.get(error_code, f"unknown_fault_{error_code:#04x}")


def format_payload_hex(payload: Iterable[int]) -> str:
    return " ".join(f"{int(byte) & 0xFF:02X}" for byte in payload)
