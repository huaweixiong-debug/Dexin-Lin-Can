"""Runtime protocol adapters used by the live LIN service layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable

from a045_protocol import (
    COMMAND_PID as A045_COMMAND_PID,
    FRAME_SIZE as A045_FRAME_SIZE,
    STATUS_PID as A045_STATUS_PID,
    build_command_payload as build_a045_command_payload,
    parse_status_payload as parse_a045_status_payload,
)
from a050_protocol import (
    COMMAND_PID as A050_COMMAND_PID,
    FAULT_STATUS_PID as A050_AUX_STATUS_PID,
    FRAME_SIZE as A050_FRAME_SIZE,
    MEASUREMENT_STATUS_PID as A050_STATUS_PID,
    build_command_payload_from_ratio as build_a050_command_payload,
    combine_status as combine_a050_status,
    parse_fault_payload as parse_a050_aux_status_payload,
    parse_measurement_payload as parse_a050_status_payload,
)


class RuntimeProtocolError(Exception):
    """Raised when runtime protocol metadata is missing or unsupported."""


@dataclass(frozen=True)
class RuntimeProtocolAdapter:
    product_code: str
    frame_size: int
    command_pid: int
    status_pid: int
    build_command_payload: Callable[[int], list[int]]
    parse_status_payload: Callable[[Iterable[int]], Any]
    aux_status_pid: int | None = None
    parse_aux_status_payload: Callable[[Iterable[int]], Any] | None = None
    combine_status: Callable[[Any, Any], Any] | None = None


_RUNTIME_PROTOCOLS: Dict[str, RuntimeProtocolAdapter] = {
    "A045": RuntimeProtocolAdapter(
        product_code="A045",
        frame_size=A045_FRAME_SIZE,
        command_pid=A045_COMMAND_PID,
        status_pid=A045_STATUS_PID,
        build_command_payload=build_a045_command_payload,
        parse_status_payload=parse_a045_status_payload,
    ),
    "A050": RuntimeProtocolAdapter(
        product_code="A050",
        frame_size=A050_FRAME_SIZE,
        command_pid=A050_COMMAND_PID,
        status_pid=A050_STATUS_PID,
        build_command_payload=build_a050_command_payload,
        parse_status_payload=parse_a050_status_payload,
        aux_status_pid=A050_AUX_STATUS_PID,
        parse_aux_status_payload=parse_a050_aux_status_payload,
        combine_status=combine_a050_status,
    ),
}


def get_runtime_protocol(product_code: str) -> RuntimeProtocolAdapter:
    normalized = str(product_code).strip().upper()
    protocol = _RUNTIME_PROTOCOLS.get(normalized)
    if protocol is None:
        raise RuntimeProtocolError(f"Runtime protocol is not available for product {normalized!r}")
    return protocol
