"""Probe how an A063 part interprets the 0x07 power command.

Sends several 0x07 encodings in turn to one station, each for a fixed time,
and records both zone powers, bus current and faults from 0x08 / 0x0A. The bus
current shows how many heater zones are really working (each zone at 100 %
is about 1500 W, i.e. ~3.4 A at 440 V), independent of how POWER_1/2 are encoded.

Usage (from the LIN directory on the test PC, close settings_ui.py first):
    python probe_a063_lin.py --station 1
    python probe_a063_lin.py --sn 30415455003330355300035A --index 0 --seconds 8
    python probe_a063_lin.py --list-devices

All output is also written to logs/probe_a063_<time>.txt.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Sequence

from a063_protocol import (
    AUX_STATUS_PID,
    COMMAND_PID,
    FRAME_SIZE,
    STATUS_PID,
    ZONE_RATED_POWER_W,
    combine_status,
    format_payload_hex,
    parse_aux_status_payload,
    parse_status_payload,
)
from config_store import CONFIG_FILE, ConfigError, load_config

NOMINAL_BUS_VOLTAGE_V = 440
OFF_PAYLOAD = [0x00] * FRAME_SIZE


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    build: Callable[[int], List[int]]
    zones_expected: int


def _frame(*head: int) -> List[int]:
    return list(head) + [0x00] * (FRAME_SIZE - len(head))


VARIANTS: List[Variant] = [
    Variant("spec_le16", "需求表格式（当前程序）：PowerSet1=byte1-2，PowerSet2=byte3-4，低字节在前",
            lambda p: _frame(0x01, p, 0x00, p, 0x00), 2),
    Variant("left_only", "需求表格式，只开主驾（左）区", lambda p: _frame(0x01, p, 0x00, 0x00, 0x00), 1),
    Variant("right_only", "需求表格式，只开副驾（右）区", lambda p: _frame(0x01, 0x00, 0x00, p, 0x00), 1),
    Variant("u8_adjacent", "8 位功率：PowerSet1=byte1，PowerSet2=byte2", lambda p: _frame(0x01, p, p), 2),
    Variant("be16", "16 位高字节在前：PowerSet1=byte1-2，PowerSet2=byte3-4", lambda p: _frame(0x01, 0x00, p, 0x00, p), 2),
]


@dataclass
class Sample:
    current_a: int
    bus_voltage_v: int
    power_1_le: int
    power_2_le: int
    power_1_be: int
    power_2_be: int
    fault_names: List[str]


@dataclass
class PhaseResult:
    variant: Variant
    samples: List[Sample] = field(default_factory=list)
    errors: int = 0

    def steady(self) -> List[Sample]:
        # Ignore the ramp-up: use the second half of the phase.
        return self.samples[len(self.samples) // 2:]


class Tee:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")
        self.path = path

    def __call__(self, message: str = "") -> None:
        print(message, flush=True)
        self._file.write(message + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def exchange_raw(service, command_payload: Sequence[int], settle_delay_sec: float) -> tuple[List[int], List[int]]:
    """Write one raw 0x07 frame, then read 0x08 and 0x0A.

    Uses the LinService frame helpers directly so arbitrary 0x07 payloads can be
    sent; the production path only builds the requirement-table encoding.
    """
    from usb2lin_ex import LIN_EX_MSG_TYPE_MW

    payload = [int(value) & 0xFF for value in command_payload]
    with service._lock:
        service._ensure_ready()
        service.send_break()
        ret, _ = service._master_sync(COMMAND_PID, payload, LIN_EX_MSG_TYPE_MW)
        if ret <= 0:
            raise RuntimeError(f"0x07 写入失败 code={ret}")
        if settle_delay_sec > 0:
            time.sleep(settle_delay_sec)
        service.send_break()
        status_payload = service._read_frame_payload(STATUS_PID, payload)
        service.send_break()
        aux_payload = service._read_frame_payload(AUX_STATUS_PID, None)
    return status_payload, aux_payload


def decode_sample(status_payload: List[int], aux_payload: List[int]) -> tuple[Sample, str]:
    status = combine_status(parse_status_payload(status_payload), parse_aux_status_payload(aux_payload))
    main, aux = status.main, status.aux
    sample = Sample(
        current_a=main.bus_current_a,
        bus_voltage_v=main.bus_voltage_v,
        power_1_le=status_payload[5] | (status_payload[6] << 8),
        power_2_le=aux_payload[1] | (aux_payload[2] << 8),
        power_1_be=(status_payload[5] << 8) | status_payload[6],
        power_2_be=(aux_payload[1] << 8) | aux_payload[2],
        fault_names=status.fault_names,
    )
    detail = (
        f"I={sample.current_a}A U={sample.bus_voltage_v}V "
        f"P1={sample.power_1_le}W(BE {sample.power_1_be}) P2={sample.power_2_le}W(BE {sample.power_2_be}) "
        f"T1={main.temperature_1_c}C T2={aux.temperature_2_c}C IGBT={aux.igbt_temperature_c}C "
        f"state={main.state} limited={int(main.power_limited)} "
        f"fault={'+'.join(sample.fault_names) or 'none'} "
        f"rx08={format_payload_hex(status_payload)} rx0A={format_payload_hex(aux_payload)}"
    )
    return sample, detail


OFF_VARIANT = Variant("off", "关闭（Request=0）", lambda _p: list(OFF_PAYLOAD), 0)


def run_phase(service, variant: Variant, percent: int, seconds: float, log: Tee) -> PhaseResult:
    """Repeat the variant's 0x07 frame for *seconds* at the 100 ms bus period."""
    payload = variant.build(percent)
    label = variant.name
    period_sec = 0.1
    samples: List[Sample] = []
    errors = 0
    start = time.time()
    last_print = 0.0
    while time.time() - start < seconds:
        cycle_start = time.time()
        try:
            status_payload, aux_payload = exchange_raw(service, payload, 0.03)
            sample, detail = decode_sample(status_payload, aux_payload)
            samples.append(sample)
            if cycle_start - last_print >= 1.0:
                log(f"  [{label} {cycle_start - start:5.1f}s] tx07={format_payload_hex(payload)} {detail}")
                last_print = cycle_start
        except Exception as exc:  # keep probing; report communication problems
            errors += 1
            if cycle_start - last_print >= 1.0:
                log(f"  [{label} {cycle_start - start:5.1f}s] 通讯失败: {exc}")
                last_print = cycle_start
        time.sleep(max(period_sec - (time.time() - cycle_start), 0.0))
    return PhaseResult(variant, samples, errors)


def summarize(results: List[PhaseResult], percent: int, log: Tee) -> None:
    log("")
    log("=" * 100)
    log(f"汇总（功率 {percent}%，取每段后一半的平均值；单区 {percent}% ≈ {ZONE_RATED_POWER_W * percent // 100} W）")
    log("=" * 100)
    log(f"{'编码':<12} {'电流A':>6} {'电压V':>6} {'估算加热区数':>12} {'P1(低在前)':>10} {'P2(低在前)':>10} {'P1(高在前)':>10} {'P2(高在前)':>10}  故障")
    for result in results:
        steady = result.steady()
        if not steady:
            log(f"{result.variant.name:<12} 无有效数据（通讯失败 {result.errors} 次）")
            continue
        avg = lambda values: sum(values) / len(values)
        current = avg([s.current_a for s in steady])
        voltage = avg([s.bus_voltage_v for s in steady]) or NOMINAL_BUS_VOLTAGE_V
        single_zone_a = ZONE_RATED_POWER_W * percent / 100 / voltage
        zones = current / single_zone_a if single_zone_a else 0
        faults = sorted({name for s in steady for name in s.fault_names})
        log(
            f"{result.variant.name:<12} {current:6.1f} {voltage:6.0f} {zones:12.1f} "
            f"{avg([s.power_1_le for s in steady]):10.0f} {avg([s.power_2_le for s in steady]):10.0f} "
            f"{avg([s.power_1_be for s in steady]):10.0f} {avg([s.power_2_be for s in steady]):10.0f}  "
            f"{'+'.join(faults) or '无'}"
        )
    log("")
    log("怎么看：")
    log("  - “估算加热区数”由母线电流算出，最可信。spec_le16 约为 2 说明需求表格式正确，两区都在加热。")
    log("  - spec_le16 约为 1：看 left_only / right_only 哪个能单独加热；再看 u8_adjacent / be16 哪个约为 2，")
    log("    那就是产品实际使用的 0x07 格式。")
    log("  - P1/P2 两列对比“低在前 / 高在前”，哪一种和电流对得上，产品上报 POWER_1/2 就用哪种字节序。")
    log("  - 电压为 0 或有 hv_undervoltage 故障：高压没上，所有编码都不会加热，请先确认高压电源。")
    log("把整个日志文件发回即可。")


def resolve_target(args: argparse.Namespace) -> tuple[str, int, int]:
    if args.sn:
        return args.sn.strip().upper(), args.index, args.baud
    config_path = Path(args.config) if args.config else Path(__file__).resolve().parent / CONFIG_FILE
    config = load_config(config_path)
    baud = int(config.get("device", {}).get("baud_rate", args.baud))
    for station in config.get("stations", []):
        if int(station.get("slot", 0)) == args.station:
            serial = str(station.get("lin_sn", "")).strip().upper()
            if not serial:
                raise ConfigError(f"工位 {args.station} 没有配置 LIN SN")
            return serial, int(station.get("lin_index", 0)), baud
    raise ConfigError(f"config.json 中没有工位 {args.station}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A063 0x07 编码探测")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--station", type=int, help="按 config.json 中的工位号选择 SN / Index")
    target.add_argument("--sn", help="USB2XXX 序列号")
    target.add_argument("--list-devices", action="store_true", help="只列出扫描到的 USB2XXX 设备")
    parser.add_argument("--index", type=int, default=0, help="LIN Index（配合 --sn）")
    parser.add_argument("--baud", type=int, default=19200)
    parser.add_argument("--config", help="config.json 路径，默认与本脚本同目录")
    parser.add_argument("--percent", type=int, default=100, help="每种编码下发的功率百分比，默认 100（电流只有 1 A 分辨率，低功率不易区分一区和两区）")
    parser.add_argument("--seconds", type=float, default=12.0, help="每种编码持续时间，默认 12 s")
    parser.add_argument("--off-seconds", type=float, default=6.0, help="每种编码之间关闭的时间，默认 6 s")
    parser.add_argument("--variants", default=",".join(v.name for v in VARIANTS),
                        help="要测试的编码，逗号分隔，默认全部")
    parser.add_argument("--yes", action="store_true", help="不询问，直接开始加热")
    args = parser.parse_args(argv[1:])
    if not 1 <= args.percent <= 100:
        parser.error("--percent 必须在 1-100 之间")
    return args


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    from lin_device_manager import lin_device_manager

    if args.list_devices:
        for device in lin_device_manager.scan_devices_once(force=True):
            print(f"scan_index={device['scan_index']} serial={device['serial']}")
        lin_device_manager.close_all()
        return 0

    variants_by_name: Dict[str, Variant] = {v.name: v for v in VARIANTS}
    selected = [name.strip() for name in args.variants.split(",") if name.strip()]
    unknown = [name for name in selected if name not in variants_by_name]
    if unknown:
        print(f"未知编码: {unknown}，可选: {list(variants_by_name)}")
        return 1

    try:
        serial, lin_index, baud = resolve_target(args)
    except (ConfigError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    log = Tee(Path(__file__).resolve().parent / "logs" / f"probe_a063_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    log(f"A063 0x07 编码探测  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"目标: SN={serial} LIN Index={lin_index} Baud={baud}  功率={args.percent}%  "
        f"每段 {args.seconds:.0f}s，间隔关闭 {args.off_seconds:.0f}s")
    for name in selected:
        variant = variants_by_name[name]
        log(f"  {name:<12} tx07={format_payload_hex(variant.build(args.percent))}  {variant.description}")
    log("请确认：老化高压电源已上电，产品已装好，测试期间会实际加热。")
    if not args.yes:
        try:
            input("按回车开始，Ctrl+C 取消 > ")
        except (KeyboardInterrupt, EOFError):
            log("已取消。")
            log.close()
            return 1

    results: List[PhaseResult] = []
    service = None
    try:
        service = lin_device_manager.ensure_channel_initialized(serial, lin_index, baud, "A063")
        log("")
        log("== 初始状态（关闭）")
        run_phase(service, OFF_VARIANT, args.percent, 2.0, log)
        for name in selected:
            variant = variants_by_name[name]
            log("")
            log(f"== {variant.name}: {variant.description}")
            results.append(run_phase(service, variant, args.percent, args.seconds, log))
            log(f"== 关闭 {args.off_seconds:.0f}s")
            run_phase(service, OFF_VARIANT, args.percent, args.off_seconds, log)
    except KeyboardInterrupt:
        log("用户中断，正在关闭输出...")
    except Exception as exc:
        log(f"[ERROR] {exc}")
    finally:
        if service is not None:
            for _ in range(5):
                try:
                    exchange_raw(service, OFF_PAYLOAD, 0.02)
                except Exception:
                    pass
                time.sleep(0.1)
            log("已发送关闭命令（Request=0）。")
        lin_device_manager.close_all()

    if results:
        summarize(results, args.percent, log)
    log(f"日志文件: {log.path}")
    log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
