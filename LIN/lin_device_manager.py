"""Centralized USB2XXX/LIN device manager for supported products."""

from __future__ import annotations

import threading
import time
from ctypes import byref, c_char, c_uint
from typing import Any, Dict, List, Tuple

from logger import logger
from product_catalog import DEFAULT_PRODUCT_CODE
from lin_service import (
    DeviceNotFoundError,
    LinCommunicationError,
    LinDeviceConfig,
    LinService,
    LinServiceError,
    NativeDriverError,
    _call_native,
    _safe_close_device,
    normalize_serial,
)
from usb_device import DEVICE_INFO, DEV_GetDeviceInfo, USB_OpenDevice, USB_ScanDevice
from usb2lin_ex import LIN_EX_CtrlPowerOut


class LinDeviceManager:
    def __init__(self) -> None:
        self.management_lock = threading.RLock()
        self.device_catalog: Dict[str, Dict[str, Any]] = {}
        self.device_locks: Dict[str, threading.RLock] = {}
        self.channel_state: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.scanned = False

    def scan_devices_once(self, force: bool = False) -> List[Dict[str, Any]]:
        with self.management_lock:
            if force and self._has_open_devices_locked():
                logger.info("Skip force scan while LIN devices are open; returning cached catalog.")
                return self._catalog_snapshot_locked()

            if self.scanned and not force and self.device_catalog:
                return self._catalog_snapshot_locked()

            return self._scan_devices_locked()

    def open_all_devices(self, sn_list: List[str]) -> None:
        normalized_sns: List[str] = []
        for sn in sn_list:
            normalized = normalize_serial(sn)
            if normalized and normalized not in normalized_sns:
                normalized_sns.append(normalized)
        if not normalized_sns:
            return

        with self.management_lock:
            all_open = all(
                self.device_catalog.get(sn, {}).get("opened") for sn in normalized_sns
            )
            if all_open:
                return
            self._scan_and_open_targets_locked(normalized_sns)

    def get_or_open_device(self, sn: str) -> int:
        normalized_sn = normalize_serial(sn)
        if not normalized_sn:
            raise DeviceNotFoundError("设备发现失败: 未提供 LIN 序列号")

        with self.management_lock:
            entry = self.device_catalog.get(normalized_sn)
            if entry and entry.get("opened", False):
                entry["last_seen"] = time.time()
                self.device_locks.setdefault(normalized_sn, threading.RLock())
                return int(entry["handle"])

            if self._has_open_devices_locked():
                # Other devices are open — try cached handle direct open first, then scan
                if entry is not None:
                    try:
                        just_opened = bool(_call_native("USB_OpenDevice", USB_OpenDevice, int(entry["handle"])))
                        if just_opened:
                            entry["opened"] = True
                            entry["last_seen"] = time.time()
                            self.device_locks.setdefault(normalized_sn, threading.RLock())
                            return int(entry["handle"])
                    except Exception:
                        pass
                if self._has_initialized_channels_locked():
                    raise LinServiceError(
                        f"设备 {normalized_sn} 未在首轮启动前预打开，当前已有 LIN 通道处于活动状态，"
                        "禁止在运行中重新扫描 USB 设备，以免打断已运行工位。"
                    )
                opened_handle = self._scan_and_open_target_locked(normalized_sn)
                if opened_handle is not None:
                    return opened_handle
                raise LinServiceError(
                    f"设备 {normalized_sn} 未预打开且扫描失败。"
                    "请先停止所有工位，重新加载配置后再试。"
                )

            for attempt in range(2):
                opened_handle = self._scan_and_open_target_locked(normalized_sn)
                if opened_handle is not None:
                    return opened_handle
                if attempt == 0:
                    continue
                break

            known_serials = sorted(self.device_catalog.keys())
            raise LinServiceError(
                f"设备发现失败: 无法打开 USB2XXX 设备 SN={normalized_sn}; scanned={known_serials}。"
                '请确认设备未被其他程序占用，并可点击"扫描设备"后重试。'
            )

    def ensure_channel_initialized(
        self,
        sn: str,
        lin_index: int,
        baud_rate: int,
        product_code: str = DEFAULT_PRODUCT_CODE,
    ) -> LinService:
        normalized_sn = normalize_serial(sn)
        channel_index = int(lin_index)
        channel_baud = int(baud_rate)
        normalized_product = str(product_code).strip().upper() or DEFAULT_PRODUCT_CODE
        key = (normalized_sn, channel_index)

        with self.management_lock:
            state = self.channel_state.get(key)
            if (
                state
                and state.get("initialized")
                and state.get("baud_rate") == channel_baud
                and state.get("product_code", DEFAULT_PRODUCT_CODE) == normalized_product
                and state.get("service") is not None
                and state["service"].is_ready
            ):
                return state["service"]

            handle = self.get_or_open_device(normalized_sn)
            device_lock = self.device_locks.setdefault(normalized_sn, threading.RLock())
            if (
                state
                and state.get("service") is not None
                and state.get("baud_rate") == channel_baud
                and state.get("product_code", DEFAULT_PRODUCT_CODE) == normalized_product
            ):
                service = state["service"]
                service._handle = handle
            else:
                if state and state.get("service") is not None:
                    try:
                        state["service"].close()
                    except Exception:
                        pass
                service = LinService(
                    LinDeviceConfig(normalized_sn, channel_index, channel_baud, normalized_product),
                    handle=handle,
                    device_lock=device_lock,
                    owns_handle=False,
                )
            self.channel_state[key] = {
                "initialized": False,
                "baud_rate": channel_baud,
                "product_code": normalized_product,
                "service": service,
                "last_error": "",
            }

        try:
            service.initialize()
        except Exception as exc:
            with self.management_lock:
                state = self.channel_state.setdefault(
                    key,
                    {
                        "initialized": False,
                        "baud_rate": channel_baud,
                        "product_code": normalized_product,
                        "service": service,
                        "last_error": "",
                    },
                )
                state["initialized"] = False
                state["last_error"] = str(exc)
            raise LinServiceError(
                f"通道初始化失败: SN={normalized_sn} LIN Index={channel_index}: {exc}"
            ) from exc

        with self.management_lock:
            state = self.channel_state[key]
            state["initialized"] = True
            state["last_error"] = ""
        return service

    def is_channel_initialized(self, sn: str, lin_index: int, baud_rate: int | None = None) -> bool:
        normalized_sn = normalize_serial(sn)
        key = (normalized_sn, int(lin_index))
        with self.management_lock:
            state = self.channel_state.get(key)
            if not state or not state.get("initialized"):
                return False
            if baud_rate is not None and state.get("baud_rate") != int(baud_rate):
                return False
            service = state.get("service")
            return bool(service and service.is_ready)

    def read_status(
        self,
        sn: str,
        lin_index: int,
        baud_rate: int,
        product_code: str = DEFAULT_PRODUCT_CODE,
    ):
        service = self.ensure_channel_initialized(sn, lin_index, baud_rate, product_code)
        try:
            return service.read_status()
        except NativeDriverError as exc:
            self.invalidate_channel(sn, lin_index)
            raise LinServiceError(
                f"状态读取失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc
        except LinCommunicationError as exc:
            raise LinCommunicationError(
                f"状态读取失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc
        except LinServiceError as exc:
            raise LinServiceError(
                f"状态读取失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc

    def write_command(
        self,
        sn: str,
        lin_index: int,
        baud_rate: int,
        power_ratio: int,
        product_code: str = DEFAULT_PRODUCT_CODE,
    ):
        service = self.ensure_channel_initialized(sn, lin_index, baud_rate, product_code)
        try:
            return service.send_command(power_ratio)
        except NativeDriverError as exc:
            self.invalidate_channel(sn, lin_index)
            raise LinServiceError(
                f"命令写入失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc
        except LinCommunicationError as exc:
            raise LinCommunicationError(
                f"命令写入失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc
        except LinServiceError as exc:
            raise LinServiceError(
                f"命令写入失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc

    def exchange_status(
        self,
        sn: str,
        lin_index: int,
        baud_rate: int,
        power_ratio: int,
        settle_delay: float,
        product_code: str = DEFAULT_PRODUCT_CODE,
    ):
        service = self.ensure_channel_initialized(sn, lin_index, baud_rate, product_code)
        try:
            return service.exchange_status(power_ratio, settle_delay)
        except NativeDriverError as exc:
            self.invalidate_channel(sn, lin_index)
            raise LinServiceError(
                f"状态读取失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc
        except LinCommunicationError as exc:
            raise LinCommunicationError(
                f"状态读取失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc
        except LinServiceError as exc:
            raise LinServiceError(
                f"状态读取失败: SN={normalize_serial(sn)} LIN Index={int(lin_index)}: {exc}"
            ) from exc

    def invalidate_channel(self, sn: str, lin_index: int) -> None:
        normalized_sn = normalize_serial(sn)
        key = (normalized_sn, int(lin_index))
        with self.management_lock:
            state = self.channel_state.pop(key, None)
        if state and state.get("service") is not None:
            try:
                state["service"].close()
            except Exception:
                pass

    def close_device(self, sn: str) -> None:
        normalized_sn = normalize_serial(sn)
        with self.management_lock:
            keys = [key for key in self.channel_state if key[0] == normalized_sn]
        for key in keys:
            self.invalidate_channel(*key)

        with self.management_lock:
            entry = self.device_catalog.get(normalized_sn)
            if entry and entry.get("opened"):
                _safe_close_device(int(entry["handle"]))
                entry["opened"] = False

    def close_all(self) -> None:
        with self.management_lock:
            keys = list(self.channel_state.keys())
        for key in keys:
            self.invalidate_channel(*key)

        with self.management_lock:
            for entry in self.device_catalog.values():
                if entry.get("opened"):
                    _safe_close_device(int(entry["handle"]))
                    entry["opened"] = False

    def _scan_devices_locked(self) -> List[Dict[str, Any]]:
        dev_handles = (c_uint * 20)()
        count = _call_native("USB_ScanDevice", USB_ScanDevice, byref(dev_handles))
        refreshed_catalog: Dict[str, Dict[str, Any]] = {}
        if count <= 0:
            self.device_catalog = {}
            self.scanned = True
            return []

        devices: List[Dict[str, Any]] = []
        for index in range(count):
            handle = dev_handles[index]
            opened = False
            try:
                opened = bool(_call_native("USB_OpenDevice", USB_OpenDevice, handle))
                if not opened:
                    continue
                identity = self._read_device_identity(handle)
                if identity is None:
                    # Retry with close/reopen
                    _safe_close_device(handle)
                    time.sleep(0.1)
                    if not _call_native("USB_OpenDevice(retry)", USB_OpenDevice, handle):
                        opened = False
                        continue
                    identity = self._read_device_identity(handle)
                    if identity is None:
                        _safe_close_device(handle)
                        opened = False
                        continue
                serial, description = identity
                entry = {
                    "scan_index": index,
                    "handle": int(handle),
                    "serial": serial,
                    "description": description,
                    "opened": False,
                    "last_seen": time.time(),
                }
                refreshed_catalog[serial] = entry
                devices.append(dict(entry))
            except LinServiceError as exc:
                logger.error("LIN scan failed for handle=%s index=%s: %s", handle, index, exc)
            finally:
                if opened:
                    _safe_close_device(handle)
                    time.sleep(0.05)

        self.device_catalog = refreshed_catalog
        self.scanned = True
        return self._catalog_snapshot_locked()

    def _scan_and_open_target_locked(self, target_sn: str) -> int | None:
        dev_handles = (c_uint * 20)()
        count = _call_native("USB_ScanDevice", USB_ScanDevice, byref(dev_handles))
        if count <= 0:
            self.device_catalog = {}
            self.scanned = True
            return None

        open_handles: Dict[int, str] = {}
        for serial, entry in self.device_catalog.items():
            if entry.get("opened"):
                open_handles[int(entry["handle"])] = serial

        refreshed_catalog: Dict[str, Dict[str, Any]] = {}
        target_handle: int | None = None
        for index in range(count):
            handle = dev_handles[index]
            handle_int = int(handle)
            just_opened = False
            keep_open = False
            try:
                if handle_int in open_handles:
                    identity = self._read_device_identity(handle_int)
                    if identity is None:
                        continue
                    serial, description = identity
                    keep_open = serial == target_sn or open_handles[handle_int] == target_sn
                else:
                    just_opened = bool(_call_native("USB_OpenDevice", USB_OpenDevice, handle))
                    if not just_opened:
                        continue
                    time.sleep(0.05)
                    identity = self._read_device_identity(handle_int)
                    if identity is None:
                        _safe_close_device(handle_int)
                        time.sleep(0.1)
                        if not _call_native("USB_OpenDevice(retry)", USB_OpenDevice, handle):
                            continue
                        time.sleep(0.05)
                        identity = self._read_device_identity(handle_int)
                        if identity is None:
                            continue
                    serial, description = identity
                    keep_open = serial == target_sn

                entry = {
                    "scan_index": index,
                    "handle": handle_int,
                    "serial": serial,
                    "description": description,
                    "opened": keep_open or handle_int in open_handles,
                    "last_seen": time.time(),
                }
                refreshed_catalog[serial] = entry
                if keep_open:
                    target_handle = handle_int
                    if serial not in open_handles:
                        self.device_locks.setdefault(serial, threading.RLock())
            except LinServiceError as exc:
                logger.error("LIN target scan failed for handle=%s index=%s: %s", handle, index, exc)
            finally:
                if just_opened and not keep_open:
                    _safe_close_device(handle_int)
                    time.sleep(0.05)
                if just_opened:
                    time.sleep(0.2)

        self.device_catalog = refreshed_catalog
        self.scanned = True
        return target_handle

    def _scan_and_open_targets_locked(self, target_sns: List[str]) -> Dict[str, int]:
        target_set = {normalize_serial(sn) for sn in target_sns if normalize_serial(sn)}
        if not target_set:
            return {}

        dev_handles = (c_uint * 20)()
        count = _call_native("USB_ScanDevice", USB_ScanDevice, byref(dev_handles))
        if count <= 0:
            self.device_catalog = {}
            self.scanned = True
            raise LinServiceError(f"设备发现失败: 未扫描到 USB2XXX 设备，目标 SN={sorted(target_set)}")

        open_handles: Dict[int, str] = {}
        for serial, entry in self.device_catalog.items():
            if entry.get("opened"):
                open_handles[int(entry["handle"])] = serial

        refreshed_catalog: Dict[str, Dict[str, Any]] = {}
        opened_targets: Dict[str, int] = {}
        unknown_open_handles: List[Dict[str, Any]] = []

        for index in range(count):
            handle = dev_handles[index]
            handle_int = int(handle)
            just_opened = False
            keep_open = handle_int in open_handles
            try:
                if handle_int in open_handles:
                    identity = self._read_device_identity(handle_int)
                    if identity is None:
                        continue
                    serial, description = identity
                else:
                    just_opened = bool(_call_native("USB_OpenDevice", USB_OpenDevice, handle))
                    if not just_opened:
                        logger.error("USB_OpenDevice failed while pre-opening handle=%s index=%s", handle_int, index)
                        continue

                    time.sleep(0.05)
                    identity = self._read_device_identity(handle_int)
                    if identity is None:
                        logger.error("DEV_GetDeviceInfo failed while pre-opening handle=%s index=%s", handle_int, index)
                        unknown_open_handles.append(
                            {
                                "scan_index": index,
                                "handle": handle_int,
                                "description": "UNKNOWN_DEV_GET_INFO_FAILED",
                            }
                        )
                        keep_open = True
                        continue

                    serial, description = identity
                    keep_open = serial in target_set

                entry = {
                    "scan_index": index,
                    "handle": handle_int,
                    "serial": serial,
                    "description": description,
                    "opened": keep_open,
                    "last_seen": time.time(),
                }
                refreshed_catalog[serial] = entry
                if keep_open and serial in target_set:
                    opened_targets[serial] = handle_int
                    self.device_locks.setdefault(serial, threading.RLock())
            except LinServiceError as exc:
                logger.error("LIN batch pre-open failed for handle=%s index=%s: %s", handle_int, index, exc)
            finally:
                if just_opened and not keep_open:
                    _safe_close_device(handle_int)
                    time.sleep(0.05)

        self.device_catalog = refreshed_catalog
        self.scanned = True

        missing = sorted(target_set - set(opened_targets.keys()))
        if missing and len(missing) == len(unknown_open_handles):
            ordered_missing = [sn for sn in target_sns if sn in missing]
            for sn, unknown in zip(ordered_missing, unknown_open_handles):
                handle_int = int(unknown["handle"])
                try:
                    power_ret = _call_native(
                        "LIN_EX_CtrlPowerOut",
                        LIN_EX_CtrlPowerOut,
                        handle_int,
                        0,
                        1,
                    )
                except Exception as exc:
                    power_ret = None
                    logger.error(
                        "[LIN_OPEN_FALLBACK] Capability probe failed for unknown handle=%s scan_index=%s: %s",
                        handle_int,
                        unknown["scan_index"],
                        exc,
                    )
                if power_ret != 0:
                    logger.error(
                        "[LIN_OPEN_FALLBACK] Unknown handle=%s scan_index=%s is not usable as LIN device; "
                        "LIN_EX_CtrlPowerOut returned %s. Configured SN=%s will remain unopened.",
                        handle_int,
                        unknown["scan_index"],
                        power_ret,
                        sn,
                    )
                    _safe_close_device(handle_int)
                    time.sleep(0.05)
                    continue
                self.device_catalog[sn] = {
                    "scan_index": int(unknown["scan_index"]),
                    "handle": handle_int,
                    "serial": sn,
                    "description": unknown["description"],
                    "opened": True,
                    "last_seen": time.time(),
                    "identity_fallback": True,
                }
                opened_targets[sn] = handle_int
                self.device_locks.setdefault(sn, threading.RLock())
                logger.warning(
                    "[LIN_OPEN_FALLBACK] DEV_GetDeviceInfo failed for handle=%s scan_index=%s; "
                    "assigned to configured SN=%s by station order.",
                    handle_int,
                    unknown["scan_index"],
                    sn,
                )
            missing = sorted(target_set - set(opened_targets.keys()))

        if missing:
            assigned_handles = set(opened_targets.values())
            for unknown in unknown_open_handles:
                handle_int = int(unknown["handle"])
                if handle_int not in assigned_handles:
                    _safe_close_device(handle_int)
                    time.sleep(0.05)
            logger.error("[LIN_OPEN] Failed to pre-open target SNs: %s; opened=%s", missing, sorted(opened_targets.keys()))
        else:
            assigned_handles = set(opened_targets.values())
            for unknown in unknown_open_handles:
                handle_int = int(unknown["handle"])
                if handle_int not in assigned_handles:
                    _safe_close_device(handle_int)
                    time.sleep(0.05)
            logger.info("[LIN_OPEN] Pre-opened all target SNs: %s", sorted(opened_targets.keys()))
        return opened_targets

    def _read_device_identity(self, handle: int) -> tuple[str, str] | None:
        info = DEVICE_INFO()
        function_str = (c_char * 256)()
        for attempt in range(3):
            try:
                result = _call_native("DEV_GetDeviceInfo", DEV_GetDeviceInfo, handle, byref(info), byref(function_str))
            except LinServiceError as exc:
                logger.error("DEV_GetDeviceInfo failed handle=%s attempt=%s: %s", handle, attempt + 1, exc)
                result = False
            if result:
                serial = normalize_serial("".join(f"{info.SerialNumber[idx]:08X}" for idx in range(len(info.SerialNumber))))
                description = bytes(function_str.value).decode("ascii", errors="ignore")
                return serial, description
            # Create fresh structs for next attempt
            info = DEVICE_INFO()
            function_str = (c_char * 256)()
            time.sleep(0.1)
        return None

    def _catalog_snapshot_locked(self) -> List[Dict[str, Any]]:
        return [dict(self.device_catalog[serial]) for serial in sorted(self.device_catalog.keys())]

    def _has_open_devices_locked(self) -> bool:
        return any(bool(entry.get("opened")) for entry in self.device_catalog.values())

    def _has_initialized_channels_locked(self) -> bool:
        return any(bool(state.get("initialized")) for state in self.channel_state.values())


lin_device_manager = LinDeviceManager()
