"""Console runner for the A045 LIN test sequence.

Usage:
    python main.py [config.json] [--station N]
    python main.py [config.json] --stations 1,2
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from config_store import CONFIG_FILE, ConfigError, load_config, validate_config
from product_catalog import DEFAULT_PRODUCT_CODE
from product_presenter import (
    RuntimeStatus,
    adapt_status,
    build_command,
    extract_step_power,
    present_status,
    present_summary,
    status_signature,
)
from lin_device_manager import lin_device_manager
from lin_service import DeviceNotFoundError, LinCommunicationError, LinServiceError
from power_limits import check_power_lower, check_power_upper


class ProductFaultError(LinServiceError):
    """Raised when a product reports a fault that requires immediate shutdown."""


class PowerOutOfRangeError(LinServiceError):
    """Raised when measured power leaves the configured per-step range."""


# Consecutive faulty status frames before the run is stopped as NG.
# A063/A064 debounce 3 frames (~300 ms) so a one-off ResponseError does not trip.
FAULT_STOP_CONFIRM_FRAMES = {
    "A050": 1,
    "A063": 3,
    "A064": 3,
}


class SequenceRunner:
    def __init__(
        self,
        config: Dict[str, Any],
        station_tag: str = "",
        print_lock: threading.Lock | None = None,
        channel_binding: Dict[str, Any] | None = None,
        stop_event: threading.Event | None = None,
        log_callback: Callable[[str], None] | None = None,
        start_barrier: threading.Barrier | None = None,
    ):
        self.config = config
        self.channel_binding = channel_binding
        self._tag = station_tag
        self._print_lock = print_lock
        self._stop_event = stop_event
        self._log_callback = log_callback
        self._start_barrier = start_barrier
        self.current_power_ratio = 0
        self.last_valid_status_time = 0.0
        self.last_status_print_time = 0.0
        self.read_success_count = 0
        self.last_status_signature = None
        self.step_summaries = []
        self._consecutive_failures = 0
        self._reinit_threshold = 5
        self._consecutive_fault_frames = 0

    def _check_stop_requested(self) -> None:
        if self._stop_event is not None and self._stop_event.is_set():
            raise RunStoppedError("Run stopped by user")

    def _log(self, message: str) -> None:
        line = f"{self._tag}{message}"
        if self._log_callback is not None:
            self._log_callback(line)
            return
        if self._print_lock:
            with self._print_lock:
                print(line, flush=True)
        else:
            print(line, flush=True)

    def run(self) -> None:
        if self.channel_binding is None:
            self.channel_binding = _ensure_channel_for_device_config(
                self.config["device"],
                self.config.get("product", DEFAULT_PRODUCT_CODE),
            )
        self._log(
            f"Initializing LIN channel... SN={self.config['device']['lin_sn']} "
            f"Index={self.config['device']['lin_index']}"
        )

        if self._start_barrier is not None:
            self._log("Waiting for multi-station start gate...")
            try:
                self._start_barrier.wait()
            except threading.BrokenBarrierError as exc:
                raise LinServiceError("Multi-station start gate broken before run began") from exc

        self.last_valid_status_time = time.time()

        try:
            self._run_sequence()
        finally:
            self._shutdown()

    def _run_sequence(self) -> None:
        product_code = self.config.get("product", "A045")
        read_interval_sec = self.config["timing"]["read_interval_ms"] / 1000.0
        send_interval_sec = self.config["timing"]["send_interval_ms"] / 1000.0
        watchdog_sec = self.config["timing"]["watchdog_sec"]
        settle_delay_sec = max(send_interval_sec - read_interval_sec, 0.08)

        for step_index, step in enumerate(self.config["sequence"], start=1):
            self._check_stop_requested()
            self.current_power_ratio = step["power_ratio"]
            start_time = time.time()
            duration_sec = step["duration_sec"]
            step_max_left_power = 0
            step_max_right_power = 0
            step_last_status = None
            # Lower limit is judged on the last quarter of the step to avoid
            # tripping during the heater ramp-up.
            steady_check_offset = duration_sec * 0.75
            steady_left_sum = 0.0
            steady_right_sum = 0.0
            steady_samples = 0
            self._log(
                f"[STEP {step_index}/{len(self.config['sequence'])}] "
                f"{step['name']} | power_ratio={self.current_power_ratio}% "
                f"| duration={duration_sec:.1f}s"
            )

            while time.time() - start_time < duration_sec:
                self._check_stop_requested()
                self._ensure_watchdog(watchdog_sec)
                cycle_start = time.time()
                status = self._exchange_and_log_status(settle_delay_sec)
                if status is not None:
                    self.read_success_count += 1
                    step_last_status = status
                    left_w, right_w = extract_step_power(status, product_code)
                    upper_msg = check_power_upper(step, left_w, right_w)
                    if upper_msg:
                        self._log(
                            f"[POWER_NG] step {step_index} {step['name']}: {upper_msg}"
                        )
                        raise PowerOutOfRangeError(
                            f"step {step_index} {step['name']}: {upper_msg}"
                        )
                    if cycle_start - start_time >= steady_check_offset:
                        steady_left_sum += left_w
                        steady_right_sum += right_w
                        steady_samples += 1
                    step_max_left_power = max(step_max_left_power, left_w)
                    step_max_right_power = max(step_max_right_power, right_w)
                elapsed = time.time() - cycle_start
                remaining_sleep = max(send_interval_sec - elapsed, 0.0)
                if remaining_sleep > 0:
                    if self._stop_event is not None:
                        self._stop_event.wait(remaining_sleep)
                    else:
                        time.sleep(remaining_sleep)

            if steady_samples:
                lower_msg = check_power_lower(
                    step,
                    steady_left_sum / steady_samples,
                    steady_right_sum / steady_samples,
                    steady_samples,
                )
                if lower_msg:
                    self._log(
                        f"[POWER_NG] step {step_index} {step['name']}: {lower_msg}"
                    )
                    raise PowerOutOfRangeError(
                        f"step {step_index} {step['name']}: {lower_msg}"
                    )

            self._record_step_summary(
                step_index=step_index,
                step=step,
                step_last_status=step_last_status,
                step_max_left_power=step_max_left_power,
                step_max_right_power=step_max_right_power,
            )

        self._log("Sequence completed successfully.")

    def _exchange_and_log_status(self, settle_delay_sec: float) -> RuntimeStatus | None:
        product_code = self.config.get("product", "A045")
        command_payload = build_command(self.current_power_ratio, product_code)
        try:
            binding = self._require_channel_binding()
            raw_status = lin_device_manager.exchange_status(
                binding["lin_sn"],
                binding["lin_index"],
                binding["baud_rate"],
                self.current_power_ratio,
                settle_delay_sec,
                product_code,
            )
            status = adapt_status(raw_status, product_code)
            self._check_product_fault(status, command_payload, product_code)
        except LinCommunicationError as exc:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._reinit_threshold:
                self._log(f"[RECOVER] re-initializing channel after {self._consecutive_failures} consecutive failures")
                try:
                    binding = self._require_channel_binding()
                    lin_device_manager.ensure_channel_initialized(
                        binding["lin_sn"],
                        binding["lin_index"],
                        binding["baud_rate"],
                        product_code,
                    )
                    self._consecutive_failures = 0
                    self.last_valid_status_time = time.time()
                    self._log("[RECOVER] channel re-initialized OK")
                except Exception as reinit_exc:
                    self._log(f"[RECOVER] re-init failed: {reinit_exc}")
            else:
                self._log(f"[WARN] exchange failed ({self._consecutive_failures}/{self._reinit_threshold}): {exc}")
            return None

        self._consecutive_failures = 0

        self.last_valid_status_time = time.time()
        product_code = self.config.get("product", "A045")
        current_signature = status_signature(status, product_code)
        should_print_snapshot = self.last_valid_status_time - self.last_status_print_time >= 1.0
        has_transition = current_signature != self.last_status_signature

        if should_print_snapshot or has_transition:
            self._print_status(status, command_payload, product_code, has_transition)
            self.last_status_print_time = self.last_valid_status_time
            self.last_status_signature = current_signature
        return status

    def _check_product_fault(self, status: RuntimeStatus, command_payload: List[int], product_code: str) -> None:
        code = str(product_code).strip().upper()
        confirm_frames = FAULT_STOP_CONFIRM_FRAMES.get(code)
        if confirm_frames is None or not status.error_level:
            self._consecutive_fault_frames = 0
            return
        self._consecutive_fault_frames += 1
        if self._consecutive_fault_frames < confirm_frames:
            return
        self._print_status(status, command_payload, product_code, True)
        raise ProductFaultError(
            f"{code} fault reported: state={status.run_status_text} code=0x{status.error_code:X}"
        )

    def _print_status(self, status: RuntimeStatus, command_payload: List[int], product_code: str, has_transition: bool) -> None:
        prefix = "[TRANSITION]" if has_transition else "[STATUS]"
        self._log(present_status(status, command_payload, product_code, prefix))

    def _ensure_watchdog(self, watchdog_sec: float) -> None:
        if time.time() - self.last_valid_status_time > watchdog_sec:
            raise LinCommunicationError(
                f"Communication watchdog timeout exceeded {watchdog_sec:.1f}s without valid status"
            )

    def _shutdown(self) -> None:
        self._log("Shutting down LIN runner, forcing 0% output...")
        self.current_power_ratio = 0
        time.sleep(0.3)
        try:
            binding = self._require_channel_binding()
            lin_device_manager.write_command(
                binding["lin_sn"],
                binding["lin_index"],
                binding["baud_rate"],
                0,
                self.config.get("product", DEFAULT_PRODUCT_CODE),
            )
        except Exception as exc:
            self._log(f"[WARN] final zero command failed: {exc}")
        for summary in self.step_summaries:
            self._log(summary)
        self._log(f"Summary: read_success={self.read_success_count}")

    def _record_step_summary(
        self,
        step_index: int,
        step: Dict[str, Any],
        step_last_status: RuntimeStatus | None,
        step_max_left_power: int,
        step_max_right_power: int,
    ) -> None:
        product_code = self.config.get("product", "A045")
        self.step_summaries.append(
            present_summary(step_index, step, step_last_status, step_max_left_power, step_max_right_power, product_code)
        )

    def _require_channel_binding(self) -> Dict[str, Any]:
        if self.channel_binding is None:
            raise LinServiceError("通道初始化失败: 未绑定 LIN 通道")
        return self.channel_binding


class RunStoppedError(Exception):
    """Raised when an in-process station run is stopped by the UI."""


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A045 LIN test runner")
    parser.add_argument("config", nargs="?", default=None, help="Path to config.json")
    parser.add_argument("--station", "-s", type=int, default=None, help="Station slot (1-10) to run")
    parser.add_argument("--stations", type=str, default=None, help="Comma-separated station slots for multi-station mode, e.g. 1,2")
    return parser.parse_args(argv[1:])


def _resolve_station_device(config: Dict[str, Any], station_slot: int) -> Dict[str, Any]:
    stations = config.get("stations", [])
    for station in stations:
        if station.get("slot") == station_slot:
            return station
    raise ConfigError(f"Station slot {station_slot} not found in config")


def _channel_binding_from_device_config(device_config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lin_sn": str(device_config["lin_sn"]).strip().upper(),
        "lin_index": int(device_config["lin_index"]),
        "baud_rate": int(device_config["baud_rate"]),
    }


def _ensure_channel_for_device_config(
    device_config: Dict[str, Any],
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> Dict[str, Any]:
    binding = _channel_binding_from_device_config(device_config)
    lin_device_manager.ensure_channel_initialized(
        binding["lin_sn"],
        binding["lin_index"],
        binding["baud_rate"],
        product_code,
    )
    return binding


def _run_multi_station(config: Dict[str, Any], station_slots: List[int]) -> int:
    stations = config.get("stations", [])
    station_map: Dict[int, Dict[str, Any]] = {s["slot"]: s for s in stations}
    for slot in station_slots:
        station = station_map.get(slot)
        if station is None:
            print(f"[ERROR] Station slot {slot} not configured")
            return 1
        sn = str(station.get("lin_sn", "")).strip().upper()
        if not sn:
            print(f"[ERROR] Station {slot} has no LIN SN configured")
            return 1

    print_lock = threading.Lock()
    threads: List[threading.Thread] = []
    results: Dict[int, int] = {}
    channel_bindings: Dict[int, Dict[str, Any]] = {}
    start_barrier = threading.Barrier(len(station_slots)) if len(station_slots) > 1 else None

    try:
        baud_rate = int(config.get("device", {}).get("baud_rate", 19200))
        all_sns: List[str] = []
        for slot in station_slots:
            sn = str(station_map[slot].get("lin_sn", "")).strip().upper()
            if sn and sn not in all_sns:
                all_sns.append(sn)
        lin_device_manager.open_all_devices(all_sns)

        for slot in station_slots:
            station = station_map[slot]
            sn = str(station.get("lin_sn", "")).strip().upper()
            lin_index = int(station.get("lin_index", 0))
            try:
                binding = {"lin_sn": sn, "lin_index": lin_index, "baud_rate": baud_rate}
                lin_device_manager.ensure_channel_initialized(
                    sn,
                    lin_index,
                    baud_rate,
                    config.get("product", DEFAULT_PRODUCT_CODE),
                )
                channel_bindings[slot] = binding
            except (DeviceNotFoundError, LinServiceError) as exc:
                with print_lock:
                    print(f"[ERROR] Failed to initialize LIN channel for station {slot} (SN={sn} index={lin_index}): {exc}")
                return 1

        for slot in station_slots:
            station = station_map[slot]
            sn = str(station.get("lin_sn", "")).strip().upper()
            station_cfg = dict(config)
            station_cfg["device"] = {
                "lin_sn": sn,
                "lin_index": int(station.get("lin_index", 0)),
                "baud_rate": baud_rate,
            }

            def _run_station(slot=slot, cfg=station_cfg, binding=channel_bindings[slot], gate=start_barrier):
                tag = f"[Station {slot}] "
                try:
                    runner = SequenceRunner(
                        cfg,
                        station_tag=tag,
                        print_lock=print_lock,
                        channel_binding=binding,
                        start_barrier=gate,
                    )
                    runner.run()
                    results[slot] = 0
                except Exception as exc:
                    with print_lock:
                        print(f"{tag}[ERROR] {exc}")
                    results[slot] = 1

            t = threading.Thread(target=_run_station, daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
    finally:
        lin_device_manager.close_all()

    failed = [slot for slot, code in results.items() if code != 0]
    if failed:
        with print_lock:
            print(f"Multi-station run complete: failures on stations {failed}")
        return 1
    with print_lock:
        print("Multi-station run complete: all stations passed.")
    return 0


def main(argv: List[str]) -> int:
    try:
        args = parse_args(argv)
        config_path = Path(args.config).expanduser().resolve() if args.config else (Path(__file__).resolve().parent / CONFIG_FILE)
        raw_config = load_config(config_path)

        if args.stations:
            station_slots = [int(s.strip()) for s in args.stations.split(",") if s.strip()]
            if not station_slots:
                print("[ERROR] --stations requires at least one station slot")
                return 1
            config = validate_config(raw_config, station_override=station_slots[0])
            config["stations"] = raw_config.get("stations", [])
            return _run_multi_station(config, station_slots)

        config = validate_config(raw_config, station_override=args.station)
        station_tag = f"[Station {args.station}] " if args.station else ""
        channel_binding = _ensure_channel_for_device_config(
            config["device"],
            config.get("product", DEFAULT_PRODUCT_CODE),
        )
        runner = SequenceRunner(config, station_tag=station_tag, channel_binding=channel_binding)
        runner.run()
        return 0
    except (ConfigError, DeviceNotFoundError, LinServiceError, LinCommunicationError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 1
    except Exception as exc:
        print(f"[ERROR] unexpected failure: {exc}")
        return 1
    finally:
        lin_device_manager.close_all()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
