"""A064 (rear APTC, single zone) LIN protocol encode/decode helpers.

Derived from A063_A064_老化信号定义表.xlsx (sheet "A064报文") and the rear
VF8/VF9 EE communication matrix. The aging rig plays the BCM role: it publishes
0x15 and reads the 0x16 status frame.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List

COMMAND_PID = 0x15
STATUS_PID = 0x16
FRAME_SIZE = 8
MIN_POWER_RATIO = 0
MAX_POWER_RATIO = 100
# Rated 13 A @ 440 V, so 100 % = 5720 W.
RATED_POWER_W = 5720

PTC_ON_REQ_OFF = 0x1
PTC_ON_REQ_ON = 0x2

RUN_STATUS_MAP = {
    0: "off",
    1: "running",
    2: "fault",
}

# 0x16 fault bits in frame order, starting at linear bit 33.
FAULT_BITS = (
    (33, "fault_state"),
    (34, "lin_com_error"),
    (35, "overcurrent"),
    (36, "lv_undervoltage"),
    (37, "lv_overvoltage"),
    (38, "igbt_temp_sensor_error"),
    (39, "igbt_overtemp"),
    (40, "temp_sensor_error"),
    (41, "overtemp"),
    (42, "hv_undervoltage"),
    (43, "hv_overvoltage"),
    (44, "short_circuit"),
    (45, "open_circuit"),
    (46, "response_error"),
)


class ProtocolError(Exception):
    """Raised when payload data violates the A064 protocol contract."""


@dataclass
class A064Status:
    bus_voltage_v: int
    bus_current_a: float
    temperature_c: int
    heat_power_ratio: int
    status: int
    igbt_temperature_c: int
    fault_code: int
    raw_payload: List[int]

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def has_fault(self) -> bool:
        return self.fault_code != 0

    @property
    def fault_names(self) -> List[str]:
        return describe_fault_code(self.fault_code)

    @property
    def measured_power_w(self) -> int:
        return int(round(self.bus_voltage_v * self.bus_current_a))

    @property
    def run_status(self) -> int:
        if self.has_fault:
            return 2
        return 1 if self.status else 0

    @property
    def run_status_text(self) -> str:
        return RUN_STATUS_MAP[self.run_status]


def validate_power_ratio(power_ratio: int) -> int:
    if not isinstance(power_ratio, int):
        raise ProtocolError(f"power_ratio must be int, got {type(power_ratio).__name__}")
    if power_ratio < MIN_POWER_RATIO or power_ratio > MAX_POWER_RATIO:
        raise ProtocolError(
            f"power_ratio must be between {MIN_POWER_RATIO} and {MAX_POWER_RATIO}, got {power_ratio}"
        )
    return power_ratio


def build_command_payload(power_ratio: int) -> List[int]:
    """Encode 0x15: HeatingReq (7 bit %) in byte0, OnReq (2 bit) in byte1."""
    validated_ratio = validate_power_ratio(power_ratio)
    payload = [0x00] * FRAME_SIZE
    payload[0] = validated_ratio & 0x7F
    payload[1] = PTC_ON_REQ_ON if validated_ratio > 0 else PTC_ON_REQ_OFF
    return payload


def parse_status_payload(payload: Iterable[int]) -> A064Status:
    data = _normalize_payload(payload)
    fault_code = 0
    for index, (start_bit, _name) in enumerate(FAULT_BITS):
        fault_code |= _extract_bits(data, start_bit, 1) << index
    return A064Status(
        bus_voltage_v=data[0] * 4,
        bus_current_a=round(data[1] * 0.1, 1),
        temperature_c=data[2] - 40,
        heat_power_ratio=data[3],
        status=_extract_bits(data, 32, 1),
        igbt_temperature_c=data[6] - 40,
        fault_code=fault_code,
        raw_payload=data,
    )


def describe_fault_code(fault_code: int) -> List[str]:
    return [name for index, (_bit, name) in enumerate(FAULT_BITS) if fault_code & (1 << index)]


def format_payload_hex(payload: Iterable[int]) -> str:
    return " ".join(f"{int(byte) & 0xFF:02X}" for byte in payload)


def _normalize_payload(payload: Iterable[int]) -> List[int]:
    data = [int(byte) & 0xFF for byte in payload]
    if len(data) != FRAME_SIZE:
        raise ProtocolError(f"payload must be {FRAME_SIZE} bytes, got {len(data)}")
    return data


def _extract_bits(payload: List[int], start_bit: int, bit_length: int) -> int:
    value = 0
    for offset in range(bit_length):
        absolute_bit = start_bit + offset
        byte_index = absolute_bit // 8
        bit_index = absolute_bit % 8
        bit_value = (payload[byte_index] >> bit_index) & 0x01
        value |= bit_value << offset
    return value
