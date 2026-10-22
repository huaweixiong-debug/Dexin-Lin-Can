"""A063 (front APTC, dual zone) LIN protocol encode/decode helpers.

Derived from A063_A064_老化信号定义表.xlsx (sheet "A063报文"), which follows the
VF8/VF9 dual-zone mass-production matrix. The aging rig plays the AMP role:
it publishes 0x07 and reads the 0x08 and 0x0A status frames.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List

COMMAND_PID = 0x07
STATUS_PID = 0x08
AUX_STATUS_PID = 0x0A
FRAME_SIZE = 8
MIN_POWER_RATIO = 0
MAX_POWER_RATIO = 100
# 0x64 (100 %) equals 1500 W per zone.
ZONE_RATED_POWER_W = 1500

RUN_STATUS_MAP = {
    0: "off",
    1: "running",
    2: "fault",
}

# Bus voltage raw 0 = no HV, 1 = below 240 V, 10..250 = raw + 230 V.
BUS_VOLTAGE_RAW_NO_HV = 0
BUS_VOLTAGE_RAW_BELOW_240V = 1
BUS_VOLTAGE_OFFSET_V = 230

ERROR_MODE0_BITS = (
    "left_igbt_short",
    "left_ptc_open",
    "pcba_overtemp",
    "right_ptc_open",
    "right_igbt_short",
)

ERROR_MODE1_BITS = (
    "igbt_temp_sensor_error",
    "igbt_overtemp",
    "left_temp_sensor_error",
    "core_overtemp",
    "hv_undervoltage",
    "hv_overvoltage",
    "overcurrent",
    "right_temp_sensor_error",
)

ERROR_MODE2_BITS = (
    "lv_undervoltage",
    "lv_overvoltage",
)

# Bit layout of A063FaultStatus.fault_code (not a bus signal, used for logs).
FAULT_CODE_BITS = (
    *ERROR_MODE0_BITS,
    *ERROR_MODE1_BITS,
    *ERROR_MODE2_BITS,
    "response_error",
    "lin_com_error",
    "hv_interlock_open",
    "error_state",
)


class ProtocolError(Exception):
    """Raised when payload data violates the A063 protocol contract."""


@dataclass
class A063MainStatus:
    """Decoded 0x08 APTC_AMP frame."""

    state: int
    error_state: bool
    error_mode0: int
    response_error: bool
    error_mode1: int
    temperature_1_c: int
    bus_voltage_raw: int
    bus_voltage_v: int
    bus_current_a: int
    power_1_w: int
    lin_com_error: bool
    power_limited: bool
    raw_payload: List[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class A063AuxStatus:
    """Decoded 0x0A APTC_AMP frame."""

    temperature_2_c: int
    power_2_w: int
    pcba_temperature_c: int
    software_version: float
    hardware_version: float
    igbt_temperature_c: int
    error_mode2: int
    hv_interlock_open: bool
    raw_payload: List[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class A063Status:
    main: A063MainStatus
    aux: A063AuxStatus

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def fault_code(self) -> int:
        main = self.main
        code = main.error_mode0 & 0x1F
        code |= (main.error_mode1 & 0xFF) << 5
        code |= (self.aux.error_mode2 & 0x03) << 13
        code |= int(main.response_error) << 15
        code |= int(main.lin_com_error) << 16
        code |= int(self.aux.hv_interlock_open) << 17
        code |= int(main.error_state) << 18
        return code

    @property
    def has_fault(self) -> bool:
        return self.fault_code != 0

    @property
    def fault_names(self) -> List[str]:
        return describe_fault_code(self.fault_code)

    @property
    def run_status(self) -> int:
        if self.has_fault:
            return 2
        return 1 if self.main.state else 0

    @property
    def run_status_text(self) -> str:
        return RUN_STATUS_MAP[self.run_status]


def combine_status(main: A063MainStatus, aux: A063AuxStatus) -> A063Status:
    return A063Status(main=main, aux=aux)


def validate_power_ratio(power_ratio: int) -> int:
    if not isinstance(power_ratio, int):
        raise ProtocolError(f"power_ratio must be int, got {type(power_ratio).__name__}")
    if power_ratio < MIN_POWER_RATIO or power_ratio > MAX_POWER_RATIO:
        raise ProtocolError(
            f"power_ratio must be between {MIN_POWER_RATIO} and {MAX_POWER_RATIO}, got {power_ratio}"
        )
    return power_ratio


def build_command_payload(left_ratio: int, right_ratio: int | None = None) -> List[int]:
    """Encode 0x07: Request in byte0, PowerSet1/PowerSet2 as little-endian u16."""
    left = validate_power_ratio(left_ratio)
    right = left if right_ratio is None else validate_power_ratio(right_ratio)
    payload = [0x00] * FRAME_SIZE
    payload[0] = 0x01 if (left > 0 or right > 0) else 0x00
    payload[1] = left & 0xFF
    payload[2] = (left >> 8) & 0xFF
    payload[3] = right & 0xFF
    payload[4] = (right >> 8) & 0xFF
    return payload


def build_command_payload_from_ratio(power_ratio: int) -> List[int]:
    """Apply the shared 0-100 % sequence value to both zones."""
    return build_command_payload(power_ratio, power_ratio)


def parse_status_payload(payload: Iterable[int]) -> A063MainStatus:
    data = _normalize_payload(payload)
    bus_voltage_raw = data[3]
    return A063MainStatus(
        state=_extract_bits(data, 0, 1),
        error_state=bool(_extract_bits(data, 1, 1)),
        error_mode0=_extract_bits(data, 2, 5),
        response_error=bool(_extract_bits(data, 7, 1)),
        error_mode1=data[1],
        temperature_1_c=data[2] - 40,
        bus_voltage_raw=bus_voltage_raw,
        bus_voltage_v=decode_bus_voltage(bus_voltage_raw),
        bus_current_a=data[4],
        power_1_w=data[5] | (data[6] << 8),
        lin_com_error=bool(_extract_bits(data, 57, 1)),
        power_limited=bool(_extract_bits(data, 58, 1)),
        raw_payload=data,
    )


def parse_aux_status_payload(payload: Iterable[int]) -> A063AuxStatus:
    data = _normalize_payload(payload)
    return A063AuxStatus(
        temperature_2_c=data[0] - 40,
        power_2_w=data[1] | (data[2] << 8),
        pcba_temperature_c=data[3] - 40,
        software_version=round(data[4] * 0.1, 1),
        hardware_version=round(data[5] * 0.1, 1),
        igbt_temperature_c=data[6] - 40,
        error_mode2=_extract_bits(data, 56, 4),
        hv_interlock_open=bool(_extract_bits(data, 60, 1)),
        raw_payload=data,
    )


def decode_bus_voltage(raw: int) -> int:
    """Return volts; raw 0/1 (no HV / below 240 V) both read as 0 V."""
    if raw in (BUS_VOLTAGE_RAW_NO_HV, BUS_VOLTAGE_RAW_BELOW_240V):
        return 0
    return raw + BUS_VOLTAGE_OFFSET_V


def describe_fault_code(fault_code: int) -> List[str]:
    return [name for bit, name in enumerate(FAULT_CODE_BITS) if fault_code & (1 << bit)]


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
