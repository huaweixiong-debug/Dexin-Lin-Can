"""PLC control service adapted from the legacy LGV2 project."""

from __future__ import annotations

import threading
import time
from typing import Callable

from logger import logger

try:
    import snap7
    from snap7.util import get_bool, set_bool
except Exception as exc:  # pragma: no cover - runtime dependency
    snap7 = None
    get_bool = None
    set_bool = None
    _SNAP7_IMPORT_ERROR = exc
else:
    _SNAP7_IMPORT_ERROR = None


class PLCServiceError(Exception):
    """Raised when PLC service cannot be started or used."""


PLC_STATUS_BITS = {
    "SCAN_OK": 0,
    "PASS": 1,
    "FAIL": 2,
    "COMM_RESTART": 3,
    "COMM_RESTART_DONE": 4,
    "RESET": 5,
}
PLC_START_BYTE = 20
PLC_HEARTBEAT_BYTE = 17
PLC_STATION_BYTES = 5


def get_station_plc_mapping(station_idx: int) -> tuple[str, int, int]:
    """Return PLC name, local station index, and status byte for a station."""
    station_idx = int(station_idx)
    if station_idx < 1 or station_idx > 10:
        raise ValueError("station_idx must be between 1 and 10")
    local_index = (station_idx - 1) % PLC_STATION_BYTES
    return ("PLC1" if station_idx <= PLC_STATION_BYTES else "PLC2", local_index, local_index)


def decode_station_signals(m_data: bytes | bytearray, local_index: int) -> dict[str, bool]:
    """Decode one station from the OPC/S7 memory layout shown in the PLC tags."""
    if local_index < 0 or local_index >= PLC_STATION_BYTES:
        raise ValueError("local_index must be between 0 and 4")
    if len(m_data) <= PLC_START_BYTE:
        raise ValueError("PLC snapshot must contain M0..M20")

    def _bit(byte_offset: int, bit_offset: int) -> bool:
        return bool(m_data[byte_offset] & (1 << bit_offset))

    return {
        "start": _bit(PLC_START_BYTE, local_index),
        "reset": _bit(local_index, PLC_STATUS_BITS["RESET"]),
        "comm_restart": _bit(local_index, PLC_STATUS_BITS["COMM_RESTART"]),
        "heartbeat": _bit(PLC_HEARTBEAT_BYTE, local_index),
    }


class PLCController:
    def __init__(self, plc1_ip: str = "192.168.8.180", plc2_ip: str = "192.168.8.181") -> None:
        if snap7 is None or get_bool is None or set_bool is None:
            raise PLCServiceError(f"snap7 unavailable: {_SNAP7_IMPORT_ERROR}")

        self.plc1_ip = plc1_ip
        self.plc2_ip = plc2_ip
        self.rack = 0
        self.slot = 1
        self.client1 = snap7.Client()
        self.client2 = snap7.Client()
        self.connected1 = False
        self.connected2 = False
        self.lock = threading.RLock()
        self.monitor_thread: threading.Thread | None = None
        self.running = False
        self.log_callback: Callable[[str], None] | None = None
        self.on_start_signal: Callable[[int], None] | None = None
        self.on_stop_signal: Callable[[int], None] | None = None
        self.on_emergency_stop: Callable[[int], None] | None = None
        self.on_reset: Callable[[int], None] | None = None
        self.on_comm_restart: Callable[[int], None] | None = None
        self.last_states = {
            idx: {
                "start": False,
                "stop": False,
                "emergency_stop": False,
                "reset": False,
                "comm_restart": False,
                "heartbeat": False,
            }
            for idx in range(1, 11)
        }
        self.last_read_time: dict[int | str, float] = {}
        self.reconnect_interval_sec = 10.0
        self.next_reconnect_time = {"PLC1": 0.0, "PLC2": 0.0}
        self._last_connect_state: dict[str, bool | None] = {"PLC1": None, "PLC2": None}
        try:
            self.plc_mem_area = snap7.Area.MK
        except AttributeError:
            try:
                self.plc_mem_area = snap7.types.Areas.MK
            except AttributeError:
                self.plc_mem_area = 0x83
        # Suppress snap7 internal logging to avoid screen spam
        try:
            import logging
            logging.getLogger("snap7").setLevel(logging.CRITICAL)
        except Exception:
            pass

    def set_callbacks(
        self,
        on_start: Callable[[int], None] | None,
        on_stop: Callable[[int], None] | None,
        on_emergency_stop: Callable[[int], None] | None = None,
        on_reset: Callable[[int], None] | None = None,
        on_comm_restart: Callable[[int], None] | None = None,
    ) -> None:
        self.on_start_signal = on_start
        self.on_stop_signal = on_stop
        self.on_emergency_stop = on_emergency_stop
        self.on_reset = on_reset
        self.on_comm_restart = on_comm_restart

    def set_log_callback(self, log_callback: Callable[[str], None] | None) -> None:
        self.log_callback = log_callback

    def _emit_log(self, message: str) -> None:
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def connect(self) -> None:
        with self.lock:
            self.connected1 = self._connect_client(self.client1, self.plc1_ip, "PLC1")
            self.connected2 = self._connect_client(self.client2, self.plc2_ip, "PLC2")

    def _connect_client(self, client, ip: str, name: str) -> bool:
        now = time.time()
        if now < self.next_reconnect_time.get(name, 0.0):
            return False
        try:
            try:
                if client.get_connected():
                    client.disconnect()
                    time.sleep(0.1)
            except Exception:
                pass
            client.connect(ip, self.rack, self.slot)
            self.next_reconnect_time[name] = 0.0
            self._emit_log(f"{name} connected: {ip}")
            self._last_connect_state[name] = True
            return True
        except Exception as exc:
            self.next_reconnect_time[name] = time.time() + self.reconnect_interval_sec
            if self._last_connect_state.get(name) is not False:
                self._emit_log(f"{name} connect failed ({ip}): {exc}")
                self._last_connect_state[name] = False
            return False

    def disconnect(self) -> None:
        self.running = False
        with self.lock:
            for client, attr_name, plc_name in (
                (self.client1, "connected1", "PLC1"),
                (self.client2, "connected2", "PLC2"),
            ):
                try:
                    client.disconnect()
                except Exception:
                    pass
                setattr(self, attr_name, False)
                logger.info("%s disconnected", plc_name)

    def update_plc_ips(self, plc1_ip: str, plc2_ip: str) -> None:
        self.disconnect()
        self.plc1_ip = plc1_ip
        self.plc2_ip = plc2_ip
        self.connect()

    def start(self) -> None:
        self.running = True
        self.connect()
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        self.disconnect()

    def check_connection(self) -> None:
        with self.lock:
            for client, attr_name, ip, plc_name in (
                (self.client1, "connected1", self.plc1_ip, "PLC1"),
                (self.client2, "connected2", self.plc2_ip, "PLC2"),
            ):
                try:
                    is_connected = client.get_connected()
                except Exception:
                    is_connected = False
                if is_connected:
                    setattr(self, attr_name, True)
                    self.next_reconnect_time[plc_name] = 0.0
                    if self._last_connect_state.get(plc_name) is not True:
                        self._emit_log(f"{plc_name} reconnected: {ip}")
                        self._last_connect_state[plc_name] = True
                    continue
                if time.time() < self.next_reconnect_time.get(plc_name, 0.0):
                    setattr(self, attr_name, False)
                    continue
                try:
                    client.connect(ip, self.rack, self.slot)
                    setattr(self, attr_name, True)
                    self.next_reconnect_time[plc_name] = 0.0
                    self._emit_log(f"{plc_name} reconnected: {ip}")
                    self._last_connect_state[plc_name] = True
                except Exception as exc:
                    setattr(self, attr_name, False)
                    self.next_reconnect_time[plc_name] = time.time() + self.reconnect_interval_sec
                    if self._last_connect_state.get(plc_name) is not False:
                        self._emit_log(f"{plc_name} reconnect failed ({ip}): {exc}")
                        self._last_connect_state[plc_name] = False

    def monitor_loop(self) -> None:
        while self.running:
            try:
                self.check_connection()
                snapshots = {
                    "PLC1": self._read_plc_snapshot(self.client1, "PLC1") if self.connected1 else None,
                    "PLC2": self._read_plc_snapshot(self.client2, "PLC2") if self.connected2 else None,
                }
                for station_idx in range(1, 11):
                    self._poll_station(station_idx, snapshots)
                time.sleep(0.1)
            except Exception as exc:
                logger.error("PLC monitor loop failed: %s", exc)
                self._throttled_log("loop", f"PLC monitor loop failed: {exc}")
                time.sleep(1)

    def _read_plc_snapshot(self, client, plc_name: str):
        """Read M0..M20 in one request so all station bits use one PLC snapshot."""
        for attempt in range(3):
            try:
                with self.lock:
                    return client.read_area(self.plc_mem_area, 0, 0, PLC_START_BYTE + 1)
            except Exception as exc:
                logger.warning("%s read M0..M20 failed %s/3: %s", plc_name, attempt + 1, exc)
                time.sleep(0.2)
        self._throttled_log(f"snapshot_{plc_name}", f"{plc_name} read M0..M20 failed")
        return None

    def _poll_station(self, station_idx: int, snapshots: dict[str, bytearray | None]) -> None:
        plc_name, local_index, _status_byte_offset = get_station_plc_mapping(station_idx)
        m_data = snapshots.get(plc_name)
        if m_data is None or len(m_data) <= PLC_START_BYTE:
            return

        # Per the OPC tag definitions: M0..M4 are station status bytes,
        # M20.0..M20.4 are station start commands, and M17.0..M17.4 are heartbeats.
        signals = decode_station_signals(m_data, local_index)
        start_signal = signals["start"]
        reset_signal = signals["reset"]
        comm_restart_signal = signals["comm_restart"]
        heartbeat_signal = signals["heartbeat"]

        self._dispatch_edge(station_idx, "start", start_signal, self.on_start_signal, f"PLC start signal: station {station_idx}")
        self._dispatch_edge(
            station_idx,
            "comm_restart",
            comm_restart_signal,
            self.on_comm_restart,
            f"PLC communication restart signal: station {station_idx}",
        )
        self._dispatch_edge(station_idx, "reset", reset_signal, self.on_reset, f"PLC reset signal: station {station_idx}")

        self.last_states[station_idx]["start"] = start_signal
        self.last_states[station_idx]["stop"] = False
        self.last_states[station_idx]["emergency_stop"] = False
        self.last_states[station_idx]["reset"] = reset_signal
        self.last_states[station_idx]["comm_restart"] = comm_restart_signal
        self.last_states[station_idx]["heartbeat"] = heartbeat_signal

    def _dispatch_edge(
        self,
        station_idx: int,
        key: str,
        current_value: bool,
        callback: Callable[[int], None] | None,
        message: str,
    ) -> None:
        previous_value = self.last_states[station_idx][key]
        if current_value and not previous_value:
            self._emit_log(message)
            if callback:
                callback(station_idx)

    def _throttled_log(self, key: int | str, message: str, interval: float = 10.0) -> None:
        now = time.time()
        last_time = self.last_read_time.get(key, 0.0)
        if now - last_time >= interval:
            logger.info(message)
            if self.log_callback:
                self.log_callback(message)
            self.last_read_time[key] = now

    def write_status(self, station_idx: int, status_type: str, value: bool = True) -> bool:
        plc_name, local_index, byte_offset = get_station_plc_mapping(station_idx)
        client = self.client1 if plc_name == "PLC1" and self.connected1 else None
        if plc_name == "PLC2" and self.connected2:
            client = self.client2
        plc_ip = self.plc1_ip if plc_name == "PLC1" else self.plc2_ip

        if client is None:
            self._throttled_log(
                f"offline_write_{station_idx}_{status_type}",
                f"Cannot write {status_type} for station {station_idx}: PLC offline",
                interval=10.0,
            )
            return False

        bit_offset = PLC_STATUS_BITS.get(status_type)
        if bit_offset is None:
            logger.error("Unknown PLC status type: %s", status_type)
            return False

        for attempt in range(5):
            try:
                with self.lock:
                    if not client.get_connected():
                        plc_name_for_write = plc_name
                        if time.time() < self.next_reconnect_time.get(plc_name_for_write, 0.0):
                            raise PLCServiceError(f"{plc_name_for_write} reconnect cooldown active")
                        client.connect(plc_ip, self.rack, self.slot)
                        self.next_reconnect_time[plc_name_for_write] = 0.0
                        time.sleep(0.2)
                    current_data = client.read_area(self.plc_mem_area, 0, byte_offset, 1)
                    set_bool(current_data, 0, bit_offset, value)
                    client.write_area(self.plc_mem_area, 0, byte_offset, current_data)
                self._throttled_log(
                    f"plc_write_{station_idx}_{status_type}",
                    f"PLC write: station {station_idx} {status_type}={value}",
                    interval=30.0,
                )
                return True
            except Exception as exc:
                if "cooldown active" not in str(exc):
                    self.next_reconnect_time[plc_name] = time.time() + self.reconnect_interval_sec
                self._throttled_log(
                    f"write_fail_{plc_name}_{station_idx}_{status_type}",
                    f"{plc_name} write failed station {station_idx} {status_type} attempt {attempt + 1}/5: {exc}",
                    interval=10.0,
                )
                time.sleep(0.5)
        return False

    def write_status_pulse(self, station_idx: int, status_type: str, duration: float = 2.0) -> bool:
        success = self.write_status(station_idx, status_type, True)
        if not success:
            return False

        def _reset() -> None:
            self.write_status(station_idx, status_type, False)

        threading.Timer(duration, _reset).start()
        return True

    def write_test_result(self, station_idx: int, result: str) -> bool:
        # Hold PASS/FAIL until the PLC sends a reset signal; the UI clears
        # both bits in _process_plc_stop_like_signal().  A 2 s pulse was too
        # short for the PLC program to latch reliably.
        if result == "PASS":
            self.write_status(station_idx, "FAIL", False)
            return self.write_status(station_idx, "PASS", True)
        if result == "FAIL":
            self.write_status(station_idx, "PASS", False)
            return self.write_status(station_idx, "FAIL", True)
        logger.error("Unknown test result: %s", result)
        return False
