"""LIN channel executor."""

from __future__ import annotations

import threading
import time
from ctypes import byref, c_ubyte
from dataclasses import dataclass
from typing import Any, Callable, List

from product_catalog import DEFAULT_PRODUCT_CODE
from runtime_protocols import RuntimeProtocolAdapter, get_runtime_protocol
from usb2lin_ex import (
    LIN_EX_CHECK_EXT,
    LIN_EX_CtrlPowerOut,
    LIN_EX_MASTER,
    LIN_EX_MSG,
    LIN_EX_MSG_TYPE_BK,
    LIN_EX_MSG_TYPE_MR,
    LIN_EX_MSG_TYPE_MW,
    LIN_EX_SUCCESS,
    LIN_EX_Init,
    LIN_EX_MasterRead,
    LIN_EX_MasterSync,
)
from usb_device import USB_CloseDevice


class LinServiceError(Exception):
    """Base error raised by the LIN service layer."""


class DeviceNotFoundError(LinServiceError):
    """Raised when the configured USB2XXX serial number cannot be found."""


class LinCommunicationError(LinServiceError):
    """Raised when a LIN frame cannot be sent or read."""


class NativeDriverError(LinServiceError):
    """Raised when the USB2XXX native driver reports a low-level failure."""


_NATIVE_DRIVER_LOCK = threading.RLock()


@dataclass
class LinDeviceConfig:
    lin_sn: str
    lin_index: int
    baud_rate: int = 19200
    product_code: str = DEFAULT_PRODUCT_CODE


def scan_usb2xxx_devices() -> List[dict]:
    from lin_device_manager import lin_device_manager

    return lin_device_manager.scan_devices_once(force=False)


def normalize_serial(serial: str) -> str:
    return str(serial).strip().upper()


class LinService:
    def __init__(
        self,
        config: LinDeviceConfig,
        handle: int | None = None,
        shared_handle: int | None = None,
        device_lock: threading.RLock | None = None,
        owns_handle: bool = False,
    ):
        self.config = config
        self._handle = handle if handle is not None else shared_handle
        self._owns_handle = owns_handle
        self._opened = self._handle is not None
        self._initialized = False
        self._lock = device_lock or threading.RLock()
        self._protocol: RuntimeProtocolAdapter = get_runtime_protocol(self.config.product_code)
        self.send_failures = 0
        self.read_failures = 0

    @property
    def is_ready(self) -> bool:
        return self._opened and self._initialized and self._handle is not None

    def initialize(self) -> None:
        with self._lock:
            if self.is_ready:
                return
            if self._handle is None:
                raise LinServiceError("设备发现失败: 未提供已打开的 USB2XXX 句柄")

            last_error = None
            for attempt in range(3):
                self._opened = False
                self._initialized = False
                if attempt > 0:
                    time.sleep(0.3 * attempt)
                try:
                    power_result = _call_native(
                        "LIN_EX_CtrlPowerOut",
                        LIN_EX_CtrlPowerOut,
                        self._handle,
                        self.config.lin_index,
                        1,
                    )
                    if power_result != LIN_EX_SUCCESS:
                        raise LinServiceError(f"LIN_EX_CtrlPowerOut code={power_result}")
                    time.sleep(0.3)

                    init_result = _call_native(
                        "LIN_EX_Init",
                        LIN_EX_Init,
                        self._handle,
                        self.config.lin_index,
                        self.config.baud_rate,
                        LIN_EX_MASTER,
                    )
                    if init_result != LIN_EX_SUCCESS:
                        raise LinServiceError(f"LIN_EX_Init code={init_result}")

                    self._opened = True
                    self._initialized = True
                    time.sleep(0.2)
                    return
                except (LinServiceError, LinCommunicationError) as exc:
                    last_error = exc

            if self._owns_handle:
                _safe_close_device(self._handle)
            self._opened = False
            self._initialized = False
            raise LinServiceError(
                f"通道初始化失败: SN={self.config.lin_sn} LIN Index={self.config.lin_index}: {last_error} (retried 3x)"
            )

    def close(self) -> None:
        with self._lock:
            if self._opened and self._owns_handle and self._handle is not None:
                _safe_close_device(self._handle)
            self._opened = False
            self._initialized = False
            if self._owns_handle:
                self._handle = None

    def send_command(self, control_value: int) -> List[int]:
        payload = self._protocol.build_command_payload(control_value)
        with self._lock:
            self._ensure_ready()
            self.send_break()
            ret, _ = self._master_sync(self._protocol.command_pid, payload, LIN_EX_MSG_TYPE_MW)
            if ret <= 0:
                self.send_failures += 1
                raise LinCommunicationError(
                    f"命令写入失败: PID=0x{self._protocol.command_pid:02X}, code={ret}"
                )
        return payload

    def read_status(self):
        with self._lock:
            self._ensure_ready()
            self.send_break()
            command_payload = self._protocol.build_command_payload(0)
            payload = self._read_frame_payload(self._protocol.status_pid, command_payload)
            status = self._protocol.parse_status_payload(payload)
            return self._read_and_combine_aux_status(status)

    def exchange_status(self, control_value: int, settle_delay_sec: float):
        payload = self._protocol.build_command_payload(control_value)
        with self._lock:
            self._ensure_ready()
            last_error = None

            for extra_break_before_read in (False, True):
                try:
                    return self._exchange_once(payload, settle_delay_sec, extra_break_before_read)
                except LinCommunicationError as exc:
                    last_error = exc
                    time.sleep(0.01)

            self.read_failures += 1
            raise LinCommunicationError(str(last_error) if last_error else "状态读取失败: LIN exchange failed")

    def send_break(self) -> None:
        tx_msg = LIN_EX_MSG()
        tx_msg.MsgType = LIN_EX_MSG_TYPE_BK
        rx_msg = LIN_EX_MSG()
        ret = _call_native(
            "LIN_EX_MasterSync",
            LIN_EX_MasterSync,
            self._handle,
            self.config.lin_index,
            byref(tx_msg),
            byref(rx_msg),
            1,
        )
        if ret <= 0:
            raise LinCommunicationError(f"BREAK code={ret}")

    def _ensure_ready(self) -> None:
        if not self.is_ready:
            raise LinServiceError("通道初始化失败: LIN service is not initialized")

    def _master_sync(self, pid: int, payload: List[int], msg_type: int):
        in_msg = LIN_EX_MSG()
        out_msg = LIN_EX_MSG()
        in_msg.MsgType = msg_type
        in_msg.Timestamp = 10
        in_msg.PID = pid
        in_msg.CheckType = LIN_EX_CHECK_EXT
        in_msg.DataLen = self._protocol.frame_size

        for idx, value in enumerate(payload[: self._protocol.frame_size]):
            in_msg.Data[idx] = value & 0xFF

        ret = _call_native(
            "LIN_EX_MasterSync",
            LIN_EX_MasterSync,
            self._handle,
            self.config.lin_index,
            byref(in_msg),
            byref(out_msg),
            1,
        )
        return ret, out_msg

    def _exchange_once(self, command_payload: List[int], settle_delay_sec: float, extra_break_before_read: bool):
        self.send_break()
        ret, _ = self._master_sync(self._protocol.command_pid, command_payload, LIN_EX_MSG_TYPE_MW)
        if ret <= 0:
            self.send_failures += 1
            raise LinCommunicationError(f"命令写入失败: PID=0x{self._protocol.command_pid:02X}, code={ret}")

        if settle_delay_sec > 0:
            time.sleep(settle_delay_sec)

        if extra_break_before_read:
            self.send_break()
            time.sleep(0.01)

        status_payload = self._read_frame_payload(self._protocol.status_pid, command_payload)
        status = self._protocol.parse_status_payload(status_payload)
        return self._read_and_combine_aux_status(status)

    def _read_and_combine_aux_status(self, status):
        protocol = self._protocol
        if protocol.aux_status_pid is None:
            return status
        if protocol.parse_aux_status_payload is None or protocol.combine_status is None:
            raise LinCommunicationError(
                f"辅助状态配置不完整: product={protocol.product_code} PID=0x{protocol.aux_status_pid:02X}"
            )

        self.send_break()
        aux_payload = self._read_frame_payload(protocol.aux_status_pid, None)
        aux_status = protocol.parse_aux_status_payload(aux_payload)
        return protocol.combine_status(status, aux_status)

    def _read_frame_payload(self, pid: int, echo_payload: List[int] | None) -> List[int]:
        ret, out_msg = self._master_sync(
            pid,
            [0x00] * self._protocol.frame_size,
            LIN_EX_MSG_TYPE_MR,
        )
        if ret > 0 and out_msg.DataLen > 0:
            payload = [
                out_msg.Data[i] & 0xFF
                for i in range(min(out_msg.DataLen, self._protocol.frame_size))
            ]
            if len(payload) == self._protocol.frame_size and (
                echo_payload is None or not self._is_echo_payload(payload, echo_payload)
            ):
                return payload

        payload = self._read_status_payload(pid, echo_payload)
        if len(payload) != self._protocol.frame_size:
            raise LinCommunicationError(
                f"状态读取失败: PID=0x{pid:02X}, payload_length={len(payload)}"
            )
        return payload

    def _master_read_status(self, pid: int) -> List[int]:
        read_buffer = (c_ubyte * self._protocol.frame_size)()
        ret = _call_native(
            "LIN_EX_MasterRead",
            LIN_EX_MasterRead,
            self._handle,
            self.config.lin_index,
            pid,
            read_buffer,
        )
        if ret <= 0:
            raise LinCommunicationError(
                f"状态读取失败: LIN_EX_MasterRead PID=0x{pid:02X}, code={ret}"
            )
        return [read_buffer[idx] & 0xFF for idx in range(min(ret, self._protocol.frame_size))]

    def _read_status_payload(
        self,
        pid: int,
        echo_payload: List[int] | None,
        max_attempts: int = 3,
    ) -> List[int]:
        last_payload: List[int] = []
        for _ in range(max_attempts):
            payload = self._master_read_status(pid)
            if len(payload) == self._protocol.frame_size and (
                echo_payload is None or not self._is_echo_payload(payload, echo_payload)
            ):
                return payload
            last_payload = payload
            time.sleep(0.01)

        raise LinCommunicationError(
            f"状态读取失败: PID=0x{pid:02X} 收到命令回显, last_payload={last_payload}"
        )

    def _is_echo_payload(self, payload: List[int], command_payload: List[int]) -> bool:
        if len(payload) != self._protocol.frame_size:
            return False
        return list(payload[: self._protocol.frame_size]) == list(command_payload[: self._protocol.frame_size])


def _call_native(operation: str, func: Callable[..., Any], *args) -> Any:
    with _NATIVE_DRIVER_LOCK:
        try:
            return func(*args)
        except LinServiceError:
            raise
        except OSError as exc:
            raise NativeDriverError(_format_native_error(operation, exc)) from exc
        except Exception as exc:
            raise NativeDriverError(_format_native_error(operation, exc)) from exc


def _safe_close_device(handle) -> None:
    try:
        _call_native("USB_CloseDevice", USB_CloseDevice, handle)
    except NativeDriverError:
        pass


def _format_native_error(operation: str, exc: BaseException) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    if "access violation" in detail.lower():
        return (
            f"{operation} 调用 USB2XXX 驱动时发生访问冲突: {detail}. "
            "请检查驱动版本、设备连接状态以及当前 LIN Index 是否与硬件通道匹配。"
        )
    return f"{operation} 调用 USB2XXX 驱动失败: {detail}"
