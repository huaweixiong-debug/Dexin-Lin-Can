"""Shared logger for the A045 LIN tools."""

from __future__ import annotations

import logging


logger = logging.getLogger("a045_lin")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

