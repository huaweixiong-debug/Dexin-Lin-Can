# 老化 LIN 通讯交接记录

最后更新：2026-06-13 09:20

> 持续更新约定：后续每完成一轮重要修改，都同步更新本文件，至少补充“最近完成的改动”“验证结果”“下一步建议”三块。

## 当前目标

本项目是 `A045` 的 Python/Tkinter 多工位 LIN 老化测试程序，当前目标是：

- 10 个工位独立配置 `LIN SN / LIN Index / 扫码枪 IP`
- 测试看板实时显示每个工位的当前状态
- 测试完成后自动记录结果并支持历史查询、CSV 导出
- 复用 `R:\老化CAN通讯\LGV2` 的 PLC / 扫码联动逻辑
- LIN 通信层采用参考 CAN 的稳定模型：按设备集中管理、一次建链、统一调度，避免运行中反复扫描 USB2XXX 设备

## 当前目录

- 工作目录：`R:\老化LIN通讯`
- 参考 CAN 项目：`R:\老化CAN通讯\LGV2`
- 远程运行目录：`D:\老化LIN通讯`

## 关键文件

### LIN 协议与通信

- `R:\老化LIN通讯\a045_protocol.py`
  - A045 LIN 命令帧和状态帧协议
  - `0x26` 命令构造
  - `0x27` 状态解析
- `R:\老化LIN通讯\lin_device_manager.py`
  - 新增中心设备管理层
  - 负责 USB2XXX 扫描、打开、句柄缓存、LIN 通道初始化、读写调度、关闭
  - 当前所有 UI / 查询 / 运行入口都应通过它访问 LIN 驱动
- `R:\老化LIN通讯\lin_service.py`
  - LIN 通道执行器
  - 只负责 `BREAK / MasterSync / MasterRead / send_command / read_status / exchange_status`
  - 不再自行扫描设备或按 SN 查找设备
- `R:\老化LIN通讯\main.py`
  - A045 测试流程运行器
  - `SequenceRunner` 通过中心管理器准备好的通道执行测试
- `R:\老化LIN通讯\probe_a045_lin.py`
  - USB2XXX / LIN Index 探测脚本
  - 已切到 `lin_device_manager` 路径

### 配置、界面、记录

- `R:\老化LIN通讯\settings_ui.py`
  - Tkinter 主界面
  - 包含 `测试看板 / 设置页面 / A045 LIN 运行日志 / 全量查询`
  - 设置页中文乱码已修复
  - 启动、查询、手动扫描已接入中心 LIN 管理器
- `R:\老化LIN通讯\config_store.py`
  - `config.json` 加载、保存、校验、模板管理
  - 10 工位配置归一化
- `R:\老化LIN通讯\config.json`
  - 当前现场配置
- `R:\老化LIN通讯\test_records.json`
  - 测试完成历史记录

### PLC / 扫码

- `R:\老化LIN通讯\plc_service.py`
  - 复用 LGV2 PLC 读写逻辑
- `R:\老化LIN通讯\scanner_service.py`
  - 复用 LGV2 扫码 TCP 接收逻辑
- `R:\老化LIN通讯\logger.py`
  - 公共日志

## 当前能力

### 1. LIN 通信

已实现：

- `0x26` 写命令、`0x27` 读状态
- 可解析左右功率、左右温度、PCB 温度、高压、运行状态、故障状态
- 支持 watchdog 超时保护
- 停止时发送 0% 输出
- 原生 USB2XXX / LIN_EX 调用统一包装为可读错误

本轮重点重构：

- 新增 `lin_device_manager.py`
- 采用稳定优先模型：
  - 手动扫描才调用 `scan_devices_once(force=True)`
  - 启动和查询不再隐式反复 `USB_ScanDevice`
  - 同一 SN 下不同 LIN Index 共用中心管理器
  - 同一 SN 的驱动调用由设备锁串行化
- `LinService` 从“设备发现 + 通道执行”收缩为“纯通道执行”
- `main.py` 多工位运行不再自行共享 `_handle`
- `settings_ui.py` 不再保存大量 `LinService` 实例，只保存轻量工位绑定

### 2. 10 工位设置与看板

界面包含 4 个页签：

1. `测试看板`
2. `设置页面`
3. `A045 LIN 运行日志`
4. `全量查询`

已实现：

- 10 工位独立配置 `LIN SN / LIN Index / 扫码枪 IP`
- PLC 参数配置：`PLC1 IP / PLC2 IP`
- USB2XXX 扫描后可回填当前工位
- 每个工位独立 `启动 / 停止`
- 看板实时显示：
  - 当前步骤
  - 当前命令
  - 运行状态
  - 故障状态
  - 左功率
  - 右功率
  - 高压
  - 左温度
  - 右温度
  - PCB 温度
  - 最新汇总
  - 测试结果

### 3. 运行日志页

`A045 LIN 运行日志` 为内嵌页签，包含：

- 当前运行状态卡片
- 步骤汇总表
- 原始日志文本

### 4. 全量查询页

已实现：

- `查询全部工位`
- `查询当前工位`
- `清空查询结果`
- 当前状态表
- 测试完成记录表
- `导出测试记录` 为 CSV

当前状态表字段：

- 工位
- 名称
- SN
- Index
- 运行状态
- 故障状态
- 左功率
- 右功率
- 高压
- 左温度
- 右温度
- PCB 温度
- 查询时间

完成记录表字段：

- 工位
- 名称
- 结果
- 开始时间
- 结束时间
- SN
- Index
- 运行状态
- 故障状态
- 左功率
- 右功率
- 高压

### 5. 历史记录持久化

已实现：

- 测试完成记录自动写入 `R:\老化LIN通讯\test_records.json`
- 程序下次打开时自动加载历史记录
- 全量查询页可查看历史记录
- 测试记录可导出 CSV

### 6. PLC / 扫码联动

已接入：

- 扫码枪 TCP 接收
- PLC 读写
- 设置页可启停 `PLC/扫码`
- PLC 启动信号可触发对应工位测试
- 扫码结果可回写 `SCAN_OK`
- 测试完成后可回写 `PASS/FAIL`

## 2026-06-09 18:55 硬件联机验证 + USB_OpenDevice 彻底修复

### 根因分析

`lin_device_manager._scan_and_open_target_locked()` 在重新扫描时对**所有** `USB_ScanDevice` 返回的 handle（包括已打开设备的 handle）都调用了 `USB_OpenDevice`。对已打开的 handle 再次调用 `USB_OpenDevice` 会把 USB2XXX 驱动搞乱，导致后续所有设备的打开都失败。

对比参考 CAN 项目 `R:\老化CAN通讯\LGV2\can_manager.py::get_device_handle()`，它在扫描时会先检查 `self.handles` 中是否已有匹配的 handle，对已打开的 handle 跳过 `USB_OpenDevice`，只读取设备信息。

### 本轮修改

`lin_device_manager.py` 两处改动：

1. **`get_or_open_device()`** 简化：
   - 已打开设备直接返回 handle，不再做冗余检查
   - 未打开设备不再尝试用缓存 handle 调 `USB_OpenDevice`（USB2XXX SDK 不支持跨扫描重用 handle），直接走 `_scan_and_open_target_locked()`
   - 两次扫描重试

2. **`_scan_and_open_target_locked()`** 对齐 CAN 模型：
   - 扫描前先记录已打开 handle 集合 `open_handles`
   - 对已打开的 handle 只调用 `DEV_GetDeviceInfo` 读取身份，不调用 `USB_OpenDevice`
   - 对未打开 handle 才执行 `USB_OpenDevice` → 读身份
   - 已打开设备保持 `opened=True`，不被 `finally` 块误关

### 验证结果

在工控机 (100.123.122.100, dell / 0000) 上执行：

```
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py  → PASS
python -m unittest test_a045_protocol.py test_main_config.py  → 11/11 OK
python probe_a045_lin.py  → 6/6 SN 全部打开，10/10 配置工位通道 OK
```

快速功能测试 `_quick_test.py`：
- **单工位启动 (10 工位)**：10/10 OK，全部 exchange_status 成功
- **同 SN 双工位** (工位1+2，共享 SN 30415455003330355300035A)：5 轮循环无冲突，无 `USB_ScanDevice access violation`
- **查询全部工位**：正常工作（idle 通道返回 fault/无响应属于预期行为——LIN 总线上无从设备主动发送时 MasterRead 会超时）

### SSH 问题备注

工控机 SSH 已在 2026-06-09 21:07 修复。根因：`sshd_config` 末尾 `Match User dell` + `ForceCommand wsl` 把所有 dell 用户的命令强制转给不存在的 WSL。修复方法：以管理员身份注释掉该行，重启 sshd。

从本机 SSH 连接方式：
```python
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.123.122.100', username='dell', password='0000', timeout=15)
ssh.exec_command('cd /d D:\\老化LIN通讯 && <command>')
```

## 最近完成的改动 (2026-06-09)

### LIN 架构重构 (15:00-15:15)

- 新增 `lin_device_manager.py` — 中心设备管理层
- `lin_service.py` 收缩为纯 LIN 通道执行器
- `main.py` SequenceRunner 不再持有或直接调用 LinService，一律通过中心管理器读写
- `settings_ui.py` 不再保存 LinService 实例，只保存轻量 station_runtime_bindings
- 10 工位 LIN 配置导入日志 (`[LIN_IMPORT x/10]`)
- 编译 + 11 单测通过

### USB_OpenDevice 根因修复 (18:55) — 本轮核心

**问题**：`_scan_and_open_target_locked()` 对 USB_ScanDevice 返回的所有 handle（包括已打开设备的 handle）都调用 `USB_OpenDevice`，驱动被搞乱，导致 5/6 设备打开失败。

**修复**（对齐 CAN 项目 `can_manager.py` 的做法）：
- `get_or_open_device()`：已打开直接返回，未打开不再用缓存 handle 调 `USB_OpenDevice`（SDK 不支持跨扫描重用 handle），直接重扫
- `_scan_and_open_target_locked()`：扫描前记录已打开 handle 集合，对已打开 handle 只读身份不调 `USB_OpenDevice`

**结果**：6/6 SN 全部可打开（修复前 1/6）。

### 测试看板美化 (22:00)

按 `DASHBOARD_REDESIGN_FOR_CLAUDE.md` 规范完成看板改造：

- 新增 `DASHBOARD_COLORS` 颜色常量（12 种状态色）
- 数据格从 `ttk.Label` 改为 `tk.Label(bg=...)`，支持按单元格动态设置背景色
- 新增 `dashboard_cell_widgets` / `dashboard_header_widgets` 控件引用表
- 新增 `_short_serial()` — SN 过长时只显示后 6 位
- 新增 `_dashboard_color_for_state()` — 根据 state 或 value 自动返回颜色
- `_set_dashboard_cell()` 增加 `state` 参数，同时更新文字和背景色
- `_reset_dashboard_station()` 清空所有格为空白，不再写 "Waiting..."
- `_sync_dashboard_loaded_bindings()` — 按状态传色（已连接=绿色、未连接=灰色、异常=红色…）
- 启动/Error/Exit 路径全部接入颜色状态
- 扫码枪 IP 不再塞入故障状态格
- 系统提示缩短为一行
- 按钮改为原生 `tk.Button`（绿/红色）

验证：`py_compile` 通过 + 11 单测通过 + UI 窗口正常显示。

## 2026-06-12 10:30 远程 10 工位启动失败排查

### 现象

远程工控机 `100.123.122.100`，运行目录 `D:\老化LIN通讯`，启动/诊断时只有 4 个 USB2XXX 设备能正常识别：

- `30415455003330355300035A`
- `30415455003330355300021B`
- `30415455003330355300023E`
- `304154550033303553000239`

配置中的两个设备：

- `30415455003330355300023B`
- `30415455003330355300023C`

对应的 USB handle 可以 `USB_OpenDevice=1`，但 `DEV_GetDeviceInfo=0`，无法读出 USB2XXX SN。

### 原生验证结果

远程原始扫描连续 5 轮结果稳定：

```text
SCAN_COUNT 6
idx=0 handle=1392509500 open=1 info=0 sn=-
idx=1 handle=1392509497 open=1 info=1 sn=0239
idx=2 handle=1392509786 open=1 info=1 sn=035A
idx=3 handle=1392509502 open=1 info=1 sn=023E
idx=4 handle=1392509499 open=1 info=0 sn=-
idx=5 handle=1392509467 open=1 info=1 sn=021B
```

对两个 `DEV_GetDeviceInfo` 失败的 handle 继续做 LIN 能力探测：

- `LIN_EX_CtrlPowerOut` 返回 `-4` 或 `-6`
- `LIN_EX_Init` 返回 `-1` 或卡住

结论：这两个 handle 当前不是可安全使用的 USB2XXX LIN 设备状态。软件不能仅靠代码把它们可靠绑定为 `023B/023C`。

### 本轮代码处理

`lin_device_manager.py`：

- `open_all_devices()` 改为一次扫描中批量打开所有目标 SN，避免按 SN 重复 `USB_ScanDevice`
- 通道初始化失败时只标记当前 `(SN, LIN Index)` 失败，不再关闭整个 SN 设备
- 对 `DEV_GetDeviceInfo` 失败但已打开的未知 handle 增加安全探测：
  - 只有 `LIN_EX_CtrlPowerOut(handle, 1)` 返回成功码 `0` 时，才允许按配置顺序做 fallback 绑定
  - 如果返回 `-4/-6`，立即关闭该 handle，并记录：
    - `Unknown handle ... is not usable as LIN device`
    - 对应配置 SN 保持未打开

`settings_ui.py`：

- 预打开 SN 列表从无序 `set` 改为按工位配置顺序生成，避免 fallback 时顺序随机

### 当前验证

远程执行：

```powershell
cd /d D:\老化LIN通讯
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py
python -m unittest test_a045_protocol.py test_main_config.py
```

## 2026-08-03 PLC tag mapping corrected

The PLC communication definition now follows the OPC Server tag screenshots:

- PLC1: `192.168.10.180`, stations 1-5; PLC2: `192.168.10.181`, stations 6-10.
- Station status bytes are `M0` through `M4` on each PLC.
- `SCAN_OK` is bit 0, `PASS` is bit 1, `FAIL` is bit 2.
- Communication restart request is bit 3; communication restart complete is bit 4.
- Reset is bit 5.
- Start commands are `M20.0` through `M20.4`.
- Heartbeat tags are read from `M17.0` through `M17.4`.

Changed files:

- `plc_service.py`
- `config_store.py`
- `settings_ui.py`
- `test_plc_mapping.py`
- `test_main_config.py`

Validation completed:

```text
python -m py_compile plc_service.py config_store.py settings_ui.py test_plc_mapping.py  PASS
python -m unittest test_plc_mapping.py test_main_config.py -v  12 tests OK
```

The code change corrects the S7 memory addresses and bit definitions. If the remote machine still reports `TCP : Unreachable peer`, that is a network/PLC endpoint issue rather than a tag mapping issue; verify that the remote machine can reach `192.168.10.180` and `192.168.10.181` on S7 port 102 and that the PLC rack/slot is `0/1`.

## Claude Code execution request (next slice)

Please read this file first, then implement exactly the following slice and stop there.

### Slice goal

Create the product runtime presentation adapter layer for `main.py`, while keeping current A045 runtime behavior unchanged.

### Required implementation scope

1. Create `product_presenter.py`
   Responsibilities:
   - provide A045 runtime presentation behavior
   - build command display text used by logs
   - format status snapshot log lines
   - format step summary lines
   - expose a presenter lookup by `product code`

2. Refactor `main.py`
   - remove direct dependency on A045-only formatting helpers where possible
   - route runtime status/log/summary formatting through `product_presenter.py`
   - preserve current A045 log format and operator-visible behavior as much as possible

3. Keep this slice strictly limited
   - do not enable A050 runtime
   - do not change `settings_ui.py` dashboard semantics yet
   - do not change PLC/scanner logic
   - do not redesign records/history schema
   - do not rework `lin_device_manager.py` concurrency again unless a real bug is found

### Acceptance criteria

- A045 still runs exactly as before from the operator perspective
- `main.py` no longer owns A045-specific presentation formatting directly
- the new presenter layer is ready for future A050 presenter implementation

### Required verification

Run at minimum:

```powershell
cd R:\老化LIN通讯
python -m py_compile main.py product_presenter.py lin_service.py lin_device_manager.py runtime_protocols.py product_catalog.py
python -m unittest test_a045_protocol.py test_a050_protocol.py test_main_config.py test_lin_device_manager.py test_product_catalog.py test_runtime_protocols.py -v
```

Add new tests if needed and include them in the command.

### Required return payload to Codex

When done, report back with:

1. files changed
2. concise architecture summary
3. exact test commands run
4. actual test results
5. anything still A045-specific after this slice

### Codex review step

After Claude Code finishes this slice, send the returned summary and changed files back to Codex for review before continuing to the next slice.

## 2026-06-12 11:21 Multi-station scheduling fix

### Findings

- `main.py` multi-station mode was launching one thread per station immediately after each SN group finished initialization.
- Each runner thread called `lin_device_manager.exchange_status(...)` directly in its own loop.
- `lin_device_manager` already had per-SN locks, but `lin_service.py` also serialized native LIN work with a process-wide `_NATIVE_DRIVER_LOCK`.
- Because the full `exchange_status` transaction includes `settle_delay` inside that serialized path, early-start stations could keep reacquiring the single lane and later stations could starve long enough to show `read_success=0`.

### Changes made

- Added a FIFO fair-operation gate in `lin_device_manager.py` for `read_status`, `write_command`, and `exchange_status`.
- Updated `main.py --stations` to initialize all requested stations first, then start all worker threads together through a `threading.Barrier`.
- Added `test_lin_device_manager.py` to cover fair FIFO execution order for the new gate.

### Verification

```powershell
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py test_lin_device_manager.py
python -m unittest test_a045_protocol.py test_main_config.py test_lin_device_manager.py
```

Result:

- `py_compile` PASS
- `unittest` PASS (`12` tests)

### Next recommended on-machine check

- Re-run the 10-station live scenario and compare whether stations 3-10 now start producing status snapshots instead of staying at `read_success=0`.
- If starvation is gone but aggregate throughput is still too low, the next slice should be measuring real per-exchange latency and deciding whether the global native serialization can be narrowed safely.

## 2026-06-12 11:40 Runtime start isolation hardening

### New symptom confirmed

- Stations `1-4` could keep running together.
- Starting any later station such as `5-10` could immediately push already-running stations into `minor_fault/communication_error`.
- This pointed to a start-time side effect, not only to steady-state polling contention.

### Root-cause direction addressed in code

- `lin_device_manager.get_or_open_device()` previously still had a path that could rescan/open a missing USB device while other LIN channels were already active.
- `settings_ui.py` pre-opened all device SNs on first launch, but it did not pre-initialize every station channel, so a later station could still trigger fresh channel initialization during an active run window.

### Changes made

- Replaced the fair ticket gate in `lin_device_manager.py` with a dedicated central worker queue for live LIN `read/write/exchange` operations.
- Added a runtime guard in `get_or_open_device()`:
  if any LIN channel is already initialized, a not-preopened device is now refused instead of being rescanned live.
- Extended `settings_ui.py::_preload_station_bindings()`:
  after bulk `open_all_devices(...)`, it now bulk `ensure_channel_initialized(...)` for every enabled station before the first run starts.

### Self-test executed

```powershell
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py test_lin_device_manager.py
python -m unittest test_a045_protocol.py test_main_config.py test_lin_device_manager.py -v
```

Result:

- `py_compile` PASS
- `unittest` PASS (`13` tests)
- New regression coverage:
  - 10 concurrent `exchange_status` requests are serialized by one central worker
  - runtime rescan is refused once any LIN channel is active

## 2026-06-12 12:05 Scheduling direction corrected: per-device parallel, not global parallel

### Field feedback

- Devices `023E / 0239 / 023B` are confirmed normal.
- Stable pattern on site:
  `035A + 021B + 023C` can run together, but once `023E / 0239 / 023B` join, total active stations rise and communication errors appear.

### Root-cause conclusion

- The previous hotfix over-corrected into **global transaction serialization**:
  every device had to wait behind every other device.
- `lin_service.py::_exchange_once()` also held the global native lock across the full transaction including `settle_delay`.
- That reduced total throughput too far when many USB2XXX devices were active, which matches the现场 pattern better than a bad-device hypothesis.

### Code correction made

- Removed the global live-traffic worker from `lin_device_manager.py`.
- Kept the runtime safety guard:
  if any LIN channel is already initialized, do not rescan/open a new USB device in the middle of a run.
- Removed the outer `_NATIVE_DRIVER_LOCK` wrapper around the entire `exchange_status` transaction in `lin_service.py`.
- Native driver calls are still individually protected by `_call_native(...)`, while station traffic is now effectively:
  - same SN: serialized by `device_lock`
  - different SN: allowed to overlap between native calls

### Validation

```powershell
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py test_lin_device_manager.py
python -m unittest test_a045_protocol.py test_main_config.py test_lin_device_manager.py -v
```

Result:

- `py_compile` PASS
- `unittest` PASS (`13` tests)
- Concurrency regression updated:
  different devices are now allowed to run in parallel instead of being forced through one global queue

## 2026-06-12 Current LIN runtime model (important handoff summary)

This section describes the **current effective communication flow** after the latest scheduling fixes. If future work touches LIN concurrency again, use this section as the source of truth.

### 1. Startup / preload flow

- UI entry: `settings_ui.py::_preload_station_bindings()`
- Step 1:
  build lightweight station bindings only: `{lin_sn, lin_index, baud_rate}`
- Step 2:
  call `lin_device_manager.open_all_devices(all_sns)` once to pre-open all configured USB2XXX devices in one batch scan
- Step 3:
  call `lin_device_manager.ensure_channel_initialized(...)` for every enabled station before the first run starts
- Result:
  all configured `(SN, LIN Index)` channels are opened and initialized up front, instead of being lazily discovered in the middle of a run

### 2. Runtime communication flow

- Each station still has its own business thread (`SequenceRunner`)
- The station thread does **not** talk to USB2XXX directly
- The station thread only calls:
  - `lin_device_manager.exchange_status(...)`
  - `lin_device_manager.write_command(...)`
- `lin_device_manager` resolves the already-prepared channel/service and forwards the request to `LinService`
- `LinService` performs the actual LIN transaction:
  - `BREAK`
  - `0x26` command write
  - settle delay
  - `0x27` status read
  - optional retry path if the first read is bad

### 3. Read mode / status acquisition

- Main polling mode is `exchange_status(power_ratio, settle_delay)`
- A single exchange is:
  1. send command payload (`0x26`)
  2. wait `settle_delay`
  3. read status payload (`0x27`)
- `read_status()` and `write_command()` still exist, but the normal running path is `exchange_status()`
- `settle_delay` is now **outside** the coarse global transaction lock, so one device waiting for response does not stall every other device

### 4. Concurrency model: why 10 stations should not interfere

The current rule is:

- same `SN`:
  serialized
- different `SN`:
  parallel

Concretely:

- `lin_device_manager.ensure_channel_initialized()` gives all channels under the same USB2XXX serial number the same `device_lock`
- `LinService` holds that shared `device_lock` for channel init / exchange / read / write on that device
- Therefore:
  - station 1 and 2 (same `35A`) cannot race each other
  - station 7 and 8 (same `23B`) cannot race each other
  - but `35A`, `21B`, `23E`, `239`, `23B`, `23C` can run at the same time as separate device lanes

So the real runtime shape is not "10 fully independent raw threads", and not "1 global queue for all stations". It is:

- business layer:
  10 station threads may run in parallel
- device layer:
  1 lane per USB2XXX serial number
- current site config:
  6 device lanes total

### 5. Native driver locking policy

- `_call_native(...)` in `lin_service.py` still protects each individual USB2XXX SDK call
- The code no longer wraps the **entire** `exchange_status()` transaction in one global lock
- This is intentional:
  the SDK call itself stays protected, but device-local waiting time must not block unrelated devices

### 6. Runtime isolation guarantees

To reduce cross-station impact, the code now relies on these rules:

- no runtime lazy scan for a new device once LIN channels are already active
- no runtime `USB_ScanDevice` as part of the normal station polling loop
- no repeated open/close cycle per station poll
- no direct UI thread access to `USB_* / LIN_EX_*`
- no cross-device global serialization during normal exchange traffic

In practice, this means:

- starting station 5 should reuse its pre-opened / pre-initialized channel
- starting station 5 should not trigger a fresh device scan that disturbs stations 1-4
- one station failing communication should not force other devices to wait behind its full `settle_delay`

### 7. Files responsible for the current behavior

- `settings_ui.py`
  preload bindings, bulk open, bulk channel init before first run
- `main.py`
  station runner threads and business polling loop
- `lin_device_manager.py`
  device catalog, handle reuse, channel lifecycle, same-SN lock sharing
- `lin_service.py`
  actual LIN frame transaction (`BREAK / write / read / retry`)

### 8. Important maintenance rule

If LIN concurrency is changed again in future, do **not** revert to either of these two extremes:

- bad option A:
  every station directly hits native driver calls with no device-level serialization
- bad option B:
  all devices are forced through one global transaction queue

The intended model is:

- same device (`SN`): serialized
- different devices (`SN`): parallel

## 2026-06-12 12:35 Multi-product direction for A045 / A050

### Architecture decision

- Do **not** fork a second project for A050.
- Keep one shared project for:
  - 10-station runtime scheduling
  - PLC / scanner linkage
  - dashboard / query / records
  - LIN device lifecycle and concurrency control
- Separate only the product-specific parts:
  - protocol constants and frame parsing
  - product metadata
  - later: product-specific status-to-dashboard mapping

### Current verified slice

- Added `product_catalog.py`
  - registers `A045` and `A050`
  - marks only `A045` as `runtime_supported=True` for now
- Updated `config_store.py`
  - config validation now depends on the runtime-supported product list instead of a single hardcoded `EXPECTED_PRODUCT`
  - current production behavior is unchanged:
    only `A045` configs can run
- Added `a050_protocol.py`
  - `0x36` command payload helper
  - `0x37` measurement frame parser
  - `0x39` fault/status frame parser
  - derived from `A050.xlsx`

### Why A050 is not enabled in UI/runtime yet

- A050 does not match A045 one-to-one at protocol level
- A050 status is split across at least:
  - `0x37` measurement frame
  - `0x39` fault/status frame
- Current A045 runtime and dashboard assume one A045-shaped status object with fields like:
  - left/right power
  - left/right temperature
  - single `error_code`
- So the safe migration path is:
  1. keep A045 production-safe
  2. land A050 protocol helpers
  3. add a product adapter layer
  4. then expose A050 in UI/runtime

### Verification

```powershell
python -m py_compile a050_protocol.py test_a050_protocol.py product_catalog.py config_store.py
python -m unittest test_a045_protocol.py test_a050_protocol.py test_main_config.py test_lin_device_manager.py test_product_catalog.py -v
```

Result:

- `py_compile` PASS
- `unittest` PASS (`22` tests)

## 2026-06-12 13:00 Runtime protocol adapter slice

### Goal of this slice

- Decouple the live LIN service layer from hardcoded A045 frame constants
- Keep current A045 runtime behavior unchanged
- Prepare the runtime core so A050 can be connected later without cloning the whole project

### Changes made

- Added `runtime_protocols.py`
  - defines the runtime protocol adapter registry
  - current runtime registry contains only `A045`
- Rewrote `lin_service.py`
  - no longer imports A045 constants/functions directly
  - now loads a runtime protocol adapter from `LinDeviceConfig.product_code`
  - current default remains `A045`
- `LinDeviceConfig` now carries `product_code`
  - existing call sites stay compatible because the default is still `A045`

### What is already abstracted now

- command PID
- status PID
- frame size
- command payload builder
- status payload parser

### What is still A045-specific after this slice

- `main.py` status logging and summary formatting
- `settings_ui.py` dashboard field semantics
- A045-specific run/result wording in UI

### Verification

```powershell
python -m py_compile runtime_protocols.py lin_service.py lin_device_manager.py test_runtime_protocols.py
python -m unittest test_a045_protocol.py test_a050_protocol.py test_main_config.py test_lin_device_manager.py test_product_catalog.py test_runtime_protocols.py -v
```

Result:

- `py_compile` PASS
- `unittest` PASS (`24` tests)

## 2026-06-12 14:00 A050 adaptation progress

### Decision

- A050 will **not** become a separate project.
- The chosen direction is one shared project with:
  - shared 10-station runtime / PLC / scanner / dashboard infrastructure
  - product-specific protocol and presentation adapters

### Already completed

- Added `product_catalog.py`
  - registers `A045` and `A050`
  - only `A045` is currently runtime-enabled
- Added `a050_protocol.py`
  - `0x36` command payload helper
  - `0x37` measurement frame parser
  - `0x39` fault/status frame parser
  - derived from `A050.xlsx`
- Added `runtime_protocols.py`
  - runtime protocol adapter registry
  - current runtime registry contains only `A045`
- Reworked `lin_service.py`
  - no longer hardcodes A045 protocol constants directly
  - now resolves runtime protocol behavior through `LinDeviceConfig.product_code`
  - default remains `A045`

### Not completed yet

- `main.py` is still A045-specific in status logging / summary formatting
- `settings_ui.py` is still A045-specific in dashboard field semantics and wording
- `A050` is **not** enabled in runtime or UI yet
- `product_presenter.py` has **not** been created yet; this is the next recommended slice

### Recommended next slice

- create `product_presenter.py`
- move A045-specific status/log formatting out of `main.py`
- let `main.py` depend on a product presenter instead of A045-only formatting
- keep A045 runtime behavior unchanged while preparing the path for A050 runtime enablement

## 2026-06-12 14:00 完成：main.py 产品解耦切片

### 完成内容

1. 新建 `product_presenter.py` — 产品格式化适配层
   - `build_command(power_ratio, product_code)` — 构建命令帧
   - `present_status(status, command_payload, product_code, prefix)` — 格式化状态行
   - `present_summary(step_index, step, status, max_left, max_right, product_code)` — 格式化步骤汇总
   - `status_signature(status, product_code)` — 用于 transition detection

2. 重构 `main.py`
   - 移除 4 个直接 `a045_protocol` 导入
   - 改用 `product_presenter` 的 4 个函数
   - A045 当前行为完全不变

3. A050 仍在 `runtime_protocols.py` 注册但 `runtime_supported=False`
   - A050 协议 helper (`a050_protocol.py`) 已完成
   - A050 产品定义 (`product_catalog.py`) 已完成
   - 未来启用 A050 时只需扩充 `product_presenter.py`，main.py 不改

### 验证

```
python -m py_compile product_presenter.py main.py  → PASS
python -m unittest test_a045_protocol.py test_a050_protocol.py test_main_config.py test_lin_device_manager.py test_product_catalog.py test_runtime_protocols.py -v
→ 24 tests OK
```

### 当前还需解耦的 A045 依赖

- `main.py` 的 `A045Status` 类型注解（通过 `from a045_protocol import A045Status` 保留）
- `settings_ui.py` 看板字段语义（A045 专有）
- A045 专用 run/result 文案

这三个留到后续切片处理。

## 2026-06-12 14:30 完成：彻底移除 main.py 的 A045 字段耦合

### 改动

1. **重构 `product_presenter.py`**
   - 新增 `RuntimeStatus` dataclass — 产品无关的状态包装器（12 字段）
   - 新增 `adapt_status(status_obj, product_code)` — A045Status→RuntimeStatus 转换工厂
   - 所有 presenter 函数（`build_command/present_status/present_summary/status_signature`）改为按产品路由，接受 RuntimeStatus
   - 未知/未启用产品一律 `raise RuntimeProtocolError`，不静默回退

2. **重构 `main.py`**
   - 移除 `from a045_protocol import A045Status`
   - 导入 `RuntimeStatus, adapt_status` from product_presenter
   - `_exchange_and_log_status` 返回 `RuntimeStatus | None`
   - 所有 status 参数类型改为 `RuntimeStatus`
   - 不再直接访问 `status.left_power_w` 等字段 → 通过 RuntimeStatus（字段名不变但类型来自 presenter）

3. **新增 `test_product_presenter.py`** — 11 个测试覆盖：
   - `adapt_status` 正常/未知产品/错误类型
   - `build_command` 正常/未知产品
   - `present_status` 正常/未知产品
   - `present_summary` 有状态/无状态
   - `status_signature` 正常/未知产品

### 验证

```
python -m py_compile product_presenter.py main.py test_product_presenter.py  → PASS
python -m unittest test_a045_protocol.py test_a050_protocol.py test_main_config.py test_lin_device_manager.py test_product_catalog.py test_runtime_protocols.py test_product_presenter.py -v
→ 35 tests OK
```

### main.py 残留 A045 检查

| 行 | 内容 | 是否耦合 |
|----|------|---------|
| 1 | docstring "A045 LIN test sequence" | 文案（无害） |
| 143,176,223 | `self.config.get("product", "A045")` | 配置驱动，读 config.json |
| 239 | `description="A045 LIN test runner"` | CLI 文案（无害） |

**结论：main.py 已完全无 A045 协议层耦合。** `A045Status` 类型和字段只在 `product_presenter.py` 内部使用。

## 2026-06-12 14:50 A050 presenter 层补齐

### 改动

`product_presenter.py` 所有函数新增 A050 路由分支：

| 函数 | A050 行为 |
|------|----------|
| `adapt_status` | `A050MeasurementStatus` → `RuntimeStatus`（单通道功率填入 left/right，core_temp1/2 填入左/右温度） |
| `build_command` | power_ratio % → 线性换算 wattage → `build_a050_command_payload()` |
| `present_status` | 单通道格式：power/temp1/temp2/pcb/hv/tx36/rx37 |
| `present_summary` | max_power/end_power/end_temp1/end_temp2（无左/右区分） |
| `extract_step_power` | 返回 `(power, power)` 同一值 |
| `status_signature` | 与 A045 相同 6 元组结构 |

**字段映射**（A050MeasurementStatus → RuntimeStatus）：

```
power_feedback_w        → left_power_w / right_power_w (同一值)
core_temperature_1_c    → left_temperature_c
core_temperature_2_c    → right_temperature_c
pcb_temperature_c       → pcb_igbt_temperature_c
high_voltage_v          → hv_voltage_v (int)
run/error 字段          → 0/"off"/"normal" (测量帧无故障信息)
```

`test_product_presenter.py`：拆为 A045/A050/Unknown 三个 TestCase，23 个测试。

### 验证

```
python -m py_compile product_presenter.py main.py test_product_presenter.py a050_protocol.py → PASS
python -m unittest ... → 47 tests OK
```

## 2026-06-13 09:20 A045 启动即报 `product_code` 未定义修复

### 现场现象

A045 工位启动后能成功预初始化、也能读到首帧状态，但随即立刻退出：

```text
[Station 1] [TRANSITION] run=off fault=normal/no_fault ...
[Station 1] Shutting down LIN runner, forcing 0% output...
[Station 1] Summary: read_success=1
[Station 1] [ERROR] unexpected failure: name 'product_code' is not defined
```

这不是 LIN 硬件通信失败，而是 `main.py` 运行循环里的 Python 变量作用域错误。

### 根因

在 `main.py::SequenceRunner._run_sequence()` 里，步骤峰值统计已经改成：

```python
left_w, right_w = extract_step_power(status, product_code)
```

但 `product_code` 只在 `_exchange_and_log_status()` / `_record_step_summary()` 内定义，`_run_sequence()` 自己没有定义该变量。
因此只要首帧状态返回成功，代码就会在步骤循环里立刻抛出 `NameError`。

### 修复

- `main.py`
  - 在 `_run_sequence()` 顶部补回：
    - `product_code = self.config.get("product", "A045")`
  - 这样步骤峰值提取和步骤摘要都使用同一个已解析产品码

- `test_main_runner.py`（新增）
  - 新增最小回归测试 `test_run_sequence_uses_configured_product_code_for_step_power_extraction`
  - 通过 mock 单帧成功状态，覆盖“首帧返回后执行 `extract_step_power(...)` 不会因局部变量未定义而崩溃”

### 验证

执行：

```powershell
python -m py_compile main.py test_main_runner.py
python -m unittest test_a045_protocol.py test_a050_protocol.py test_lin_device_manager.py test_product_catalog.py test_runtime_protocols.py test_product_presenter.py test_main_config.py test_main_runner.py -v
```

结果：

```text
py_compile OK
48 tests OK
```

### 结论

- 本次 A045 “启动就 FAIL” 的直接原因已经确认是软件回归，不是现场设备异常
- 修复后，`name 'product_code' is not defined` 这条启动即崩路径已被堵住
- 如果现场重启后仍然 FAIL，应继续看真实 LIN 状态/故障码，而不是再沿着这条 Python 异常方向排查

### 明确确认

- `runtime_protocols.py` **仍然只开放 A045**，未改变
- `lin_service.py` 未修改
- `settings_ui.py` 未修改
- A050 运行时未启用

## 2026-06-12 14:35 补刀：extract_step_power 收尾

### 改动

- `product_presenter.py` 新增 `extract_step_power(status, product_code)` → `(left_w, right_w)`
- `main.py` 第 122-123 行改为调用 `extract_step_power()`
- `test_product_presenter.py` 新增 2 个测试
- 总测试：37 OK

## Claude Code next slice briefing (历史参考 — 已完成)

Use this exact repository state as the starting point.

### Current state

- A045 production path is still the only runtime-supported product.
- A050 protocol helpers already exist:
  - `a050_protocol.py`
  - `A050.xlsx` has been translated into basic command / measurement / fault parsing helpers
- Product metadata already exists:
  - `product_catalog.py`
- Runtime protocol adapter entry already exists:
  - `runtime_protocols.py`
- `lin_service.py` is already decoupled from hardcoded A045 frame constants and now loads runtime protocol metadata by `product_code`

### Next slice to implement

Implement **only** the runtime/logging product adapter layer in `main.py` and its supporting helper module(s).

Target:

- remove direct `main.py -> a045_protocol.py` dependency
- keep current A045 runtime behavior unchanged
- prepare `main.py` so product-specific status formatting can later support A050

### What this slice should do

1. Introduce a product runtime presentation adapter
   Responsibilities:
   - build the command display text used in logs
   - format status snapshot lines
   - format summary lines
   - expose the status type shape that `main.py` needs for A045

2. Refactor `main.py`
   - stop importing directly from `a045_protocol.py`
   - read product information from the validated config
   - use the product runtime presentation adapter instead of A045-only helpers
   - preserve current A045 log line structure as much as possible

3. Keep the actual business behavior unchanged for A045
   - same polling loop
   - same watchdog logic
   - same shutdown behavior
   - same concurrency model

### What this slice must NOT do

- do not enable A050 in UI/runtime
- do not change `settings_ui.py` dashboard field mapping yet
- do not redesign records/history schema yet
- do not change PLC/scanner logic
- do not rewrite `lin_device_manager.py` concurrency again unless a bug is found

### Verification required

At minimum run:

```powershell
python -m py_compile main.py lin_service.py lin_device_manager.py runtime_protocols.py product_catalog.py
python -m unittest test_a045_protocol.py test_a050_protocol.py test_main_config.py test_lin_device_manager.py test_product_catalog.py test_runtime_protocols.py -v
```

If new tests are added, include them in the command and report actual pass counts.

### Required return format

When this slice is done, return:

1. files changed
2. concise architecture summary
3. exact test commands run
4. real test results
5. explicit note of anything still A045-specific after the slice

结果：

- 编译通过
- `11` 个单元测试通过

远程批量预打开结果：

```text
035A opened=True
021B opened=True
023E opened=True
0239 opened=True
023B opened=None
023C opened=None
```

并明确报错：

```text
DEV_GetDeviceInfo failed while pre-opening handle=1392509500 index=0
DEV_GetDeviceInfo failed while pre-opening handle=1392509499 index=4
[LIN_OPEN_FALLBACK] Unknown handle=... is not usable as LIN device; LIN_EX_CtrlPowerOut returned -4
```

### 现场处置建议

这不是 UI 或配置字段问题，当前优先处理硬件/驱动状态：

1. 关闭主程序、PyCharm、所有诊断脚本，确认无 `python.exe` 占用。
2. 断开并重新插拔对应 `023B / 023C` 两个 USB2XXX 设备。
3. 尽量换 USB 口或换 USB Hub 口，避免两个异常设备继续挂在相同 hub port。
4. 重插后先运行原始扫描，必须看到 6 个设备均 `DEV_GetDeviceInfo=1` 且能读出 SN。
5. 再启动 `settings_ui.py`。

如果重插后仍然 `DEV_GetDeviceInfo=0`：

- 优先怀疑这两个 USB2XXX 设备固件/驱动状态异常
- 可把 `023B/023C` 与其它正常设备互换 USB 口，判断问题跟随设备还是跟随 USB 口/Hub
- 不建议在软件中强行按 scan index 绑定，否则可能把工位 7/8 与 9/10 物理设备映射错

## 2026-06-12 10:55 10 工位连接测试与 BREAK 初始化修复

### 现象

`settings_ui.py` 启动/连接时出现：

```text
通道初始化失败: SN=30415455003330355300035A LIN Index=0:
通道初始化失败: ... BREAK code=0 (retried 3x)
```

### 根因

`lin_service.py::LinService.initialize()` 在 `LIN_EX_Init` 成功后，额外调用了一次 `send_break()` 作为暖机检查。

这会把“通道初始化成功，但当前 LIN 总线没有响应 BREAK / 空闲 / 从设备未应答”的情况误判为“初始化失败”。

参考 CAN 的生命周期模型，连接阶段只应该完成设备打开和通道初始化；业务读写是否有响应，应由运行/查询阶段判断。

### 修改

`lin_service.py`：

- `initialize()` 只保留：
  - `LIN_EX_CtrlPowerOut(handle, 1)`
  - `LIN_EX_Init(handle, lin_index, baud_rate, LIN_EX_MASTER)`
- 删除初始化阶段额外 `send_break()` 暖机检查
- `BREAK / MasterSync / MasterRead` 仍保留在实际 `send_command/read_status/exchange_status` 业务路径中

### 远程验证

远程工控机：

```text
100.123.122.100
D:\老化LIN通讯
```

执行 10 工位纯连接初始化测试：

```text
PREOPEN SN=035A opened=True
PREOPEN SN=021B opened=True
PREOPEN SN=023E opened=True
PREOPEN SN=0239 opened=True
PREOPEN SN=023B opened=True
PREOPEN SN=023C opened=True

INIT station=1 sn=035A index=0  OK ready=True
INIT station=2 sn=035A index=1  OK ready=True
INIT station=3 sn=021B index=0  OK ready=True
INIT station=4 sn=021B index=1  OK ready=True
INIT station=5 sn=023E index=0  OK ready=True
INIT station=6 sn=0239 index=0  OK ready=True
INIT station=7 sn=023B index=0  OK ready=True
INIT station=8 sn=023B index=1  OK ready=True
INIT station=9 sn=023C index=0  OK ready=True
INIT station=10 sn=023C index=1 OK ready=True

SUMMARY INIT_OK [1,2,3,4,5,6,7,8,9,10]
SUMMARY INIT_FAIL []
```

编译与单测：

```powershell
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py
python -m unittest test_a045_protocol.py test_main_config.py
```

结果：

- 编译通过
- `11` 个单元测试通过

### 注意

本轮验证的是“启动连接/通道初始化”。

真实运行或查询时，如果某个工位仍出现：

- `BREAK code=0`
- `BREAK code=-4`
- `LIN_EX_MasterRead failed`

那属于业务通讯阶段的 LIN 总线/从设备响应问题，不应再阻断软件启动。

### SSH 修复 (21:07)

**问题**：`C:\ProgramData\ssh\sshd_config` 末尾 `Match User dell` + `ForceCommand wsl` 把所有 SSH 命令转给不存在的 WSL。

**修复**：注释掉 `ForceCommand wsl`，重启 sshd。从本机 `dell@100.123.122.100:0000` 可正常远程执行命令。

## 参考 CAN 的 10 工位分配方式

CAN 项目不是给 10 个工位分别分配 10 个独立 USB2XXX 设备，而是通过配置表把每个工位路由到：

- 一个 USB2XXX 设备序列号 `SN`
- 一个 CAN 通道 `can_channel=0/1`
- 一个扫码枪地址 `scanner_ip`

参考文件：

- `R:\老化CAN通讯\LGV2\config.json`
  - `hardware_settings["工位1"..."工位10"]`
  - 每个工位配置 `can_sn / can_channel / scanner_ip`
- `R:\老化CAN通讯\LGV2\Main.py`
  - `init_all_can_devices()` 遍历 `hardware_settings`
  - 从 `can_sn` 字符串中解析 `序列号=...`
  - 读取 `can_channel`
  - 调用 `self.can_manager.initialize_can(sn, can_channel)`
- `R:\老化CAN通讯\LGV2\can_manager.py`
  - `handles = {serial_number: handle}`：同一 SN 只打开一次
  - `device_locks = {serial_number: RLock}`：同一设备原生调用串行
  - `can_initialized = {f"{serial_number}_{channel}": state}`：同一设备不同 CAN 通道分别初始化

当前 CAN 配置里的典型映射：

- 工位 1 / 工位 2 共用 SN `30415455003330355300035A`，分别用通道 `0 / 1`
- 工位 3 / 工位 5 共用 SN `30415455003330355300023E`，分别用通道 `1 / 0`
- 工位 6 / 工位 8 共用 SN `304154550033303553000239`，分别用通道 `0 / 1`
- 工位 9 / 工位 10 共用 SN `30415455003330355300023C`，分别用通道 `0 / 1`

迁移到 LIN 时应保持同一思想：

- 工位只是业务编号
- 真实连接键是 `SN + LIN Index`
- 设备生命周期键是 `SN`
- 通道初始化键是 `(SN, lin_index)`
- 同一 SN 下多个 LIN Index 不能让多个线程直接扫设备、开设备或并发调用 LIN_EX；必须统一经过 `lin_device_manager`

## 2026-06-09 15:12 CAN 模型对齐切片

本轮按 CAN 的运行逻辑继续收敛 LIN：

- `main.py`
  - `SequenceRunner` 不再持有或直接调用 `LinService`
  - Runner 只持有轻量通道绑定 `{lin_sn, lin_index, baud_rate}`
  - 运行循环里的读写全部改为：
    - `lin_device_manager.exchange_status(...)`
    - `lin_device_manager.write_command(...)`
  - 单工位 CLI 和多工位 CLI 都先通过 `lin_device_manager.ensure_channel_initialized(...)` 建链，再把绑定传给 Runner
- `settings_ui.py`
  - UI 不再把中心 `LinService` 实例传给 Runner
  - 原 `station_services` 改为 `station_runtime_bindings`
  - 原“预加载服务”语义收缩为“预加载工位绑定/配置预检查”
  - 启动前只调用中心管理器初始化通道，Runner 后续仍通过中心管理器读写

当前主链路已经满足：

- UI 不直接调用 `USB_* / LIN_EX_*`
- 查询页不直接创建/释放 `LinService`
- Runner 不直接调用 `LinService.exchange_status/send_command`
- 只有 `lin_device_manager.py` 负责 USB2XXX 发现/打开/句柄缓存
- 只有 `lin_service.py` 负责 LIN_EX 帧级执行

## 2026-06-09 15:15 LIN 导入日志

本轮新增 10 工位 LIN 配置导入日志：

- 入口：`settings_ui.py::_preload_station_bindings()`
- 每次加载配置、恢复默认、保存配置、启动前刷新绑定时，都会按工位顺序输出日志
- 日志前缀格式：`[LIN_IMPORT x/10]`
- 每条日志包含：
  - 工位号
  - 工位名称
  - 导入状态
  - `SN`
  - `LIN Index`
  - 波特率
  - 扫码枪地址
- 日志同时写入：
  - Python `logger.info`
  - UI 的 `A045 LIN 运行日志` 页签

当前 `config.json` 验证输出为 10 条导入日志，结果：

- `BINDINGS=10`
- `ERRORS=0`

### PLC / 扫码 / UI / SSH 硬件验证 (19:00-21:07)

- **PLC**：两台 (192.168.10.180, 192.168.10.181) 通过 snap7 连通
- **扫码枪**：3 台 (192.168.10.164/166/168:8888) TCP 连通
- **UI 联机**：10 工位看板、扫描设备、启停工位、全量查询、CSV 导出均正常
- **SSH**：修复完毕，从本机可远程管理工控机

## 验证结果汇总 (2026-06-09)

| 类别 | 测试项 | 结果 |
|------|--------|------|
| 编译 | py_compile (5 模块) | PASS |
| 单测 | 11 unittest | PASS |
| LIN 设备发现 | USB_ScanDevice → 6 SN | 6/6 OK |
| LIN 设备打开 | USB_OpenDevice (修复后) | 6/6 OK |
| LIN 通信 | 10 工位 exchange_status | 10/10 OK |
| 同 SN 双工位 | 工位1+2 (共享 35A) | 无冲突，5 轮通过 |
| 完整序列(单) | Station 3，5 步 ~30s | 185 次读写 OK |
| 完整序列(双) | Station 1+2，各 5 步并行 | 105+100 次读写 OK |
| UI 看板 | 10 工位实时刷新 | OK |
| UI 启停/查询 | 启动/停止/查询全部 | OK |
| PLC | 2 台 snap7 连接 | OK |
| 扫码枪 | 3 台 TCP 连接 | OK |
| SSH 远程管理 | 编译/测试/文件管理 | OK |

## 下一步建议

全部验证通过，项目可交付使用。

## 换账号后如何继续

换账号后直接发：

```text
请先阅读 R:\老化LIN通讯\SESSION_HANDOFF.md，然后继续开发。
```

继续开发时先做：

```powershell
cd R:\老化LIN通讯
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py
python -m unittest test_a045_protocol.py test_main_config.py
```

## 2026-10-22 新增 A063 / A064 产品（同一界面四产品）

依据：`015 A063 A064 老化机程序/A063_A064_老化信号定义表.xlsx`（含保护策略、通讯矩阵汇总）。

### 本轮修改

- 新增 `a063_protocol.py`（前风暖，双温区）：发 `0x07`（Request + PowerSet1/2，16 位小端），收 `0x08` + `0x0A`。
  - 序列的 0~100% 同时下发到左右两区；POWER_1/POWER_2 → 看板左/右功率，Temperature1/2 → 左/右温度，PCBA 温度 → PCB 温度。
  - 母线电压 raw 0/1（未上高压 / <240 V）按 0 V 处理；ErrorMode0/1/2、ResponseError、LinComError、HV_interlock=1（未锁）、ErrorState 合成 `fault_code`，日志列出故障名。
- 新增 `a064_protocol.py`（后风暖，单温区）：发 `0x15`（HeatingReq 7 bit %，OnReq 0x2=on / 0x1=off），收 `0x16`。
  - 看板功率 = U×I 实测功率（左右相同）；芯体温度 → 左/右温度；IGBT 温度占 PCB 温度位（A064 不上报 PCBA），看板/日志卡/查询表该列标题自动改为“IGBT温度”。
  - 14 个故障位合成 `fault_code`。
- `product_catalog.py` / `runtime_protocols.py` 注册 A063、A064；设置页“产品型号”下拉自动出现四个产品。
- `product_presenter.py`：A063/A064 状态行与步骤汇总沿用 A045 格式，额外附 `current= igbt_temp= heat_pwr= limited= sw= hw= rx0A=` 字段。
- `main.py`：故障停机由 A050 专用改为按产品配置 `FAULT_STOP_CONFIRM_FRAMES`：A050 = 1 帧（原行为不变），A063/A064 = 连续 3 帧（约 300 ms）故障判 NG 并停机下发 0%。

### 验证结果

- 单测 98 个全部通过（新增 `test_a063_protocol.py`、`test_a064_protocol.py`、`test_a063_a064_runtime.py`、`test_settings_ui_a063_a064.py`，用定义表“报文示例”帧做样本）。
- Tk 界面启动、切换 A063/A064/A045 正常（无 USB2XXX / PLC 的开发机上验证）。
- **尚未上实机验证。**

### 待确认 / 下一步建议

1. A064 定义表“报文示例”中 0x16 的 Data[4]=0x02 按矩阵位定义是 FaultState=1、Status=0，与备注“Status=1；无故障”矛盾；程序按矩阵（bit32=Status，bit33=FaultState）实现，需用样件抓一帧确认。
2. A063 16 位信号（PowerSet、POWER_1/2）按小端实现，首件需确认。
3. 老化判据中的功率 ±10%、高压 ±5 V、温度余量等数值判定尚未实现（与 A045/A050 一致，目前只按故障位判 NG）。

## 2026-10-26 每个产品单独保存测试步骤和通信参数

### 本轮修改

- `config_store.py`：`config.json` 新增 `product_profiles`，按产品保存 `baud_rate`、`timing`（发送/读取间隔、Watchdog）、`step_plan`（测试步骤 + 冷却时长）。
  - 顶层 `device.baud_rate` / `timing` / `step_plan` / `sequence` 仍是**当前产品**的值，`main.py` 与运行逻辑不变；保存时当前产品的档案总以顶层为准。
  - 新增 `switch_product(config, code)`：把当前值存入原产品档案，再载入目标产品档案；目标产品还没有档案时沿用当前值。
  - 工位（SN / Index / 扫码枪 IP）、PLC、扫码配置为所有产品共用，切换时不变。
  - 旧 `config.json`（无 `product_profiles`）可直接加载，首次保存时自动生成当前产品档案。
- `settings_ui.py`：设置页切换“产品型号”时调用 `switch_product` 并保存，表单载入该产品的步骤与通信参数；“通信参数”“测试步骤配置”两个框标题显示当前产品；切换失败时下拉框恢复原产品。
- 模板会保存完整配置（含 `product_profiles`）。

### 验证结果

- 单测 106 个全部通过（新增 `test_product_profiles.py`）。
- 真实 Tk 界面脚本验证：A050 改步骤 → 切 A063（沿用）→ 改步骤和发送间隔 → 切回 A050（恢复 A050 的值）→ 再切 A063（恢复 A063 的值），`config.json` 中两份档案正确，工位配置不变。
- 尚未上实机验证。

## 2026-10-26 界面适配：文字超框、设置页超出屏幕

### 问题

- 界面最小需要约 2068×1192 像素：看板 11 列按固定字符宽度（width=18、字号 12）排布，设置页右栏固定 620 px 且关闭了自动伸缩。
- Tk 在 Windows 上不感知 DPI，1920×1080 屏幕在 125% 缩放下只有 1536×864 可用，因此看板右侧、底部的行和设置页的步骤按钮都被截掉，单元格内长文字溢出。

### 本轮修改（仅 `settings_ui.py`，不涉及通信与运行逻辑）

- 启动时按屏幕逻辑宽度选布局：< 1800 px 用紧凑布局（看板字号 10、行最小高度 28），否则字号 12。
- 看板：工位列平分宽度（`uniform`），文字按单元格实际宽度换行；超过 32/44 字符的内容截断加“…”，鼠标悬停（`HoverTip`）显示全文；“最新汇总”改为“第N步 左/右末功率 高压”，完整汇总行在悬停提示里。
- 设置页：工具栏和状态栏固定，内容放进 `ScrollableFrame`（超出时出现滚动条，支持滚轮）；左右两栏按 3:2 伸缩；“通信参数”移到右栏，与“测试步骤配置”放在一起；步骤行控件变窄，表头与输入框同一网格对齐；模板区拆成两行。
- 运行日志：最新事件/汇总按窗口宽度换行，状态卡片的值在列内换行；步骤汇总表与原始日志加横向滚动条。
- 全量查询：两张表加横向滚动条；“筛选记录”栏先于表格布局，不会再被挤出页面。

### 验证结果

- 截图验证 1366×728、1536×824（强制紧凑）和 1920×1040（正常）四个页签，均无截断；界面最小需求降到约 1450×640。
- 悬停提示、步骤汇总缩写、滚轮滚动（指针在输入框上）、产品切换脚本全部通过；单测 106 个通过。
- 开发机为 Linux，字体用 Noto CJK 代替微软雅黑，Windows 上字形宽度略有差异，需现场看一眼。

## 2026-10-26 A063 现场问题：只有一个加热管工作 → 新增 0x07 编码探测脚本

### 现场反馈

- A063 测试时只有一个加热管（一个温区）有功率，两个应同时工作；PLC 也没通讯上（PLC 待看现场日志，代码中 PLC 部分与产品无关）。

### 分析

- 程序按需求表下发 `0x07`：`01 p 00 p 00 00 00 00`（PowerSet1 = byte1-2、PowerSet2 = byte3-4，16 位低字节在前）。
- 若产品固件按其他格式解读（例如 PowerSet2 为 byte2 的 8 位值，或 16 位高字节在前），就会出现只有左区加热的现象。需要实测确认，不能靠猜。

### 本轮修改

- 新增 `probe_a063_lin.py`：对一个工位依次下发 5 种 `0x07` 编码（`spec_le16` / `left_only` / `right_only` / `u8_adjacent` / `be16`），每种持续 12 s、之间关闭 6 s，读取 `0x08` / `0x0A`，打印两区功率（按低在前、高在前两种解读）、电流、电压、温度、故障。
  - 用母线电流估算实际加热区数（100% 时单区约 3.4 A），给出汇总表；全部输出同时写入 `logs/probe_a063_<时间>.txt`。
  - 开始前需按回车确认（`--yes` 跳过）；退出或 Ctrl+C 时连续发送关闭帧。
- 新增 `test_probe_a063_lin.py`：用模拟产品（需求表固件 / byte2 8 位固件）验证探测与汇总判断。

### 验证结果

- 单测 110 个全部通过；端到端用模拟产品跑 `main()`，汇总能正确区分两种固件。
- 待现场运行，根据结果修改 `a063_protocol.py` 的 `0x07` 编码（以及必要时 POWER_1/2 解析）。
