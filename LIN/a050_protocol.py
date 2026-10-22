"""A050 LIN protocol encode/decode helpers derived from A050.xlsx."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List

COMMAND_PID = 0x36
MEASUREMENT_STATUS_PID = 0x37
FAULT_STATUS_PID = 0x39
FRAME_SIZE = 8
POWER_STEP_W = 50
MAX_POWER_REQUEST_RAW = 0xFF
MAX_POWER_REQUEST_W = MAX_POWER_REQUEST_RAW * POWER_STEP_W

REQUEST_STATE_MAP = {
    0: "disengage",
    1: "engage",
}

OPERATION_STATUS_MAP = {
    0: "normal_operation",
    1: "degraded_operation",
    2: "reserved_2",
    3: "reserved_3",
}

VOLTAGE_ERROR_MAP = {
    0: "no_error",
    1: "overvoltage",
    2: "undervoltage",
    3: "reserved_3",
}

IGBT_ERROR_MAP = {
    0: "no_error",
    1: "igbt_short_circuit",
    2: "igbt_open_circuit",
    3: "igbt_voltage_driven_breakdown",
}


class ProtocolError(Exception):
    """Raised when payload data violates the A050 protocol contract."""


@dataclass
class A050MeasurementStatus:
    high_voltage_v: float
    electrical_current_a: float
    core_temperature_1_c: int
    core_temperature_2_c: int
    pcb_temperature_c: int
    igbt_temperature_c: int
    power_feedback_w: int
    software_version: int
    hardware_version: int
    raw_payload: List[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class A050FaultStatus:
    operation_status: int
    operation_status_text: str
    hv_voltage_error: int
    hv_voltage_error_text: str
    lv_voltage_error: int
    lv_voltage_error_text: str
    overcurrent: bool
    core_temp_1_sensor_error: bool
    core_temp_2_sensor_error: bool
    core_temp_1_overtemp: bool
    core_temp_2_overtemp: bool
    pcb_temp_sensor_error: bool
    igbt_temp_sensor_error: bool
    pcb_temp_overtemp: bool
    igbt_temp_overtemp: bool
    response_error: bool
    interlock_error: bool
    igbt_error: int
    igbt_error_text: str
    raw_payload: List[int]

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def operation_status_has_fault(self) -> bool:
        return self.operation_status == 1

    @property
    def has_fault(self) -> bool:
        return bool(
            self.operation_status_has_fault
            or self.hv_voltage_error
            or self.lv_voltage_error
            or self.overcurrent
            or self.core_temp_1_sensor_error
            or self.core_temp_2_sensor_error
            or self.core_temp_1_overtemp
            or self.core_temp_2_overtemp
            or self.pcb_temp_sensor_error
            or self.igbt_temp_sensor_error
            or self.pcb_temp_overtemp
            or self.igbt_temp_overtemp
            or self.response_error
            or self.interlock_error
            or self.igbt_error
        )

    @property
    def fault_code(self) -> int:
        return (
            self.hv_voltage_error
            | (self.lv_voltage_error << 2)
            | (int(self.overcurrent) << 4)
            | (int(self.core_temp_1_sensor_error) << 5)
            | (int(self.core_temp_2_sensor_error) << 6)
            | (int(self.core_temp_1_overtemp) << 7)
            | (int(self.core_temp_2_overtemp) << 8)
            | (int(self.pcb_temp_sensor_error) << 9)
            | (int(self.igbt_temp_sensor_error) << 10)
            | (int(self.pcb_temp_overtemp) << 11)
            | (int(self.igbt_temp_overtemp) << 12)
            | (int(self.response_error) << 13)
            | (int(self.interlock_error) << 14)
            | (self.igbt_error << 15)
        )


@dataclass
class A050Status:
    measurement: A050MeasurementStatus
    fault: A050FaultStatus

    def to_dict(self) -> dict:
        return asdict(self)


def combine_status(
    measurement: A050MeasurementStatus,
    fault: A050FaultStatus,
) -> A050Status:
    return A050Status(measurement=measurement, fault=fault)


def build_command_payload(power_request_w: int) -> List[int]:
    validated_power = validate_power_request_w(power_request_w)
    payload = [0x00] * FRAME_SIZE
    payload[0] = 0x01 if validated_power > 0 else 0x00
    payload[1] = validated_power // POWER_STEP_W
    return payload


def build_command_payload_from_ratio(power_ratio: int) -> List[int]:
    """Convert the shared 0-100% sequence value to an A050 power request."""
    if not isinstance(power_ratio, int):
        raise ProtocolError(f"power_ratio must be int, got {type(power_ratio).__name__}")
    if power_ratio < 0 or power_ratio > 100:
        raise ProtocolError(f"power_ratio must be between 0 and 100, got {power_ratio}")

    # Floor to a protocol step so the encoded request never exceeds the ratio.
    raw_steps = power_ratio * MAX_POWER_REQUEST_RAW // 100
    return build_command_payload(raw_steps * POWER_STEP_W)


def validate_power_request_w(power_request_w: int) -> int:
    if not isinstance(power_request_w, int):
        raise ProtocolError(f"power_request_w must be int, got {type(power_request_w).__name__}")
    if power_request_w < 0 or power_request_w > MAX_POWER_REQUEST_W:
        raise ProtocolError(f"power_request_w must be between 0 and {MAX_POWER_REQUEST_W}, got {power_request_w}")
    if power_request_w % POWER_STEP_W != 0:
        raise ProtocolError(f"power_request_w must be a multiple of {POWER_STEP_W}, got {power_request_w}")
    return power_request_w


def parse_measurement_payload(payload: Iterable[int]) -> A050MeasurementStatus:
    data = _normalize_payload(payload)
    versions = data[7]
    return A050MeasurementStatus(
        high_voltage_v=data[0] * 2.5,
        electrical_current_a=data[1] * 0.2,
        core_temperature_1_c=data[2] - 40,
        core_temperature_2_c=data[3] - 40,
        pcb_temperature_c=data[4] - 40,
        igbt_temperature_c=data[5] - 40,
        power_feedback_w=data[6] * POWER_STEP_W,
        software_version=versions & 0x0F,
        hardware_version=(versions >> 4) & 0x0F,
        raw_payload=data,
    )


def parse_fault_payload(payload: Iterable[int]) -> A050FaultStatus:
    data = _normalize_payload(payload)
    operation_status = _extract_bits(data, 0, 2)
    hv_voltage_error = _extract_bits(data, 2, 2)
    lv_voltage_error = _extract_bits(data, 4, 2)
    igbt_error = _extract_bits(data, 19, 2)

    return A050FaultStatus(
        operation_status=operation_status,
        operation_status_text=OPERATION_STATUS_MAP.get(operation_status, f"unknown_{operation_status}"),
        hv_voltage_error=hv_voltage_error,
        hv_voltage_error_text=VOLTAGE_ERROR_MAP.get(hv_voltage_error, f"unknown_{hv_voltage_error}"),
        lv_voltage_error=lv_voltage_error,
        lv_voltage_error_text=VOLTAGE_ERROR_MAP.get(lv_voltage_error, f"unknown_{lv_voltage_error}"),
        overcurrent=bool(_extract_bits(data, 8, 1)),
        core_temp_1_sensor_error=bool(_extract_bits(data, 9, 1)),
        core_temp_2_sensor_error=bool(_extract_bits(data, 10, 1)),
        core_temp_1_overtemp=bool(_extract_bits(data, 11, 1)),
        core_temp_2_overtemp=bool(_extract_bits(data, 12, 1)),
        pcb_temp_sensor_error=bool(_extract_bits(data, 13, 1)),
        igbt_temp_sensor_error=bool(_extract_bits(data, 14, 1)),
        pcb_temp_overtemp=bool(_extract_bits(data, 15, 1)),
        igbt_temp_overtemp=bool(_extract_bits(data, 16, 1)),
        response_error=bool(_extract_bits(data, 17, 1)),
        interlock_error=bool(_extract_bits(data, 18, 1)),
        igbt_error=igbt_error,
        igbt_error_text=IGBT_ERROR_MAP.get(igbt_error, f"unknown_{igbt_error}"),
        raw_payload=data,
    )


def describe_request_state(request_state: int) -> str:
    return REQUEST_STATE_MAP.get(request_state, f"unknown_{request_state}")


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
