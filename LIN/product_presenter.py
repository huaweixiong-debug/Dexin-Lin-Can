"""Product-specific status presentation adapters for logs and summaries.

Decouples main.py from a045_protocol.py so that future products (A050)
can use different status shapes without rewriting the runner loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from a045_protocol import A045Status, build_command_payload, describe_error_code, format_payload_hex
from a050_protocol import (
    A050MeasurementStatus,
    A050Status,
    build_command_payload_from_ratio as build_a050_command_payload,
    format_payload_hex as format_a050_hex,
)
from product_catalog import DEFAULT_PRODUCT_CODE
from runtime_protocols import RuntimeProtocolError


# ---------------------------------------------------------------------------
# Product-agnostic status wrapper
# ---------------------------------------------------------------------------

@dataclass
class RuntimeStatus:
    """Product-independent status shape consumed by main.py polling loop.

    Every product adapter must produce one RuntimeStatus per exchange.
    """

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


def adapt_status(status_obj: Any, product_code: str) -> RuntimeStatus:
    """Convert a product-specific status dataclass to RuntimeStatus.

    Raises:
        RuntimeProtocolError: if *product_code* is unknown.
        TypeError: if *status_obj* does not match the expected type.
    """
    code = _normalize_code(product_code)
    if code == "A045":
        if not isinstance(status_obj, A045Status):
            raise TypeError(
                f"Expected A045Status for product {code!r}, got {type(status_obj).__name__}"
            )
        return RuntimeStatus(
            left_power_w=status_obj.left_power_w,
            right_power_w=status_obj.right_power_w,
            left_temperature_c=status_obj.left_temperature_c,
            right_temperature_c=status_obj.right_temperature_c,
            pcb_igbt_temperature_c=status_obj.pcb_igbt_temperature_c,
            run_status=status_obj.run_status,
            run_status_text=status_obj.run_status_text,
            error_level=status_obj.error_level,
            error_level_text=status_obj.error_level_text,
            error_code=status_obj.error_code,
            hv_voltage_v=status_obj.hv_voltage_v,
            raw_payload=list(status_obj.raw_payload),
        )
    if code == "A050":
        if isinstance(status_obj, A050Status):
            measurement = status_obj.measurement
            fault = status_obj.fault
        elif isinstance(status_obj, A050MeasurementStatus):
            measurement = status_obj
            fault = None
        else:
            raise TypeError(
                f"Expected A050Status for product {code!r}, got {type(status_obj).__name__}"
            )
        return RuntimeStatus(
            # Single-channel device: report same power for left/right
            left_power_w=measurement.power_feedback_w,
            right_power_w=measurement.power_feedback_w,
            # Core temps map to left/right temperature slots
            left_temperature_c=measurement.core_temperature_1_c,
            right_temperature_c=measurement.core_temperature_2_c,
            pcb_igbt_temperature_c=measurement.pcb_temperature_c,
            run_status=fault.operation_status if fault is not None else 0,
            run_status_text=fault.operation_status_text if fault is not None else "unknown",
            error_level=int(fault.has_fault) if fault is not None else 0,
            error_level_text=(
                fault.operation_status_text
                if fault is not None and fault.operation_status_has_fault and fault.fault_code == 0
                else "fault"
                if fault is not None and fault.has_fault
                else "normal"
            ),
            error_code=fault.fault_code if fault is not None else 0x00,
            hv_voltage_v=int(measurement.high_voltage_v),
            raw_payload=list(measurement.raw_payload),
        )
    raise RuntimeProtocolError(
        f"Runtime presenter is not available for product {code!r}"
    )


# ---------------------------------------------------------------------------
# Command builder (product-routed)
# ---------------------------------------------------------------------------

def build_command(power_ratio: int, product_code: str = DEFAULT_PRODUCT_CODE) -> List[int]:
    """Build a command payload for *product_code*.

    A045: power_ratio is a percentage (0-100).
    A050: converts power_ratio % to the protocol's 0-255 power steps.
    """
    code = _normalize_code(product_code)
    if code == "A045":
        return build_command_payload(power_ratio)
    if code == "A050":
        return build_a050_command_payload(power_ratio)
    raise RuntimeProtocolError(
        f"Command builder is not available for product {code!r}"
    )


# ---------------------------------------------------------------------------
# Status presenter (product-routed, works on RuntimeStatus)
# ---------------------------------------------------------------------------

def present_status(
    status: RuntimeStatus,
    command_payload: List[int],
    product_code: str = DEFAULT_PRODUCT_CODE,
    transition_prefix: str = "[STATUS]",
) -> str:
    """Format a status snapshot as a human-readable log line."""
    code = _normalize_code(product_code)
    if code == "A045":
        return (
            f"{transition_prefix} "
            f"run={status.run_status_text} "
            f"fault={status.error_level_text}/{describe_error_code(status.error_code)} "
            f"left_power={status.left_power_w}W "
            f"right_power={status.right_power_w}W "
            f"left_temp={status.left_temperature_c}C "
            f"right_temp={status.right_temperature_c}C "
            f"pcb_temp={status.pcb_igbt_temperature_c}C "
            f"hv={status.hv_voltage_v}V "
            f"tx26={format_payload_hex(command_payload)} "
            f"rx27={format_payload_hex(status.raw_payload)} "
            f"raw={status.raw_payload}"
        )
    if code == "A050":
        fault_text = status.error_level_text
        if status.error_code or not status.error_level:
            fault_text = f"{fault_text}/0x{status.error_code:X}"
        return (
            f"{transition_prefix} "
            f"run={status.run_status_text} "
            f"fault={fault_text} "
            f"left_power={status.left_power_w}W "
            f"right_power={status.right_power_w}W "
            f"left_temp={status.left_temperature_c}C "
            f"right_temp={status.right_temperature_c}C "
            f"pcb_temp={status.pcb_igbt_temperature_c}C "
            f"hv={status.hv_voltage_v:.1f}V "
            f"tx36={format_a050_hex(command_payload)} "
            f"rx37={format_a050_hex(status.raw_payload)} "
            f"raw={status.raw_payload}"
        )
    raise RuntimeProtocolError(
        f"Status presenter is not available for product {code!r}"
    )


# ---------------------------------------------------------------------------
# Step summary presenter (product-routed, works on RuntimeStatus)
# ---------------------------------------------------------------------------

def present_summary(
    step_index: int,
    step: Dict[str, Any],
    step_last_status: RuntimeStatus | None,
    step_max_left_power: int,
    step_max_right_power: int,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> str:
    """Format a step summary log line."""
    code = _normalize_code(product_code)
    if step_last_status is None:
        return (
            f"[STEP_SUMMARY] step={step_index} name={step['name']} "
            f"power_ratio={step['power_ratio']} "
            f"result=no_valid_status"
        )
    if code == "A045":
        return (
            f"[STEP_SUMMARY] step={step_index} name={step['name']} "
            f"power_ratio={step['power_ratio']} "
            f"max_left={step_max_left_power}W max_right={step_max_right_power}W "
            f"end_left={step_last_status.left_power_w}W end_right={step_last_status.right_power_w}W "
            f"end_run={step_last_status.run_status_text} end_hv={step_last_status.hv_voltage_v}V "
            f"end_temp_left={step_last_status.left_temperature_c}C "
            f"end_temp_right={step_last_status.right_temperature_c}C"
        )
    if code == "A050":
        return (
            f"[STEP_SUMMARY] step={step_index} name={step['name']} "
            f"power_ratio={step['power_ratio']} "
            f"max_power={step_max_left_power}W "
            f"end_power={step_last_status.left_power_w}W "
            f"end_hv={step_last_status.hv_voltage_v:.1f}V "
            f"end_temp1={step_last_status.left_temperature_c}C "
            f"end_temp2={step_last_status.right_temperature_c}C"
        )
    raise RuntimeProtocolError(
        f"Summary presenter is not available for product {code!r}"
    )


# ---------------------------------------------------------------------------
# Step peak power extractor (product-routed)
# ---------------------------------------------------------------------------

def extract_step_power(
    status: RuntimeStatus,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> Tuple[int, int]:
    """Return (left_w, right_w) for step peak tracking."""
    code = _normalize_code(product_code)
    if code == "A045":
        return (status.left_power_w, status.right_power_w)
    if code == "A050":
        p = status.left_power_w
        return (p, p)
    raise RuntimeProtocolError(
        f"Step power extractor is not available for product {code!r}"
    )


# ---------------------------------------------------------------------------
# Transition-detection signature (product-routed, works on RuntimeStatus)
# ---------------------------------------------------------------------------

def status_signature(
    status: RuntimeStatus,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> Tuple[int, int, int, int, int, int]:
    """Return a hashable tuple for transition detection."""
    code = _normalize_code(product_code)
    if code == "A045":
        return (
            status.run_status,
            status.error_level,
            status.error_code,
            status.left_power_w,
            status.right_power_w,
            status.hv_voltage_v,
        )
    if code == "A050":
        return (
            status.run_status,
            status.error_level,
            status.error_code,
            status.left_power_w,
            status.right_power_w,
            status.hv_voltage_v,
        )
    raise RuntimeProtocolError(
        f"Status signature is not available for product {code!r}"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_code(product_code: str) -> str:
    return str(product_code).strip().upper()
