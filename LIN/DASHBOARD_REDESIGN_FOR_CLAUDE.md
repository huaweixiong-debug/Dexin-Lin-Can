# A045 LIN 测试看板美化改造说明

## 目标

把 `R:\老化LIN通讯\settings_ui.py` 里的 `测试看板` 改成参考 `R:\老化CAN通讯\LGV2\test_monitor_ui.py` 的彩色状态表格风格。

当前问题：

- 看板几乎没有颜色，状态不醒目。
- 等待状态下大量单元格显示 `Waiting...`，噪声太多。
- 扫码枪 IP、SN、等待文字重复显示，占用空间。
- `ttk.Label` 不方便按单元格动态设置背景色。

改造要求：

- 保留当前 10 工位横向表格结构。
- 不改通信逻辑、不改配置字段、不改测试流程。
- 只改测试看板 UI、状态文字和颜色。
- 改完后必须更新 `SESSION_HANDOFF.md`。

## 参考项目

参考文件：

```text
R:\老化CAN通讯\LGV2\test_monitor_ui.py
```

重点参考：

- `create_grid_ui()`
- `update_cell(station_idx, item_idx, text, bg_color=None)`
- 使用 `tk.Label(..., bg=...)` 而不是 `ttk.Label`
- 状态单元格保存真实 Label 控件引用，然后通过 `lbl.config(text=..., bg=...)` 更新

## 当前 LIN 主要位置

需要修改：

```text
R:\老化LIN通讯\settings_ui.py
```

重点函数：

- `_build_dashboard_tab`
- `_refresh_dashboard_headers`
- `_reset_dashboard_values`
- `_reset_dashboard_station`
- `_set_dashboard_cell`
- `_sync_dashboard_loaded_bindings`
- `_update_dashboard_from_step`
- `_update_dashboard_from_status`
- `_update_dashboard_summary`
- `_poll_run_log_queue`

## 颜色规则

在 `settings_ui.py` 顶部新增颜色常量。

建议：

```python
DASHBOARD_COLORS = {
    "header": "#DCEBFA",
    "label": "#EDF2F7",
    "idle": "#F5F7FA",
    "blank": "#FFFFFF",
    "ready": "#D8F5D0",
    "running": "#BFE7FF",
    "waiting": "#FFF0B8",
    "warning": "#FFE3A3",
    "error": "#FFC9C9",
    "pass": "#8FE388",
    "fail": "#FF9B9B",
    "disabled": "#E5E7EB",
}
```

状态含义：

- `待连接 / 未连接`: `idle`
- `待启动 / 等待扫码`: `waiting`
- `已连接 / 就绪`: `ready`
- `运行中`: `running`
- `异常 / ERROR / FAIL`: `error` 或 `fail`
- `PASS`: `pass`
- `禁用`: `disabled`
- 测量值正常显示：`blank`

## UI 结构改造

### 1. 增加控件引用表

在 `SettingsApp.__init__` 中新增：

```python
self.dashboard_cell_widgets: Dict[str, Dict[int, tk.Label]] = {}
self.dashboard_header_widgets: Dict[int, tk.Label] = {}
```

保留已有：

```python
self.dashboard_cell_vars
self.dashboard_header_vars
```

这样可以最小化改动。

### 2. `_build_dashboard_tab` 改用 `tk.Label`

把测试看板表格里的表头、行名、数据格改成 `tk.Label`。

要求：

- 表头使用 `bg=DASHBOARD_COLORS["header"]`
- 左侧项目列使用 `bg=DASHBOARD_COLORS["label"]`
- 数据格默认 `bg=DASHBOARD_COLORS["blank"]`
- `relief="solid"` 或 `relief=tk.RIDGE` 均可，但风格保持统一
- 数据格创建后保存到：

```python
self.dashboard_cell_widgets[row_key][slot] = label
```

表头保存到：

```python
self.dashboard_header_widgets[slot] = label
```

启动/停止按钮可以继续用 `ttk.Button`，也可以参考 CAN 改成：

```python
tk.Button(..., bg="#90ee90")
tk.Button(..., bg="#ffcccb")
```

推荐只改看板单元格，按钮可暂时保留，避免引入样式兼容问题。

## 等待态文字规则

当前 `_reset_dashboard_station()` 会把所有字段写成 `Waiting...`。

必须改掉。

新规则：

```python
DEFAULT_DASHBOARD_VALUES = {
    "phase": "",
    "command": "",
    "run_state": "",
    "fault": "",
    "left_power": "",
    "right_power": "",
    "hv": "",
    "left_temp": "",
    "right_temp": "",
    "pcb_temp": "",
    "summary": "",
    "result": "",
}
```

`_reset_dashboard_station(slot)`：

- 所有测量字段清空
- 背景恢复 `blank`
- 不再出现 `Waiting...`

等待/未连接时只显示必要信息：

- `phase`: `待连接` 或 `待启动`
- `command`: `Index=0/1`
- `result`: `未连接 / 就绪 / 运行中 / 异常`

以下字段等待时必须为空：

- `run_state`
- `fault`
- `left_power`
- `right_power`
- `hv`
- `left_temp`
- `right_temp`
- `pcb_temp`

不要再在 `fault` 单元格显示 `扫码=IP`。

## `_set_dashboard_cell` 新签名

把 `_set_dashboard_cell` 改成支持颜色：

```python
def _set_dashboard_cell(self, slot: int, row_key: str, value: str, state: str | None = None) -> None:
    if row_key in self.dashboard_cell_vars and slot in self.dashboard_cell_vars[row_key]:
        self.dashboard_cell_vars[row_key][slot].set(value)
    widget = self.dashboard_cell_widgets.get(row_key, {}).get(slot)
    if widget is not None:
        widget.config(bg=self._dashboard_color_for_state(state, value), fg="#111827")
```

新增：

```python
def _dashboard_color_for_state(self, state: str | None, value: str = "") -> str:
    ...
```

推荐逻辑：

- 如果传入 `state`，按 `DASHBOARD_COLORS[state]` 返回。
- 如果未传入，根据 `value` 自动判断：
  - 包含 `PASS` 或 `通过`: pass
  - 包含 `FAIL` 或 `失败`: fail
  - 包含 `异常` 或 `ERROR`: error
  - 包含 `运行中`: running
  - 包含 `就绪` 或 `已连接`: ready
  - 包含 `待`: waiting
  - 包含 `未连接`: idle
  - 空字符串: blank

## 状态更新点

### `_sync_dashboard_loaded_bindings`

按状态传颜色：

- 未启用：
  - `phase = 未启用`, state=`disabled`
  - `result = 禁用`, state=`disabled`
- 配置错误：
  - `phase = 加载失败`, state=`error`
  - `result = 异常`, state=`error`
  - `fault = 错误文本`, state=`error`
- 有 SN 但未初始化：
  - `phase = 待连接`, state=`idle`
  - `command = Index=x`, state=`idle`
  - `result = 未连接`, state=`idle`
  - 不显示扫码 IP
  - `summary` 为空
- 已初始化：
  - `phase = 已连接`, state=`ready`
  - `command = Index=x`, state=`ready`
  - `result = 就绪`, state=`ready`
  - `summary` 为空

### `_update_dashboard_from_step`

运行中：

- `phase`: 当前步骤，state=`running`
- `command`: 功率/时间，state=`running`
- `result`: `运行中`，state=`running`

### `_update_dashboard_from_status`

测量数据：

- 有数值时更新对应格，state=`blank`
- 如果 `fault` 里包含严重故障或异常，可用 `warning` 或 `error`

### `_poll_run_log_queue`

退出结果：

- `PASS`: state=`pass`
- `FAIL`: state=`fail`
- `已停止`: state=`warning`
- 其他异常：state=`error`

### 启动失败路径

现有启动前检查失败处，要把 `result/fault` 设置为红色：

```python
self._set_dashboard_cell(station_slot, "result", "异常", state="error")
self._set_dashboard_cell(station_slot, "fault", error_text, state="error")
```

## 表头优化

`_refresh_dashboard_headers()` 中 SN 太长，建议缩短显示。

新增：

```python
def _short_serial(self, serial: str) -> str:
    serial = str(serial).strip()
    if not serial or serial == "未配置":
        return "未配置"
    if len(serial) <= 10:
        return serial
    return f"...{serial[-6:]}"
```

表头格式建议：

```python
self.dashboard_header_vars[slot].set(f"{name}\n{marker}\n{self._short_serial(serial)}")
```

`marker`：

- 当前活动工位：`运行`
- 其他：`待机`
- 未启用：`禁用`

## 系统提示文案

当前提示：

```text
当前版本先保留单工位执行逻辑，10 工位看板和 10 工位配置已经可用。运行时会把当前执行工位的状态实时写入对应列，其他工位保持等待。
```

改短：

```text
看板按工位显示 LIN 运行状态；空白表示等待或暂无数据，颜色表示当前状态。
```

## 验证命令

完成后必须执行：

```powershell
cd R:\老化LIN通讯
python -m py_compile lin_device_manager.py lin_service.py main.py settings_ui.py probe_a045_lin.py
python -m unittest test_a045_protocol.py test_main_config.py
```

如果本机 USB2XXX DLL 导入导致 UI 运行测试卡住，可以只做：

- `py_compile`
- 单元测试
- fake `lin_device_manager` 的 UI smoke test

## 手工验收

启动程序后确认：

- 看板不再整屏显示 `Waiting...`
- 未连接工位只有 `待连接 / Index / 未连接`
- 测量字段等待时为空白
- 已连接为绿色
- 运行中为蓝色
- 异常为红色
- PASS 为绿色
- FAIL 为红色
- 扫码枪 IP 不再塞到故障状态格
- SN 表头变短，不再挤爆列宽

## 交接记录

完成后更新：

```text
R:\老化LIN通讯\SESSION_HANDOFF.md
```

追加内容：

- 测试看板改成彩色 `tk.Label` 单元格
- 等待态取消 `Waiting...`
- 新增颜色规则
- 验证命令和结果
