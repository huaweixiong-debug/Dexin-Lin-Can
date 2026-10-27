"""Per-step power limit checks (pure functions, no hardware imports)."""

from __future__ import annotations

from typing import Any, Dict


def check_power_upper(step: Dict[str, Any], left_w: int, right_w: int) -> str | None:
    """Return a violation message when instantaneous power exceeds the step's upper limit."""
    max_w = float(step.get("power_max_w", 0) or 0)
    if max_w <= 0:
        return None
    if left_w > max_w:
        return f"左区 {left_w}W 高于上限 {max_w:.0f}W"
    if right_w > max_w:
        return f"右区 {right_w}W 高于上限 {max_w:.0f}W"
    return None


def check_power_lower(
    step: Dict[str, Any],
    left_avg_w: float,
    right_avg_w: float,
    sample_count: int,
) -> str | None:
    """Return a violation message when the steady-state average is below the step's lower limit."""
    min_w = float(step.get("power_min_w", 0) or 0)
    if min_w <= 0 or sample_count <= 0:
        return None
    if left_avg_w < min_w:
        return f"左区末段平均 {left_avg_w:.0f}W 低于下限 {min_w:.0f}W"
    if right_avg_w < min_w:
        return f"右区末段平均 {right_avg_w:.0f}W 低于下限 {min_w:.0f}W"
    return None
