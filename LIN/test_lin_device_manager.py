import threading
import time
import unittest
from unittest.mock import patch

from lin_device_manager import LinDeviceManager
from lin_service import LinServiceError


class LinDeviceManagerSchedulingTests(unittest.TestCase):
    def test_exchange_status_allows_parallel_requests_across_devices(self):
        manager = LinDeviceManager()
        active_calls = 0
        max_concurrency = 0
        results = []
        lock = threading.Lock()
        services = {}

        class FakeService:
            def __init__(self, label: str):
                self.label = label
                self.service_lock = threading.Lock()

            def exchange_status(self, power_ratio: int, settle_delay: float):
                nonlocal active_calls, max_concurrency
                with self.service_lock:
                    with lock:
                        active_calls += 1
                        max_concurrency = max(max_concurrency, active_calls)
                    time.sleep(0.02)
                    with lock:
                        active_calls -= 1
                return {"label": self.label, "power_ratio": power_ratio, "settle_delay": settle_delay}

        for index in range(10):
            services[(f"SN{index}", index)] = FakeService(f"station-{index}")

        def _fake_ensure(sn: str, lin_index: int, baud_rate: int, product_code: str = "A045"):
            return services[(sn, lin_index)]

        manager.ensure_channel_initialized = _fake_ensure  # type: ignore[method-assign]

        threads = []

        def _worker(index: int) -> None:
            result = manager.exchange_status(f"SN{index}", index, 19200, 75, 0.08)
            with lock:
                results.append(result["label"])

        for index in range(10):
            thread = threading.Thread(target=_worker, args=(index,), daemon=True)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=2.0)

        self.assertGreaterEqual(max_concurrency, 2)
        self.assertEqual(len(results), 10)
        self.assertEqual(sorted(results), [f"station-{index}" for index in range(10)])

    def test_product_change_rebuilds_channel_service(self):
        manager = LinDeviceManager()
        manager.get_or_open_device = lambda _sn: 1  # type: ignore[method-assign]

        class FakeService:
            def __init__(self, config, **_kwargs):
                self.config = config
                self.is_ready = False

            def initialize(self):
                self.is_ready = True

            def close(self):
                self.is_ready = False

        with patch("lin_device_manager.LinService", FakeService):
            a045_service = manager.ensure_channel_initialized("SN_A", 0, 19200, "A045")
            a050_service = manager.ensure_channel_initialized("SN_A", 0, 19200, "A050")

        self.assertIsNot(a045_service, a050_service)
        self.assertEqual(a050_service.config.product_code, "A050")
        self.assertEqual(manager.channel_state[("SN_A", 0)]["product_code"], "A050")

    def test_get_or_open_device_refuses_rescan_after_channels_initialized(self):
        manager = LinDeviceManager()
        manager.device_catalog = {
            "SN_A": {
                "opened": True,
                "handle": 1,
                "serial": "SN_A",
                "description": "existing",
                "last_seen": time.time(),
            }
        }
        manager.channel_state = {
            ("SN_A", 0): {
                "initialized": True,
                "baud_rate": 19200,
                "service": object(),
                "last_error": "",
            }
        }

        scan_called = False

        def _unexpected_scan(sn: str):
            nonlocal scan_called
            scan_called = True
            raise AssertionError("runtime rescan should not be attempted")

        manager._scan_and_open_target_locked = _unexpected_scan  # type: ignore[method-assign]

        with self.assertRaisesRegex(LinServiceError, "禁止在运行中重新扫描 USB 设备"):
            manager.get_or_open_device("SN_B")

        self.assertFalse(scan_called)


if __name__ == "__main__":
    unittest.main()
