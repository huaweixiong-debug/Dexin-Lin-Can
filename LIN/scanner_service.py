"""TCP scanner manager adapted from the legacy LGV2 project."""

from __future__ import annotations

import queue
import socket
import threading
import time
from typing import Callable, Dict

from logger import logger


class Scanner:
    def __init__(self, scanner_ip: str, port: int = 8888, timeout: float = 5.0, mode: str = "client"):
        if ":" in scanner_ip:
            self.scanner_ip, port_text = scanner_ip.split(":", 1)
            try:
                self.port = int(port_text)
            except ValueError:
                self.port = port
        else:
            self.scanner_ip = scanner_ip
            self.port = port
        self.timeout = timeout
        self.mode = mode
        self.sock: socket.socket | None = None
        self.client_sock: socket.socket | None = None
        self.connected = False
        self.lock = threading.Lock()
        self.scan_queue: queue.Queue[str] = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.running = False
        self.callback: Callable[[str], None] | None = None
        self.scan_result = ""

    def connect(self) -> bool:
        with self.lock:
            if self.connected:
                return True
            try:
                if self.mode == "client":
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(self.timeout)
                    self.sock.connect((self.scanner_ip, self.port))
                else:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(self.timeout)
                    self.sock.bind(("0.0.0.0", self.port))
                    self.sock.listen(1)
                    self.client_sock, _ = self.sock.accept()
                self.connected = True
                self._connect_fail_logged = False
                logger.info("Scanner connected: %s:%s", self.scanner_ip, self.port)
                return True
            except Exception as exc:
                if not getattr(self, '_connect_fail_logged', False):
                    logger.error("Scanner connect failed %s:%s - %s", self.scanner_ip, self.port, exc)
                    self._connect_fail_logged = True
                self.connected = False
                return False

    def disconnect(self) -> None:
        with self.lock:
            self.connected = False
            for sock in (self.client_sock, self.sock):
                if sock is None:
                    continue
                try:
                    sock.close()
                except OSError:
                    pass
            self.client_sock = None
            self.sock = None

    def start_auto_scan(self, callback: Callable[[str], None] | None = None) -> None:
        self.callback = callback
        self.running = True
        if self.scan_thread and self.scan_thread.is_alive():
            return
        self.scan_thread = threading.Thread(target=self._auto_scan_loop, daemon=True)
        self.scan_thread.start()

    def stop_auto_scan(self) -> None:
        self.running = False
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=2)
        self.disconnect()

    def _auto_scan_loop(self) -> None:
        while self.running:
            try:
                if not self.connected and not self.connect():
                    time.sleep(1)
                    continue

                current_sock = self.client_sock or self.sock
                if current_sock is None:
                    time.sleep(0.5)
                    continue

                current_sock.setblocking(True)
                current_sock.settimeout(1.0)
                data = b""
                start_time = time.time()
                while time.time() - start_time < 1.0:
                    try:
                        chunk = current_sock.recv(1024)
                    except socket.timeout:
                        break
                    if not chunk:
                        self.connected = False
                        break
                    data += chunk
                    if b"\n" in data or b"\r" in data or len(data) > 10:
                        break

                result = self._decode_scan_data(data)
                if result:
                    self.scan_result = result
                    self.scan_queue.put(result)
                    logger.info("Scanner %s received: %s", self.scanner_ip, result)
                    if self.callback:
                        self.callback(result)
            except Exception as exc:
                if not getattr(self, '_scan_loop_error_logged', False):
                    logger.error("Auto scan loop failed for %s: %s", self.scanner_ip, exc)
                    self._scan_loop_error_logged = True
                self.connected = False
                time.sleep(3)

    def _decode_scan_data(self, data: bytes) -> str:
        if not data:
            return ""
        for encoding in ("utf-8", "gbk", "ascii"):
            try:
                result = data.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
            if result:
                return result
        return str(data).strip()

    def get_scan_result(self, timeout: float = 0.1) -> str:
        try:
            return self.scan_queue.get(timeout=timeout)
        except queue.Empty:
            return ""


class ScannerManager:
    def __init__(self) -> None:
        self.scanners: Dict[int, Scanner] = {}
        self.lock = threading.Lock()

    def add_scanner(self, station_idx: int, scanner_ip: str, port: int = 8888, mode: str = "client") -> None:
        with self.lock:
            if station_idx in self.scanners:
                self.scanners[station_idx].disconnect()
            self.scanners[station_idx] = Scanner(scanner_ip, port=port, mode=mode)
            logger.info("Scanner registered for station %s: %s", station_idx, scanner_ip)

    def get_scanner(self, station_idx: int) -> Scanner | None:
        with self.lock:
            return self.scanners.get(station_idx)

    def start_auto_scan_all(self, callback: Callable[[int, str], None] | None = None) -> None:
        with self.lock:
            for station_idx, scanner in self.scanners.items():
                scanner.start_auto_scan(
                    (lambda idx: (lambda result: callback(idx, result) if callback else None))(station_idx)
                )

    def stop_auto_scan_all(self) -> None:
        with self.lock:
            for scanner in self.scanners.values():
                scanner.stop_auto_scan()

    def get_scan_result(self, station_idx: int, timeout: float = 0.1) -> str:
        scanner = self.get_scanner(station_idx)
        if not scanner:
            return ""
        return scanner.get_scan_result(timeout)

    def disconnect_all(self) -> None:
        with self.lock:
            for scanner in self.scanners.values():
                scanner.disconnect()

