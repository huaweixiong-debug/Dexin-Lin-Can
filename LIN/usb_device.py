"""Compatibility wrapper that reuses the existing USB2XXX SDK loader."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    current_dir = Path(__file__).resolve().parent
    candidates = [
        current_dir.parent / "老化CAN通讯" / "LGV2" / "usb_device.py",
        current_dir.parent / "老化CAN通讯" / "USB2CAN" / "usb_device.py",
    ]

    for candidate in candidates:
        if candidate.exists():
            if str(candidate.parent) not in sys.path:
                sys.path.insert(0, str(candidate.parent))
            spec = importlib.util.spec_from_file_location("_a045_usb_device", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    raise ImportError("Unable to locate usb_device.py in the CAN project directories")


_MODULE = _load_module()

for _name in dir(_MODULE):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_MODULE, _name)
