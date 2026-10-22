"""Product metadata registry for LIN test products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ProductDefinition:
    code: str
    display_name: str
    runtime_supported: bool
    protocol_summary: str
    command_pid: int | None = None
    status_pid: int | None = None
    aux_status_pid: int | None = None


DEFAULT_PRODUCT_CODE = "A045"

_PRODUCTS: Dict[str, ProductDefinition] = {
    "A045": ProductDefinition(
        code="A045",
        display_name="A045 LIN",
        runtime_supported=True,
        protocol_summary="Dual-channel heater protocol with 0x26 command and 0x27 status frames.",
        command_pid=0x26,
        status_pid=0x27,
    ),
    "A050": ProductDefinition(
        code="A050",
        display_name="A050 LIN",
        runtime_supported=True,
        protocol_summary="Single-channel protocol from A050.xlsx using 0x36 command, 0x37 status, and 0x39 auxiliary frames.",
        command_pid=0x36,
        status_pid=0x37,
        aux_status_pid=0x39,
    ),
}


def get_product_definition(product_code: str) -> ProductDefinition | None:
    return _PRODUCTS.get(str(product_code).strip().upper())


def list_known_products() -> List[ProductDefinition]:
    return [_PRODUCTS[code] for code in sorted(_PRODUCTS.keys())]


def list_runtime_supported_products() -> List[ProductDefinition]:
    return [product for product in list_known_products() if product.runtime_supported]
