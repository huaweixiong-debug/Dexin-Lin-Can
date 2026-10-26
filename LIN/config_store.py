"""Configuration loading, validation, and saving for LIN runner settings."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from a045_protocol import validate_power_ratio
from product_catalog import DEFAULT_PRODUCT_CODE, list_known_products

CONFIG_FILE = "config.json"
TEMPLATES_DIR = "templates"
STATION_COUNT = 10
KNOWN_PRODUCTS = tuple(product.code for product in list_known_products())

DEFAULT_CONFIG: Dict[str, Any] = {
    "product": DEFAULT_PRODUCT_CODE,
    "active_station_slot": 1,
    "device": {
        "lin_sn": "",
        "lin_index": 0,
        "baud_rate": 19200,
    },
    "plc": {
        "enabled": False,
        "plc1_ip": "192.168.10.180",
        "plc2_ip": "192.168.10.181",
    },
    "scan": {
        "scan_start": False,
    },
    "stations": [
        {
            "slot": slot,
            "name": f"工位 {slot}",
            "enabled": True,
            "lin_sn": "",
            "lin_index": 0,
            "scanner_ip": "",
        }
        for slot in range(1, STATION_COUNT + 1)
    ],
    "timing": {
        "send_interval_ms": 100,
        "read_interval_ms": 20,
        "watchdog_sec": 5,
    },
    "step_plan": {
        "cooldown_duration_sec": 3,
        "steps": [
            {"name": "Step 1 (100%)", "power_ratio": 100, "duration_sec": 10},
            {"name": "Step 2 (80%)", "power_ratio": 80, "duration_sec": 10},
            {"name": "Step 3 (50%)", "power_ratio": 50, "duration_sec": 10},
            {"name": "Step 4 (30%)", "power_ratio": 30, "duration_sec": 10},
            {"name": "Step 5 (10%)", "power_ratio": 10, "duration_sec": 10},
        ],
    },
}


class ConfigError(Exception):
    """Raised when the local JSON configuration is invalid."""


def get_default_config() -> Dict[str, Any]:
    return deepcopy(DEFAULT_CONFIG)


def load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc


def save_config(config_path: Path, config: Dict[str, Any]) -> None:
    normalized = validate_config(config)
    config_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_templates(base_dir: Path) -> List[str]:
    template_dir = base_dir / TEMPLATES_DIR
    if not template_dir.exists():
        return []

    return sorted(path.stem for path in template_dir.glob("*.json") if path.is_file())


def save_template(base_dir: Path, template_name: str, config: Dict[str, Any]) -> Path:
    normalized = validate_config(config)
    safe_name = _sanitize_template_name(template_name)
    template_dir = base_dir / TEMPLATES_DIR
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / f"{safe_name}.json"
    template_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return template_path


def load_template(base_dir: Path, template_name: str) -> Dict[str, Any]:
    safe_name = _sanitize_template_name(template_name)
    template_path = base_dir / TEMPLATES_DIR / f"{safe_name}.json"
    if not template_path.exists():
        raise ConfigError(f"Template not found: {template_name}")
    return load_config(template_path)


def rename_template(base_dir: Path, old_name: str, new_name: str) -> Path:
    old_safe_name = _sanitize_template_name(old_name)
    new_safe_name = _sanitize_template_name(new_name)
    template_dir = base_dir / TEMPLATES_DIR
    old_path = template_dir / f"{old_safe_name}.json"
    new_path = template_dir / f"{new_safe_name}.json"

    if not old_path.exists():
        raise ConfigError(f"Template not found: {old_name}")
    if new_path.exists() and new_path != old_path:
        raise ConfigError(f"Template already exists: {new_name}")

    template_dir.mkdir(parents=True, exist_ok=True)
    old_path.replace(new_path)
    return new_path


def delete_template(base_dir: Path, template_name: str) -> None:
    safe_name = _sanitize_template_name(template_name)
    template_path = base_dir / TEMPLATES_DIR / f"{safe_name}.json"
    if not template_path.exists():
        raise ConfigError(f"Template not found: {template_name}")

    template_path.unlink()


def validate_config(config: Dict[str, Any], station_override: int | None = None) -> Dict[str, Any]:
    product_code = str(config.get("product", DEFAULT_PRODUCT_CODE)).strip().upper()
    if product_code not in KNOWN_PRODUCTS:
        raise ConfigError(f"product must be one of {KNOWN_PRODUCTS!r}")

    device = config.get("device")
    timing = config.get("timing")
    if not isinstance(timing, dict):
        raise ConfigError("timing section is required")

    device = device if isinstance(device, dict) else {}
    stations = _normalize_stations(config, device)
    active_station_slot = station_override if station_override is not None else int(config.get("active_station_slot", 1))
    if active_station_slot < 1 or active_station_slot > STATION_COUNT:
        raise ConfigError(f"active_station_slot must be between 1 and {STATION_COUNT}")

    selected_station = next((station for station in stations if station["slot"] == active_station_slot), None)
    if selected_station is None:
        raise ConfigError(f"active_station_slot {active_station_slot} is not configured")

    fallback_lin_sn = str(device.get("lin_sn", "")).strip()
    fallback_lin_index = int(device.get("lin_index", 0))
    baud_rate = int(device.get("baud_rate", 19200))
    plc = config.get("plc")
    scan = config.get("scan")
    plc = plc if isinstance(plc, dict) else {}
    scan = scan if isinstance(scan, dict) else {}
    lin_sn = str(selected_station.get("lin_sn", "")).strip() or fallback_lin_sn
    if not lin_sn:
        raise ConfigError("active station lin_sn is required")

    lin_index = int(selected_station.get("lin_index", fallback_lin_index))
    plc_enabled = bool(plc.get("enabled", False))
    plc1_ip = str(plc.get("plc1_ip", "192.168.10.180")).strip() or "192.168.10.180"
    plc2_ip = str(plc.get("plc2_ip", "192.168.10.181")).strip() or "192.168.10.181"
    scan_start = bool(scan.get("scan_start", False))

    if lin_index < 0:
        raise ConfigError("device.lin_index must be >= 0")
    if baud_rate <= 0:
        raise ConfigError("device.baud_rate must be > 0")
    normalized_timing = _normalize_timing(timing)
    step_plan = _normalize_step_plan(config)
    normalized_sequence = _build_sequence_from_step_plan(step_plan)
    product_profiles = _normalize_product_profiles(config.get("product_profiles"))
    # The top-level values are the active product's profile and always win.
    product_profiles[product_code] = {
        "baud_rate": baud_rate,
        "timing": deepcopy(normalized_timing),
        "step_plan": deepcopy(step_plan),
    }

    return {
        "product": product_code,
        "active_station_slot": active_station_slot,
        "device": {
            "lin_sn": lin_sn,
            "lin_index": lin_index,
            "baud_rate": baud_rate,
        },
        "plc": {
            "enabled": plc_enabled,
            "plc1_ip": plc1_ip,
            "plc2_ip": plc2_ip,
        },
        "scan": {
            "scan_start": scan_start,
        },
        "stations": stations,
        "timing": normalized_timing,
        "step_plan": step_plan,
        "sequence": normalized_sequence,
        "product_profiles": {code: product_profiles[code] for code in KNOWN_PRODUCTS if code in product_profiles},
    }


def switch_product(config: Dict[str, Any], product_code: str) -> Dict[str, Any]:
    """Return *config* with *product_code* active.

    The current top-level communication parameters and step plan are stored as
    the outgoing product's profile; the incoming product's saved profile (if
    any) replaces them. A product without a saved profile starts from the
    current values. Stations, PLC and scan settings are shared and untouched.
    """
    current = validate_config(config)
    target_code = str(product_code).strip().upper()
    if target_code not in KNOWN_PRODUCTS:
        raise ConfigError(f"product must be one of {KNOWN_PRODUCTS!r}")

    switched = deepcopy(current)
    switched["product"] = target_code
    profile = current["product_profiles"].get(target_code)
    if profile is not None:
        switched["device"]["baud_rate"] = profile["baud_rate"]
        switched["timing"] = deepcopy(profile["timing"])
        switched["step_plan"] = deepcopy(profile["step_plan"])
        switched.pop("sequence", None)
    return validate_config(switched)


def _normalize_timing(timing: Dict[str, Any]) -> Dict[str, Any]:
    send_interval_ms = int(timing.get("send_interval_ms", 100))
    read_interval_ms = int(timing.get("read_interval_ms", 20))
    watchdog_sec = float(timing.get("watchdog_sec", 5))
    if send_interval_ms <= 0:
        raise ConfigError("timing.send_interval_ms must be > 0")
    if read_interval_ms <= 0:
        raise ConfigError("timing.read_interval_ms must be > 0")
    if watchdog_sec <= 0:
        raise ConfigError("timing.watchdog_sec must be > 0")
    return {
        "send_interval_ms": send_interval_ms,
        "read_interval_ms": read_interval_ms,
        "watchdog_sec": watchdog_sec,
    }


def _normalize_product_profiles(raw_profiles: Any) -> Dict[str, Dict[str, Any]]:
    if raw_profiles is None:
        return {}
    if not isinstance(raw_profiles, dict):
        raise ConfigError("product_profiles must be an object")

    profiles: Dict[str, Dict[str, Any]] = {}
    for raw_code, profile in raw_profiles.items():
        code = str(raw_code).strip().upper()
        if code not in KNOWN_PRODUCTS:
            continue
        if not isinstance(profile, dict):
            raise ConfigError(f"product_profiles.{code} must be an object")
        timing = profile.get("timing")
        if not isinstance(timing, dict):
            raise ConfigError(f"product_profiles.{code}.timing section is required")
        baud_rate = int(profile.get("baud_rate", 19200))
        if baud_rate <= 0:
            raise ConfigError(f"product_profiles.{code}.baud_rate must be > 0")
        profiles[code] = {
            "baud_rate": baud_rate,
            "timing": _normalize_timing(timing),
            "step_plan": _normalize_step_plan({"step_plan": profile.get("step_plan")}),
        }
    return profiles


def _normalize_step_plan(config: Dict[str, Any]) -> Dict[str, Any]:
    if "step_plan" in config:
        step_plan = config.get("step_plan")
        if not isinstance(step_plan, dict):
            raise ConfigError("step_plan must be an object")

        cooldown_duration_sec = float(step_plan.get("cooldown_duration_sec", 0))
        if cooldown_duration_sec < 0:
            raise ConfigError("step_plan.cooldown_duration_sec must be >= 0")

        raw_steps = step_plan.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ConfigError("step_plan.steps must contain at least one test step")

        normalized_steps: List[Dict[str, Any]] = []
        for index, step in enumerate(raw_steps, start=1):
            if not isinstance(step, dict):
                raise ConfigError(f"step_plan.steps[{index}] must be an object")

            name = str(step.get("name", f"Step {index}")).strip() or f"Step {index}"
            power_ratio = validate_power_ratio(int(step.get("power_ratio", 0)))
            if power_ratio <= 0:
                raise ConfigError(f"step_plan.steps[{index}].power_ratio must be between 1 and 100")
            duration_sec = float(step.get("duration_sec", 0))
            if duration_sec < 0:
                raise ConfigError(f"step_plan.steps[{index}].duration_sec must be >= 0")

            normalized_steps.append(
                {
                    "name": name,
                    "power_ratio": power_ratio,
                    "duration_sec": duration_sec,
                }
            )

        return {
            "cooldown_duration_sec": cooldown_duration_sec,
            "steps": normalized_steps,
        }

    sequence = config.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        raise ConfigError("sequence must contain at least one step")

    return _derive_step_plan_from_sequence(sequence)


def _build_sequence_from_step_plan(step_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    cooldown_duration_sec = float(step_plan["cooldown_duration_sec"])
    normalized_sequence: List[Dict[str, Any]] = []
    steps = step_plan["steps"]

    for index, step in enumerate(steps, start=1):
        normalized_sequence.append(
            {
                "name": step["name"],
                "power_ratio": step["power_ratio"],
                "duration_sec": step["duration_sec"],
            }
        )
        if index < len(steps):
            normalized_sequence.append(
                {
                    "name": f"Cooldown {index}",
                    "power_ratio": 0,
                    "duration_sec": cooldown_duration_sec,
                }
            )

    return normalized_sequence


def _derive_step_plan_from_sequence(sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
    derived_steps: List[Dict[str, Any]] = []
    cooldown_duration_sec = 0.0

    for index, step in enumerate(sequence, start=1):
        if not isinstance(step, dict):
            raise ConfigError(f"sequence[{index}] must be an object")

        name = str(step.get("name", f"Step {index}")).strip() or f"Step {index}"
        power_ratio = validate_power_ratio(int(step.get("power_ratio", 0)))
        duration_sec = float(step.get("duration_sec", 0))
        if duration_sec < 0:
            raise ConfigError(f"sequence[{index}].duration_sec must be >= 0")

        if power_ratio == 0:
            cooldown_duration_sec = duration_sec
            continue

        derived_steps.append(
            {
                "name": name,
                "power_ratio": power_ratio,
                "duration_sec": duration_sec,
            }
        )

    if not derived_steps:
        raise ConfigError("sequence must contain at least one non-zero test step")

    return {
        "cooldown_duration_sec": cooldown_duration_sec,
        "steps": derived_steps,
    }


def _normalize_stations(config: Dict[str, Any], fallback_device: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_stations = config.get("stations")
    normalized_by_slot: Dict[int, Dict[str, Any]] = {}

    if isinstance(raw_stations, list):
        for index, station in enumerate(raw_stations, start=1):
            if not isinstance(station, dict):
                raise ConfigError(f"stations[{index}] must be an object")

            slot = int(station.get("slot", index))
            if slot < 1 or slot > STATION_COUNT:
                raise ConfigError(f"stations[{index}].slot must be between 1 and {STATION_COUNT}")
            if slot in normalized_by_slot:
                raise ConfigError(f"duplicate station slot detected: {slot}")

            normalized_by_slot[slot] = {
                "slot": slot,
                "name": str(station.get("name", f"工位 {slot}")).strip() or f"工位 {slot}",
                "enabled": bool(station.get("enabled", True)),
                "lin_sn": str(station.get("lin_sn", "")).strip(),
                "lin_index": int(station.get("lin_index", 0)),
                "scanner_ip": str(station.get("scanner_ip", "")).strip(),
            }
    elif raw_stations is not None:
        raise ConfigError("stations must be a list")

    fallback_lin_sn = str(fallback_device.get("lin_sn", "")).strip()
    fallback_lin_index = int(fallback_device.get("lin_index", 0))
    if 1 not in normalized_by_slot:
        normalized_by_slot[1] = {
            "slot": 1,
            "name": "工位 1",
            "enabled": True,
            "lin_sn": fallback_lin_sn,
            "lin_index": fallback_lin_index,
            "scanner_ip": "",
        }

    normalized_stations: List[Dict[str, Any]] = []
    for slot in range(1, STATION_COUNT + 1):
        station = normalized_by_slot.get(
            slot,
            {
                "slot": slot,
                "name": f"工位 {slot}",
                "enabled": True,
                "lin_sn": "",
                "lin_index": 0,
                "scanner_ip": "",
            },
        )
        if int(station["lin_index"]) < 0:
            raise ConfigError(f"stations[{slot}].lin_index must be >= 0")
        normalized_stations.append(
            {
                "slot": slot,
                "name": str(station["name"]).strip() or f"工位 {slot}",
                "enabled": bool(station.get("enabled", True)),
                "lin_sn": str(station.get("lin_sn", "")).strip(),
                "lin_index": int(station.get("lin_index", 0)),
                "scanner_ip": str(station.get("scanner_ip", "")).strip(),
            }
        )

    return normalized_stations


def _sanitize_template_name(template_name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in template_name.strip())
    cleaned = cleaned.strip("_")
    if not cleaned:
        raise ConfigError("template name must contain at least one valid character")
    return cleaned
