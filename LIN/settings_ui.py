"""Tkinter-based multi-station settings editor and dashboard for LIN runners."""

from __future__ import annotations

import queue
import re
import itertools
import csv
import json
from copy import deepcopy
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List

from config_store import (
    CONFIG_FILE,
    STATION_COUNT,
    ConfigError,
    delete_template,
    get_default_config,
    list_templates,
    load_config,
    load_template,
    rename_template,
    save_config,
    save_template,
    switch_product,
    validate_config,
)
from lin_device_manager import lin_device_manager
from logger import logger
from product_catalog import DEFAULT_PRODUCT_CODE, get_product_definition, list_known_products
from product_presenter import adapt_status

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

RECORDS_FILE = Path(__file__).with_name("test_records.json")
STATUS_HISTORY_LIMIT = 10

DASHBOARD_ROWS = [
    ("phase", "当前步骤"),
    ("command", "当前命令"),
    ("run_state", "运行状态"),
    ("fault", "故障状态"),
    ("scan_result", "二维码"),
    ("left_power", "左功率"),
    ("right_power", "右功率"),
    ("hv", "高压"),
    ("left_temp", "左温度"),
    ("right_temp", "右温度"),
    ("pcb_temp", "PCB温度"),
    ("summary", "最新汇总"),
    ("result", "测试结果"),
]

DEFAULT_PCB_TEMP_LABEL = "PCB温度"
# A064 does not report PCBA temperature; its board-temperature slot carries IGBT.
PCB_TEMP_LABELS = {
    "A064": "IGBT温度",
}

# Logical screen widths below this use the compact layout. Tk is not DPI aware on
# Windows, so a 1920x1080 panel at 125 % scaling reports 1536x864.
COMPACT_SCREEN_WIDTH = 1800
# Longer dashboard values are cut with "…"; hovering the cell shows the full text.
DASHBOARD_TEXT_LIMIT = {True: 32, False: 44}


class ScrollableFrame(ttk.Frame):
    """Frame whose ``content`` scrolls when it is larger than the visible area."""

    def __init__(self, parent: tk.Misc, **kwargs: Any):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._y_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self._x_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self._y_scroll.set, xscrollcommand=self._x_scroll.set)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.content = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window(0, 0, window=self.content, anchor=tk.NW)
        self.content.bind("<Configure>", self._refit)
        self.canvas.bind("<Configure>", self._refit)
        # Global wheel bindings; the handler only acts while the pointer is over this frame.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sequence, self._on_mousewheel, add="+")

    def _refit(self, _event: object = None) -> None:
        # Stretch the content to the visible width, but never below what it needs.
        width = max(self.canvas.winfo_width(), self.content.winfo_reqwidth())
        self.canvas.itemconfigure(self._window, width=width)
        self.canvas.configure(scrollregion=(0, 0, width, self.content.winfo_reqheight()))
        # Only show the scrollbars that are actually needed.
        if self.content.winfo_reqheight() > self.canvas.winfo_height() > 1:
            self._y_scroll.grid(row=0, column=1, sticky=tk.NS)
        else:
            self._y_scroll.grid_remove()
            self.canvas.yview_moveto(0)
        if self.content.winfo_reqwidth() > self.canvas.winfo_width() > 1:
            self._x_scroll.grid(row=1, column=0, sticky=tk.EW)
        else:
            self._x_scroll.grid_remove()
            self.canvas.xview_moveto(0)

    def _pointer_inside(self, event: tk.Event) -> bool:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                return True
            widget = widget.master
        return False

    def _on_mousewheel(self, event: tk.Event) -> None:
        if not self._pointer_inside(event):
            return
        if self.content.winfo_reqheight() <= self.canvas.winfo_height():
            return
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step * 3, "units")


class HoverTip:
    """Shows a longer text next to a widget while the pointer rests on it."""

    def __init__(self, widget: tk.Widget, text_getter):
        self._widget = widget
        self._text_getter = text_getter
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event: tk.Event) -> None:
        text = self._text_getter()
        if not text or self._tip is not None:
            return
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        tk.Label(
            self._tip,
            text=text,
            bg="#FFFBE6",
            fg="#111827",
            relief=tk.SOLID,
            borderwidth=1,
            wraplength=460,
            justify=tk.LEFT,
            padx=6,
            pady=4,
        ).pack()

    def _hide(self, _event: object = None) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


def bind_wraplength(label: tk.Widget, owner: tk.Widget, margin: int = 24, minimum: int = 120) -> None:
    """Keep *label* wrapping to the current width of *owner*."""
    owner.bind(
        "<Configure>",
        lambda event: label.configure(wraplength=max(event.width - margin, minimum)),
        add="+",
    )


class InProcessRunTask:
    _pid_counter = itertools.count(1001)

    def __init__(self, station_slot: int, worker: threading.Thread, stop_event: threading.Event):
        self.station_slot = station_slot
        self._worker = worker
        self._stop_event = stop_event
        self.pid = next(self._pid_counter)
        self.exit_code: int | None = None

    def start(self) -> None:
        self._worker.start()

    def poll(self) -> int | None:
        if self._worker.is_alive():
            return None
        return self.exit_code

    def terminate(self) -> None:
        self._stop_event.set()


class SettingsApp:
    def __init__(self, root: tk.Tk, config_path: Path):
        self.root = root
        self.config_path = config_path
        self.sequence_rows: List[Dict[str, tk.StringVar]] = []
        self.station_rows: List[Dict[str, Any]] = []
        self.scanned_devices: List[Dict[str, Any]] = []
        self.dashboard_cell_vars: Dict[str, Dict[int, tk.StringVar]] = {}
        self.dashboard_cell_widgets: Dict[str, Dict[int, tk.Label]] = {}
        self.dashboard_header_vars: Dict[int, tk.StringVar] = {}
        self.dashboard_header_widgets: Dict[int, tk.Label] = {}
        self.dashboard_start_buttons: Dict[int, tk.Button] = {}
        self.dashboard_stop_buttons: Dict[int, tk.Button] = {}
        self.run_processes: Dict[int, InProcessRunTask] = {}
        self.run_log_queue: queue.Queue[tuple[int, str, str | int]] = queue.Queue()
        self._poll_active = False
        self._process_stations: Dict[int, List[int]] = {}
        self._process_readers: Dict[int, threading.Thread] = {}
        self._config_load_worker: threading.Thread | None = None
        self.station_runtime_bindings: Dict[int, Any] = {}
        self.station_binding_errors: Dict[int, str] = {}
        self.station_binding_registry_lock = threading.RLock()
        self.lin_device_manager = lin_device_manager
        self.notebook: ttk.Notebook | None = None
        self.dashboard_tab: ttk.Frame | None = None
        self.settings_tab: ttk.Frame | None = None
        self.run_log_tab: ttk.Frame | None = None
        self.query_tab: ttk.Frame | None = None
        self.run_log_text: tk.Text | None = None
        self.run_summary_tree: ttk.Treeview | None = None
        self.query_tree: ttk.Treeview | None = None
        self.query_record_tree: ttk.Treeview | None = None
        self.plc_enabled_var = tk.BooleanVar(value=False)
        self.scan_start_var = tk.BooleanVar(value=False)
        self.plc1_ip_var = tk.StringVar()
        self.plc2_ip_var = tk.StringVar()
        self.control_service_status_var = tk.StringVar(value="未启动")
        self.plc_controller = None
        self.scanner_manager = None
        self.control_services_running = False
        self.no_scan_thread: threading.Thread | None = None
        self.no_scan_stop_event = threading.Event()
        self.scan_results_by_station: Dict[int, str] = {}
        self.pending_start_slots: set[int] = set()
        self.station_fault_start: Dict[int, float] = {}
        self.station_fault_plc_sent: Dict[int, bool] = {}
        self.station_live_snapshot: Dict[int, Dict[str, str]] = {}
        self.station_status_history: Dict[int, List[Dict[str, str]]] = {}
        self.station_run_meta: Dict[int, Dict[str, str]] = {}
        self.completed_records: List[Dict[str, str]] = []

        self.root.title("LIN 多工位测试设备")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.compact_layout = screen_width < COMPACT_SCREEN_WIDTH
        base_size = 10 if self.compact_layout else 12
        self.dashboard_header_font = ("Microsoft YaHei UI", base_size, "bold")
        self.dashboard_label_font = ("Microsoft YaHei UI", base_size, "bold")
        self.dashboard_cell_font = ("Microsoft YaHei UI", base_size)
        self.dashboard_text_limit = DASHBOARD_TEXT_LIMIT[self.compact_layout]
        self.dashboard_cell_details: Dict[tuple[str, int], str] = {}
        style = ttk.Style(self.root)
        style.configure("Compact.TButton", padding=(4, 1))
        self.root.geometry(f"{min(1680, screen_width)}x{min(980, max(screen_height - 80, 600))}")
        self.root.minsize(1100, 640)
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

        self.product_options = tuple(product.code for product in list_known_products())
        self.product_var = tk.StringVar(value=DEFAULT_PRODUCT_CODE)
        self.active_station_var = tk.StringVar(value="1")
        self.scanned_device_var = tk.StringVar()
        self.baud_rate_var = tk.StringVar()
        self.send_interval_var = tk.StringVar()
        self.read_interval_var = tk.StringVar()
        self.watchdog_var = tk.StringVar()
        self.cooldown_duration_var = tk.StringVar()
        self.template_name_var = tk.StringVar()
        self.template_select_var = tk.StringVar()
        self.status_var = tk.StringVar(value="设置页面已就绪。")
        self.run_process_status_var = tk.StringVar(value="未运行")
        self.run_latest_event_var = tk.StringVar(value="尚未启动测试。")
        self.run_current_step_var = tk.StringVar(value="-")
        self.run_command_var = tk.StringVar(value="-")
        self.run_state_var = tk.StringVar(value="-")
        self.run_fault_var = tk.StringVar(value="-")
        self.run_left_power_var = tk.StringVar(value="-")
        self.run_right_power_var = tk.StringVar(value="-")
        self.run_hv_var = tk.StringVar(value="-")
        self.run_left_temp_var = tk.StringVar(value="-")
        self.run_right_temp_var = tk.StringVar(value="-")
        self.run_pcb_temp_var = tk.StringVar(value="-")
        self.run_summary_var = tk.StringVar(value="尚无汇总。")
        self.pcb_temp_label_var = tk.StringVar(value=DEFAULT_PCB_TEMP_LABEL)
        # Per-product communication parameters / step plans not shown in the form.
        self._product_profiles: Dict[str, Any] = {}
        self._form_product_code = DEFAULT_PRODUCT_CODE
        self.timing_frame: ttk.LabelFrame | None = None
        self.sequence_frame: ttk.LabelFrame | None = None

        self.product_var.trace_add("write", self._refresh_product_presentation)
        self.scanned_device_var.trace_add("write", self._on_scanned_device_var_changed)
        self.active_station_var.trace_add("write", self._on_active_station_changed)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_app_close)
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._exit_fullscreen)
        self.is_fullscreen = False

        self._build_layout()
        self._refresh_product_presentation()
        self._load_completed_records()
        self.load_into_form()

    def _build_layout(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.dashboard_tab = ttk.Frame(self.notebook, padding=10)
        self.settings_tab = ttk.Frame(self.notebook, padding=10)
        self.run_log_tab = ttk.Frame(self.notebook, padding=10)
        self.query_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.dashboard_tab, text="测试看板")
        self.notebook.add(self.settings_tab, text="设置页面")
        self.notebook.add(self.run_log_tab, text="LIN 运行日志")
        self.notebook.add(self.query_tab, text="全量查询")

        self._build_dashboard_tab(self.dashboard_tab)
        self._build_settings_tab(self.settings_tab)
        self._build_run_log_tab(self.run_log_tab)
        self._build_query_tab(self.query_tab)

    def _build_dashboard_tab(self, parent: ttk.Frame) -> None:
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top_frame, text="产品型号").pack(side=tk.LEFT)
        ttk.Label(top_frame, textvariable=self.product_var).pack(side=tk.LEFT, padx=(6, 20))
        ttk.Label(top_frame, text="运行工位").pack(side=tk.LEFT)
        ttk.Label(top_frame, textvariable=self.active_station_var).pack(side=tk.LEFT, padx=(6, 20))
        ttk.Label(top_frame, text="进程状态").pack(side=tk.LEFT)
        ttk.Label(top_frame, textvariable=self.run_process_status_var).pack(side=tk.LEFT, padx=(6, 20))
        ttk.Label(top_frame, text="控制服务").pack(side=tk.LEFT)
        ttk.Label(top_frame, textvariable=self.control_service_status_var).pack(side=tk.LEFT, padx=(6, 20))
        ttk.Button(top_frame, text="保存并运行", command=self.save_and_run).pack(side=tk.RIGHT)
        ttk.Button(top_frame, text="停止运行", command=self.stop_run_process).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(top_frame, text="打开日志页面", command=self._open_run_window).pack(side=tk.RIGHT, padx=(0, 8))

        grid_frame = ttk.LabelFrame(parent, text="10 工位测试看板", padding=8)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        # Row 0: Headers
        tk.Label(
            grid_frame,
            text="项目",
            width=self._dashboard_label_width(),
            anchor=tk.CENTER,
            font=self.dashboard_label_font,
            bg=DASHBOARD_COLORS["header"],
            relief=tk.RIDGE,
        ).grid(row=0, column=0, sticky=tk.NSEW, padx=1, pady=1)
        for slot in range(1, STATION_COUNT + 1):
            header_var = tk.StringVar(value=f"工位 {slot}\n未配置")
            self.dashboard_header_vars[slot] = header_var
            header_lbl = tk.Label(
                grid_frame,
                textvariable=header_var,
                width=1,
                anchor=tk.CENTER,
                relief=tk.RIDGE,
                font=self.dashboard_header_font,
                bg=DASHBOARD_COLORS["header"],
            )
            header_lbl.grid(row=0, column=slot, sticky=tk.NSEW, padx=1, pady=1)
            self._bind_cell_wraplength(header_lbl)
            self.dashboard_header_widgets[slot] = header_lbl

        # Row 1: Buttons
        button_row = 1
        tk.Label(
            grid_frame,
            text="操作",
            anchor=tk.CENTER,
            relief=tk.RIDGE,
            width=self._dashboard_label_width(),
            font=self.dashboard_label_font,
            bg=DASHBOARD_COLORS["label"],
        ).grid(row=button_row, column=0, sticky=tk.NSEW, padx=1, pady=1)
        for slot in range(1, STATION_COUNT + 1):
            btn_frame = tk.Frame(grid_frame, bg=DASHBOARD_COLORS["blank"])
            btn_frame.grid(row=button_row, column=slot, sticky=tk.NSEW, padx=1, pady=1)
            start_btn = tk.Button(btn_frame, text="启动", width=4, bg="#90ee90",
                                  command=lambda s=slot: self.start_station_run(s, trigger="MANUAL"))
            start_btn.pack(side=tk.LEFT, padx=(0, 4))
            stop_btn = tk.Button(btn_frame, text="停止", width=4, bg="#ffcccb",
                                 command=lambda s=slot: self.stop_station_run(s))
            stop_btn.pack(side=tk.LEFT)
            self.dashboard_start_buttons[slot] = start_btn
            self.dashboard_stop_buttons[slot] = stop_btn

        # Data rows
        for row_index, (row_key, row_label) in enumerate(DASHBOARD_ROWS, start=2):
            label_options = {"textvariable": self.pcb_temp_label_var} if row_key == "pcb_temp" else {"text": row_label}
            tk.Label(
                grid_frame,
                **label_options,
                anchor=tk.W,
                relief=tk.RIDGE,
                width=self._dashboard_label_width(),
                font=self.dashboard_label_font,
                bg=DASHBOARD_COLORS["label"],
            ).grid(row=row_index, column=0, sticky=tk.NSEW, padx=1, pady=2)
            self.dashboard_cell_vars[row_key] = {}
            self.dashboard_cell_widgets[row_key] = {}
            for slot in range(1, STATION_COUNT + 1):
                cell_var = tk.StringVar(value="")
                self.dashboard_cell_vars[row_key][slot] = cell_var
                cell_lbl = tk.Label(
                    grid_frame,
                    textvariable=cell_var,
                    anchor=tk.CENTER,
                    relief=tk.RIDGE,
                    width=1,
                    font=self.dashboard_cell_font,
                    bg=DASHBOARD_COLORS["blank"],
                    fg="#111827",
                    justify=tk.CENTER,
                )
                cell_lbl.grid(row=row_index, column=slot, sticky=tk.NSEW, padx=1, pady=2)
                self._bind_cell_wraplength(cell_lbl)
                HoverTip(cell_lbl, lambda key=(row_key, slot): self.dashboard_cell_details.get(key, ""))
                self.dashboard_cell_widgets[row_key][slot] = cell_lbl

        # Station columns share the width equally instead of demanding a fixed text width.
        grid_frame.columnconfigure(0, weight=0)
        for column in range(1, STATION_COUNT + 1):
            grid_frame.columnconfigure(column, weight=1, uniform="station")
        row_minsize = 28 if self.compact_layout else 40
        for row in range(len(DASHBOARD_ROWS) + 2):
            grid_frame.rowconfigure(row, weight=1, minsize=row_minsize)

        self._update_dashboard_button_states()

    def _dashboard_label_width(self) -> int:
        return 8 if self.compact_layout else 12

    @staticmethod
    def _bind_cell_wraplength(label: tk.Label) -> None:
        label.bind(
            "<Configure>",
            lambda event: label.configure(wraplength=max(event.width - 8, 40)),
            add="+",
        )

    def _refresh_product_presentation(self, *_args: object) -> None:
        product_code = self.product_var.get().strip().upper() or DEFAULT_PRODUCT_CODE
        if product_code != self.product_var.get():
            self.product_var.set(product_code)
            return

        definition = get_product_definition(product_code)
        display_name = definition.display_name if definition is not None else product_code
        self.root.title(f"{display_name} 多工位测试设备")
        if self.notebook is not None and self.run_log_tab is not None:
            self.notebook.tab(self.run_log_tab, text=f"{display_name} 运行日志")
        pcb_temp_label = PCB_TEMP_LABELS.get(product_code, DEFAULT_PCB_TEMP_LABEL)
        self.pcb_temp_label_var.set(pcb_temp_label)
        if self.query_tree is not None:
            self.query_tree.heading("pcb_temp", text=pcb_temp_label)
        if self.timing_frame is not None:
            self.timing_frame.configure(text=f"{product_code} 通信参数")
        if self.sequence_frame is not None:
            self.sequence_frame.configure(text=f"{product_code} 测试步骤配置（功率比例 0% - 100%）")

    def _on_product_selected(self, _event: object | None = None) -> None:
        new_code = self.product_var.get().strip().upper() or DEFAULT_PRODUCT_CODE
        previous_code = self._form_product_code
        if new_code == previous_code:
            self._refresh_product_presentation()
            return

        has_saved_profile = new_code in self._product_profiles
        try:
            # The form still holds the outgoing product's steps and parameters.
            form_config = self._collect_form_data()
            form_config["product"] = previous_code
            config = switch_product(form_config, new_code)
            save_config(self.config_path, config)
        except (ConfigError, ValueError) as exc:
            self.product_var.set(previous_code)
            messagebox.showerror("产品切换失败", str(exc))
            self.status_var.set(f"产品切换失败: {exc}")
            return

        self._apply_config_to_form(config)
        if not self._has_running_station_tasks():
            self._start_config_load_worker(config)
        self._refresh_dashboard_headers()
        if has_saved_profile:
            self.status_var.set(f"产品型号已切换为 {new_code}，已载入该产品的测试步骤和通信参数")
        else:
            self.status_var.set(
                f"产品型号已切换为 {new_code}，该产品尚无单独设置，沿用当前测试步骤和通信参数；修改后保存即为 {new_code} 的设置"
            )

    def _short_serial(self, serial: str) -> str:
        serial = str(serial).strip()
        if not serial or serial == "未配置":
            return "未配置"
        if len(serial) <= 10:
            return serial
        return f"...{serial[-6:]}"

    def _dashboard_color_for_state(self, state: str | None, value: str = "") -> str:
        if state and state in DASHBOARD_COLORS:
            return DASHBOARD_COLORS[state]
        if not value:
            return DASHBOARD_COLORS["blank"]
        if "PASS" in value or "通过" in value:
            return DASHBOARD_COLORS["pass"]
        if "FAIL" in value or "失败" in value:
            return DASHBOARD_COLORS["fail"]
        if "no_fault" in value:
            return DASHBOARD_COLORS["ready"]
        if "fault" in value.lower() or "异常" in value or "ERROR" in value:
            return DASHBOARD_COLORS["error"]
        if "运行中" in value:
            return DASHBOARD_COLORS["running"]
        if "就绪" in value or "已连接" in value:
            return DASHBOARD_COLORS["ready"]
        if "待" in value:
            return DASHBOARD_COLORS["waiting"]
        if "未连接" in value:
            return DASHBOARD_COLORS["idle"]
        return DASHBOARD_COLORS["blank"]

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        top_tools = ttk.Frame(parent)
        top_tools.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(top_tools, text="加载配置", command=self.load_into_form).pack(side=tk.LEFT)
        ttk.Button(top_tools, text="恢复默认", command=self.reset_defaults).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(top_tools, text="产品型号").pack(side=tk.LEFT, padx=(24, 8))
        self.product_combo = ttk.Combobox(
            top_tools,
            textvariable=self.product_var,
            values=self.product_options,
            width=10,
            state="readonly",
        )
        self.product_combo.pack(side=tk.LEFT)
        self.product_combo.bind("<<ComboboxSelected>>", self._on_product_selected)
        ttk.Button(top_tools, text="启动PLC/扫码", command=self.start_control_services).pack(side=tk.LEFT, padx=(24, 0))
        ttk.Button(top_tools, text="停止PLC/扫码", command=self.stop_control_services).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_tools, text="保存配置", command=self.save_from_form).pack(side=tk.RIGHT)
        ttk.Button(top_tools, text="保存并运行", command=self.save_and_run).pack(side=tk.RIGHT, padx=(0, 8))

        # Status line stays visible below the toolbar; the rest of the page scrolls.
        status_label = ttk.Label(parent, textvariable=self.status_var, foreground="#1f4e79", justify=tk.LEFT)
        status_label.pack(fill=tk.X, pady=(0, 6))
        bind_wraplength(status_label, parent)

        page = ScrollableFrame(parent)
        page.pack(fill=tk.BOTH, expand=True)
        content_frame = page.content
        content_frame.columnconfigure(0, weight=3)
        content_frame.columnconfigure(1, weight=2)
        content_frame.rowconfigure(0, weight=1)

        left_column = ttk.Frame(content_frame)
        left_column.grid(row=0, column=0, sticky=tk.NSEW)

        right_column = ttk.Frame(content_frame)
        right_column.grid(row=0, column=1, sticky=tk.NSEW, padx=(12, 0))

        scan_frame = ttk.LabelFrame(left_column, text="设备扫描", padding=8)
        scan_frame.pack(fill=tk.X, pady=(0, 8))
        scan_frame.columnconfigure(1, weight=1)
        ttk.Label(scan_frame, text="已扫描 USB2XXX").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.scanned_device_combo = ttk.Combobox(
            scan_frame,
            textvariable=self.scanned_device_var,
            width=36,
            state="readonly",
        )
        self.scanned_device_combo.grid(row=0, column=1, sticky=tk.EW, pady=4)
        self.scanned_device_combo.bind("<<ComboboxSelected>>", self._on_scanned_device_selected)
        ttk.Button(scan_frame, text="扫描设备", command=self.scan_lin_devices).grid(
            row=0, column=2, sticky=tk.W, padx=(12, 8), pady=4
        )
        ttk.Button(scan_frame, text="填入当前工位", command=self.use_selected_scanned_device).grid(
            row=0, column=3, sticky=tk.W, pady=4
        )

        station_frame = ttk.LabelFrame(left_column, text="10 工位 LIN / 扫码配置", padding=8)
        station_frame.pack(fill=tk.X, pady=(0, 8))
        station_headers = ["工位", "启用", "名称", "LIN 序列号", "Index", "扫码枪 IP", "当前", "填入"]
        for column, header in enumerate(station_headers):
            ttk.Label(station_frame, text=header).grid(row=0, column=column, sticky=tk.W, padx=4, pady=(0, 6))
        station_frame.columnconfigure(3, weight=2)
        station_frame.columnconfigure(5, weight=1)

        self.station_rows = []
        for slot in range(1, STATION_COUNT + 1):
            enabled_var = tk.BooleanVar(value=True)
            name_var = tk.StringVar(value=f"工位 {slot}")
            lin_sn_var = tk.StringVar()
            lin_index_var = tk.StringVar(value="0")
            scanner_ip_var = tk.StringVar()
            ttk.Label(station_frame, text=f"工位 {slot}").grid(row=slot, column=0, sticky=tk.W, padx=4, pady=2)
            ttk.Checkbutton(station_frame, variable=enabled_var).grid(row=slot, column=1, sticky=tk.W, padx=4, pady=2)
            ttk.Entry(station_frame, textvariable=name_var, width=9).grid(row=slot, column=2, sticky=tk.W, padx=4, pady=2)
            ttk.Entry(station_frame, textvariable=lin_sn_var, width=26).grid(row=slot, column=3, sticky=tk.EW, padx=4, pady=2)
            ttk.Entry(station_frame, textvariable=lin_index_var, width=5).grid(row=slot, column=4, sticky=tk.W, padx=4, pady=2)
            ttk.Entry(station_frame, textvariable=scanner_ip_var, width=19).grid(row=slot, column=5, sticky=tk.EW, padx=4, pady=2)
            ttk.Radiobutton(station_frame, variable=self.active_station_var, value=str(slot)).grid(
                row=slot, column=6, sticky=tk.W, padx=8, pady=2
            )
            ttk.Button(
                station_frame,
                text="填入序列号",
                style="Compact.TButton",
                command=lambda current_slot=slot: self.apply_scanned_device_to_station(current_slot),
            ).grid(row=slot, column=7, sticky=tk.W, padx=4, pady=2)
            self.station_rows.append(
                {
                    "slot": slot,
                    "enabled": enabled_var,
                    "name": name_var,
                    "lin_sn": lin_sn_var,
                    "lin_index": lin_index_var,
                    "scanner_ip": scanner_ip_var,
                }
            )

        plc_frame = ttk.LabelFrame(left_column, text="PLC / 扫码联动", padding=8)
        plc_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(plc_frame, text="启用 PLC 联动", variable=self.plc_enabled_var).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 16), pady=4
        )
        ttk.Checkbutton(plc_frame, text="扫码完成后允许 PLC 启动", variable=self.scan_start_var).grid(
            row=0, column=1, sticky=tk.W, padx=(0, 16), pady=4
        )
        ttk.Label(plc_frame, text="PLC1 IP").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(plc_frame, textvariable=self.plc1_ip_var, width=16).grid(row=1, column=1, sticky=tk.W, pady=4)
        ttk.Label(plc_frame, text="PLC2 IP").grid(row=1, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Entry(plc_frame, textvariable=self.plc2_ip_var, width=16).grid(row=1, column=3, sticky=tk.W, pady=4)
        ttk.Label(plc_frame, text="服务状态").grid(row=0, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Label(plc_frame, textvariable=self.control_service_status_var).grid(row=0, column=3, sticky=tk.W, pady=4)

        template_frame = ttk.LabelFrame(left_column, text="配置模板", padding=8)
        template_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(template_frame, text="模板名称").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(template_frame, textvariable=self.template_name_var, width=22).grid(
            row=0, column=1, sticky=tk.W, pady=4
        )
        ttk.Button(template_frame, text="保存模板", command=self.save_as_template).grid(
            row=0, column=2, sticky=tk.W, padx=(8, 0), pady=4
        )
        ttk.Label(template_frame, text="已有模板").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.template_combo = ttk.Combobox(
            template_frame,
            textvariable=self.template_select_var,
            width=20,
            state="readonly",
        )
        self.template_combo.grid(row=1, column=1, sticky=tk.W, pady=4)
        template_actions = ttk.Frame(template_frame)
        template_actions.grid(row=1, column=2, sticky=tk.W, padx=(8, 0), pady=4)
        ttk.Button(template_actions, text="加载模板", command=self.load_selected_template).pack(side=tk.LEFT)
        ttk.Button(template_actions, text="重命名模板", command=self.rename_selected_template).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(template_actions, text="删除模板", command=self.delete_selected_template).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        # Product-specific settings sit together in the right column.
        timing_frame = ttk.LabelFrame(right_column, text="通信参数", padding=8)
        self.timing_frame = timing_frame
        timing_frame.pack(fill=tk.X, pady=(0, 8))
        timing_fields = [
            ("波特率", self.baud_rate_var),
            ("发送间隔(ms)", self.send_interval_var),
            ("读取间隔(ms)", self.read_interval_var),
            ("Watchdog(s)", self.watchdog_var),
            ("冷却时长(s)", self.cooldown_duration_var),
        ]
        for index, (label_text, variable) in enumerate(timing_fields):
            row, column = divmod(index, 3)
            ttk.Label(timing_frame, text=label_text).grid(
                row=row, column=column * 2, sticky=tk.W, padx=(0 if column == 0 else 16, 6), pady=4
            )
            ttk.Entry(timing_frame, textvariable=variable, width=8).grid(row=row, column=column * 2 + 1, sticky=tk.W, pady=4)

        sequence_frame = ttk.LabelFrame(right_column, text="测试步骤配置（功率比例 0% - 100%）", padding=8)
        self.sequence_frame = sequence_frame
        sequence_frame.pack(fill=tk.BOTH, expand=True)
        self.sequence_container = ttk.Frame(sequence_frame)
        self.sequence_container.grid(row=0, column=0, sticky=tk.NSEW)
        sequence_frame.columnconfigure(0, weight=1)
        sequence_frame.rowconfigure(0, weight=1)

        sequence_action_frame = ttk.Frame(sequence_frame)
        sequence_action_frame.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(sequence_action_frame, text="新增步骤", command=self.add_step_row).pack(side=tk.LEFT)
        ttk.Button(sequence_action_frame, text="删除末项", command=self.remove_last_step_row).pack(
            side=tk.LEFT, padx=(8, 0)
        )

    def load_into_form(self) -> None:
        if self.control_services_running:
            self._stop_control_services_internal()
            self.control_service_status_var.set("未启动")
        try:
            config = validate_config(load_config(self.config_path))
        except ConfigError as exc:
            messagebox.showwarning("配置加载失败", f"{exc}\n将加载默认配置。")
            config = get_default_config()

        self._apply_config_to_form(config)
        self.refresh_templates()
        self._refresh_dashboard_headers()
        self._reset_dashboard_values()
        self._sync_dashboard_loaded_bindings()
        self.status_var.set(f"已加载配置，正在后台连接设备: {self.config_path}")
        self._start_config_load_worker(config)
        return
        self._preload_station_bindings(config)
        self._sync_dashboard_loaded_bindings()
        if config.get("plc", {}).get("enabled", False):
            self._ensure_control_services_running(config, force_restart=False)
        self._log_plc_status()
        self.status_var.set(f"已加载配置: {self.config_path}")

    def _start_config_load_worker(self, config: Dict[str, Any]) -> None:
        if self._config_load_worker is not None and self._config_load_worker.is_alive():
            self.status_var.set("设备连接仍在进行中，请稍候")
            return

        config_snapshot = dict(config)

        def _worker() -> None:
            error_text = ""
            try:
                self._preload_station_bindings(config_snapshot)
                if config_snapshot.get("plc", {}).get("enabled", False):
                    self._ensure_control_services_running(config_snapshot, force_restart=False)
            except Exception as exc:
                error_text = str(exc)

            def _finish() -> None:
                self._sync_dashboard_loaded_bindings()
                self._log_plc_status()
                if error_text:
                    self.status_var.set(f"后台连接设备失败: {error_text}")
                else:
                    self.status_var.set(f"配置已加载，设备连接完成: {self.config_path}")

            self.root.after(0, _finish)

        self._config_load_worker = threading.Thread(target=_worker, daemon=True)
        self._config_load_worker.start()

    def reset_defaults(self) -> None:
        if self.control_services_running:
            self._stop_control_services_internal()
            self.control_service_status_var.set("未启动")
        config = get_default_config()
        self._apply_config_to_form(config)
        self.refresh_templates()
        self._refresh_dashboard_headers()
        self._reset_dashboard_values()
        self._preload_station_bindings(config)
        self._sync_dashboard_loaded_bindings()
        self.status_var.set("已恢复默认配置，尚未保存。")

    def save_from_form(self, show_message: bool = True) -> bool:
        try:
            config = self._collect_form_data()
            save_config(self.config_path, config)
            self.status_var.set(f"保存成功: {self.config_path}")
            if not self._has_running_station_tasks():
                self._preload_station_bindings(config)
            self._refresh_dashboard_headers()
            self._sync_dashboard_loaded_bindings()
            if show_message:
                messagebox.showinfo("保存成功", "设置已保存。")
            self.refresh_templates()
            return True
        except (ConfigError, ValueError) as exc:
            messagebox.showerror("保存失败", str(exc))
            self.status_var.set(f"保存失败: {exc}")
            return False

    def start_control_services(self) -> None:
        try:
            config = validate_config(self._collect_form_data())
        except (ConfigError, ValueError) as exc:
            messagebox.showerror("启动 PLC/扫码 失败", str(exc))
            self.status_var.set(f"控制服务启动失败: {exc}")
            return

        if self._ensure_control_services_running(config, force_restart=True):
            self.status_var.set("PLC/扫码服务已启动。")

    def stop_control_services(self) -> None:
        self._stop_control_services_internal()
        self.control_service_status_var.set("未启动")
        self.status_var.set("PLC/扫码服务已停止。")

    def _ensure_control_services_running(self, config: Dict[str, Any], force_restart: bool = False) -> bool:
        if self.control_services_running and not force_restart:
            return True

        self._stop_control_services_internal()

        try:
            from plc_service import PLCController, PLCServiceError
            from scanner_service import ScannerManager
        except Exception as exc:
            messagebox.showerror("控制服务加载失败", str(exc))
            self.control_service_status_var.set("加载失败")
            self.status_var.set(f"控制服务加载失败: {exc}")
            return False

        self.scan_results_by_station = {}
        self.pending_start_slots = set()
        self.scanner_manager = ScannerManager()
        scanner_count = 0
        for station in config["stations"]:
            scanner_ip = str(station.get("scanner_ip", "")).strip()
            if station.get("enabled", True) and scanner_ip:
                self.scanner_manager.add_scanner(int(station["slot"]), scanner_ip)
                scanner_count += 1
        if scanner_count:
            self.scanner_manager.start_auto_scan_all(self._on_station_scan_result)

        self.plc_controller = None
        if config.get("plc", {}).get("enabled", False):
            try:
                self.plc_controller = PLCController(
                    plc1_ip=str(config["plc"]["plc1_ip"]),
                    plc2_ip=str(config["plc"]["plc2_ip"]),
                )
                self.plc_controller.set_callbacks(
                    self._handle_plc_start_signal,
                    self._handle_plc_stop_signal,
                    self._handle_plc_emergency_stop,
                    self._handle_plc_reset,
                    self._handle_plc_comm_restart,
                )
                self.plc_controller.set_log_callback(self._on_control_service_log)
                self.plc_controller.start()
            except PLCServiceError as exc:
                messagebox.showerror("PLC 启动失败", str(exc))
                self.control_service_status_var.set("PLC失败")
                self.status_var.set(f"PLC 启动失败: {exc}")
                self._stop_control_services_internal()
                return False

        self.control_services_running = True
        self.control_service_status_var.set(f"运行中 | PLC={'ON' if self.plc_controller else 'OFF'} 扫码={scanner_count}")
        if self.plc_controller and not config.get("scan", {}).get("scan_start", False):
            self._start_no_scan_loop(config)
        self.root.after(500, self._log_plc_status)
        return True

    def _stop_control_services_internal(self) -> None:
        self.no_scan_stop_event.set()
        if self.no_scan_thread and self.no_scan_thread.is_alive():
            self.no_scan_thread.join(timeout=2)
        self.no_scan_thread = None
        self.no_scan_stop_event = threading.Event()

        if self.scanner_manager is not None:
            try:
                self.scanner_manager.stop_auto_scan_all()
                self.scanner_manager.disconnect_all()
            except Exception:
                pass
        self.scanner_manager = None

        if self.plc_controller is not None:
            try:
                self.plc_controller.stop()
            except Exception:
                pass
        self.plc_controller = None
        self.control_services_running = False

    def _close_station_bindings(self) -> None:
        with self.station_binding_registry_lock:
            self.lin_device_manager.close_all()
            self.station_runtime_bindings = {}
            self.station_binding_errors = {}

    def _preload_station_bindings(self, config: Dict[str, Any]) -> None:
        self._close_station_bindings()
        baud_rate = int(config.get("device", {}).get("baud_rate", 19200))
        stations = sorted(config.get("stations", []), key=lambda item: int(item.get("slot", 0)))
        total = len(stations)
        for position, station in enumerate(stations, start=1):
            slot = int(station["slot"])
            name = str(station.get("name", f"工位 {slot}")).strip() or f"工位 {slot}"
            scanner_ip = str(station.get("scanner_ip", "")).strip()
            if not station.get("enabled", True):
                self._log_lin_import(position, total, slot, name, "未启用", "-", "-", baud_rate, scanner_ip)
                continue
            serial = str(station.get("lin_sn", "")).strip().upper()
            if not serial:
                self.station_binding_errors[slot] = "未配置 LIN 序列号"
                self._log_lin_import(position, total, slot, name, "导入失败: 未配置 LIN 序列号", "-", "-", baud_rate, scanner_ip)
                continue
            try:
                lin_index = int(station.get("lin_index", 0))
            except Exception as exc:
                self.station_binding_errors[slot] = f"LIN Index 无效: {exc}"
                self._log_lin_import(position, total, slot, name, f"导入失败: LIN Index 无效: {exc}", serial, "-", baud_rate, scanner_ip)
                continue
            self.station_runtime_bindings[slot] = {
                "lin_sn": serial,
                "lin_index": lin_index,
                "baud_rate": baud_rate,
            }
            self._log_lin_import(position, total, slot, name, "已导入", serial, lin_index, baud_rate, scanner_ip)

        # Pre-open all LIN devices in one scan to avoid disruptive re-scans during test
        all_sns: List[str] = []
        for station in stations:
            slot = int(station["slot"])
            binding = self.station_runtime_bindings.get(slot)
            if not binding:
                continue
            serial = str(binding["lin_sn"]).strip().upper()
            if serial and serial not in all_sns:
                all_sns.append(serial)
        if all_sns:
            try:
                self.lin_device_manager.open_all_devices(all_sns)
                logger.info("[LIN_OPEN] Pre-opened %s LIN devices: %s", len(all_sns), all_sns)
            except Exception as exc:
                logger.error("[LIN_OPEN] Failed to pre-open all LIN devices: %s", exc)

        for station in stations:
            slot = int(station["slot"])
            binding = self.station_runtime_bindings.get(slot)
            if not binding or slot in self.station_binding_errors:
                continue
            try:
                self.lin_device_manager.ensure_channel_initialized(
                    binding["lin_sn"],
                    binding["lin_index"],
                    binding["baud_rate"],
                    config.get("product", DEFAULT_PRODUCT_CODE),
                )
                line = (
                    f"[LIN_INIT_PRELOAD] station={slot} "
                    f"SN={binding['lin_sn']} index={binding['lin_index']} ready=True"
                )
                logger.info(line)
                self._append_run_log(line)
            except Exception as exc:
                error_text = f"通道预初始化失败: {exc}"
                self.station_binding_errors[slot] = error_text
                line = (
                    f"[LIN_INIT_PRELOAD] station={slot} "
                    f"SN={binding['lin_sn']} index={binding['lin_index']} ready=False error={exc}"
                )
                logger.error(line)
                self._append_run_log(line)

    def _log_plc_status(self) -> None:
        try:
            import socket
            plc1 = self.plc1_ip_var.get().strip()
            plc2 = self.plc2_ip_var.get().strip()
            enabled = self.plc_enabled_var.get()
            if not enabled:
                line = "[PLC_STATUS] PLC未启用"
                logger.info(line)
                self._append_run_log(line)
                return
            for ip, name in [(plc1, "PLC1"), (plc2, "PLC2")]:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((ip, 102))
                    sock.close()
                    line = f"[PLC_STATUS] {name} {ip}:102 TCP可达"
                except Exception as e:
                    line = f"[PLC_STATUS] {name} {ip}:102 TCP不可达 ({e})"
                logger.info(line)
                self._append_run_log(line)
        except Exception as e:
            line = f"[PLC_STATUS] 检测异常: {e}"
            logger.info(line)
            self._append_run_log(line)

    def _log_lin_import(
        self,
        position: int,
        total: int,
        slot: int,
        name: str,
        state: str,
        serial: str,
        lin_index: int | str,
        baud_rate: int,
        scanner_ip: str,
    ) -> None:
        line = (
            f"[LIN_IMPORT {position}/{total}] 工位{slot} {name} | {state} | "
            f"SN={serial} | Index={lin_index} | Baud={baud_rate} | 扫码={scanner_ip or '-'}"
        )
        logger.info(line)
        self._append_run_log(line)

    def _get_station_config(self, config: Dict[str, Any], station_slot: int) -> Dict[str, Any]:
        for station in config.get("stations", []):
            if int(station.get("slot", 0)) == station_slot:
                return station
        raise ConfigError(f"工位 {station_slot} 配置不存在")

    def _get_station_runtime_binding(self, config: Dict[str, Any], station_slot: int) -> Dict[str, Any]:
        with self.station_binding_registry_lock:
            binding = self.station_runtime_bindings.get(station_slot)
            if binding is not None:
                return binding

            station = self._get_station_config(config, station_slot)
            serial = str(station.get("lin_sn", "")).strip().upper()
            if not serial:
                raise ConfigError(f"工位 {station_slot} 未配置 LIN 序列号")

            lin_index = int(station.get("lin_index", 0))
            baud_rate = int(config.get("device", {}).get("baud_rate", 19200))
            binding = {
                "lin_sn": serial,
                "lin_index": lin_index,
                "baud_rate": baud_rate,
            }
            self.station_runtime_bindings[station_slot] = binding
            return binding

    def _ensure_station_channel(self, config: Dict[str, Any], station_slot: int):
        binding = self._get_station_runtime_binding(config, station_slot)
        self.lin_device_manager.ensure_channel_initialized(
            binding["lin_sn"],
            binding["lin_index"],
            binding["baud_rate"],
            config.get("product", DEFAULT_PRODUCT_CODE),
        )
        return binding

    def _release_station_binding(self, station_slot: int) -> None:
        return

    def _start_no_scan_loop(self, config: Dict[str, Any]) -> None:
        stations = [int(station["slot"]) for station in config["stations"] if station.get("enabled", True)]
        if not stations:
            return

        def _worker() -> None:
            while not self.no_scan_stop_event.is_set():
                if self.plc_controller is not None:
                    if not (self.plc_controller.connected1 or self.plc_controller.connected2):
                        self.no_scan_stop_event.wait(2.0)
                        continue
                    for slot in stations:
                        proc = self.run_processes.get(slot)
                        if proc is not None and proc.poll() is None:
                            continue
                        try:
                            self.plc_controller.write_status(slot, "SCAN_OK", True)
                        except Exception:
                            pass
                self.no_scan_stop_event.wait(2.0)

        self.no_scan_thread = threading.Thread(target=_worker, daemon=True)
        self.no_scan_thread.start()

    def _on_control_service_log(self, message: str) -> None:
        self.root.after(0, lambda: self._append_control_service_log(message))

    def _append_control_service_log(self, message: str) -> None:
        self.status_var.set(message)
        if self.run_log_text is not None and self.run_log_text.winfo_exists():
            self._append_run_log(f"[PLC] {message}")

    def _on_station_scan_result(self, station_idx: int, scan_result: str) -> None:
        self.root.after(0, lambda: self._handle_scan_result_ui(station_idx, scan_result))

    def _handle_scan_result_ui(self, station_idx: int, scan_result: str) -> None:
        self.scan_results_by_station[station_idx] = scan_result
        self._set_dashboard_cell(station_idx, "phase", "扫码完成", state="ready")
        self._set_dashboard_cell(station_idx, "scan_result", scan_result, state="ready")
        self._set_dashboard_cell(station_idx, "result", "等待启动", state="waiting")
        self.run_latest_event_var.set(f"[SCAN] station={station_idx} result={scan_result}")
        if self.plc_controller and self.scan_start_var.get():
            self.plc_controller.write_status(station_idx, "SCAN_OK", True)
        if station_idx in self.pending_start_slots:
            self.pending_start_slots.discard(station_idx)
            self.start_station_run(station_idx, trigger="SCAN_READY")

    def _handle_plc_start_signal(self, station_idx: int) -> None:
        self.root.after(0, lambda: self._process_plc_start_signal(station_idx))

    def _process_plc_start_signal(self, station_idx: int) -> None:
        if self.scan_start_var.get() and not self.scan_results_by_station.get(station_idx):
            self.pending_start_slots.add(station_idx)
            self._set_dashboard_cell(station_idx, "result", "等待扫码", state="waiting")
            self.status_var.set(f"工位 {station_idx} 收到 PLC 启动，但尚未扫码。")
            return
        self.start_station_run(station_idx, trigger="PLC_START")

    def _handle_plc_stop_signal(self, station_idx: int) -> None:
        self.root.after(0, lambda: self._process_plc_stop_like_signal(station_idx, "STOP"))

    def _handle_plc_emergency_stop(self, station_idx: int) -> None:
        self.root.after(0, lambda: self._process_plc_stop_like_signal(station_idx, "EMERGENCY"))

    def _handle_plc_reset(self, station_idx: int) -> None:
        self.root.after(0, lambda: self._process_plc_stop_like_signal(station_idx, "RESET"))

    def _handle_plc_comm_restart(self, station_idx: int) -> None:
        self.root.after(0, lambda: self._process_plc_comm_restart(station_idx))

    def _process_plc_comm_restart(self, station_idx: int) -> None:
        self._process_plc_stop_like_signal(station_idx, "COMM_RESTART")
        if self.plc_controller is not None:
            self.plc_controller.write_status_pulse(station_idx, "COMM_RESTART_DONE", duration=2.0)

    def _process_plc_stop_like_signal(self, station_idx: int, reason: str) -> None:
        self.status_var.set(f"工位 {station_idx} 收到 PLC {reason} 信号。")
        self.pending_start_slots.discard(station_idx)
        self.scan_results_by_station.pop(station_idx, None)
        if self.plc_controller is not None:
            self.plc_controller.write_status(station_idx, "SCAN_OK", False)
            self.plc_controller.write_status(station_idx, "PASS", False)
            self.plc_controller.write_status(station_idx, "FAIL", False)
        if station_idx in self.run_processes:
            proc = self.run_processes[station_idx]
            if proc.poll() is None:
                self._stop_station_process(station_idx)

    def save_and_run(self) -> None:
        self.start_station_run(int(self.active_station_var.get().strip() or "1"), trigger="MANUAL")

    def start_station_run(self, station_slot: int, trigger: str = "MANUAL") -> None:
        existing = self.run_processes.get(station_slot)
        if existing is not None and existing.poll() is None:
            self.status_var.set(f"工位 {station_slot} 已在运行中。")
            if trigger == "MANUAL":
                messagebox.showwarning("测试运行中", f"工位 {station_slot} 已在运行中。")
            return
        if existing is not None:
            del self.run_processes[station_slot]

        self.active_station_var.set(str(station_slot))
        active_row = self.station_rows[station_slot - 1]
        target_sn = active_row["lin_sn"].get().strip().upper()
        target_index = active_row["lin_index"].get().strip() or "0"

        try:
            raw_config = self._collect_form_data()
            base_config = validate_config(raw_config)
            save_config(self.config_path, raw_config)
            if not self._has_running_station_tasks():
                # Only reload bindings if first station or bindings are stale
                needs_reload = not self.station_runtime_bindings or station_slot in self.station_binding_errors
                if needs_reload:
                    self._preload_station_bindings(base_config)
                self._sync_dashboard_loaded_bindings()
            config = validate_config(raw_config, station_override=station_slot)
        except (ConfigError, ValueError) as exc:
            if trigger == "MANUAL":
                messagebox.showerror("保存失败", str(exc))
            self.status_var.set(f"保存失败: {exc}")
            return
        if not self._ensure_control_services_running(base_config, force_restart=False):
            return
        if station_slot in self.station_binding_errors:
            error_text = self.station_binding_errors.get(station_slot, "工位 LIN 配置检查未通过")
            self._set_dashboard_cell(station_slot, "result", "异常", state="error")
            self._set_dashboard_cell(station_slot, "fault", error_text, state="error")
            self.status_var.set(f"工位 {station_slot} 启动失败: {error_text}")
            if trigger == "MANUAL":
                messagebox.showwarning("启动前检查未通过", error_text)
            return
        try:
            channel_binding = self._ensure_station_channel(base_config, station_slot)
        except Exception as exc:
            error_text = str(exc)
            self._set_dashboard_cell(station_slot, "result", "异常", state="error")
            self._set_dashboard_cell(station_slot, "fault", error_text, state="error")
            self.status_var.set(f"工位 {station_slot} 启动失败: {error_text}")
            if trigger == "MANUAL":
                messagebox.showwarning("启动前检查未通过", error_text)
            return

        self.station_fault_start.pop(station_slot, None)
        self.station_fault_plc_sent.pop(station_slot, None)
        self.station_live_snapshot[station_slot] = {}
        self.station_status_history[station_slot] = []
        self._reset_dashboard_station(station_slot)
        self._set_dashboard_cell(station_slot, "phase", "等待启动", state="waiting")
        self._set_dashboard_cell(station_slot, "result", "运行中", state="running")
        self._set_dashboard_cell(station_slot, "command", f"Index={target_index}", state="waiting")
        self._set_dashboard_cell(station_slot, "summary", f"SN={target_sn}", state="waiting")
        self.station_run_meta[station_slot] = {
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sn": target_sn,
            "index": target_index,
            "name": active_row["name"].get().strip() or f"工位 {station_slot}",
        }

        self._append_run_log(f"[Station {station_slot}] 启动主程序 SN={target_sn} Index={target_index}")
        stop_event = threading.Event()
        task: InProcessRunTask | None = None

        def _emit_log(line: str) -> None:
            self.run_log_queue.put((station_slot, "line", line))

        def _worker() -> None:
            nonlocal task
            try:
                from main import RunStoppedError, SequenceRunner

                runner = SequenceRunner(
                    config,
                    station_tag="",
                    channel_binding=channel_binding,
                    stop_event=stop_event,
                    log_callback=_emit_log,
                )
                runner.run()
                exit_code = 0
            except Exception as exc:
                try:
                    from main import RunStoppedError
                except Exception:
                    RunStoppedError = None  # type: ignore[assignment]
                if RunStoppedError is not None and isinstance(exc, RunStoppedError):
                    _emit_log("[INFO] Run stopped by user.")
                    exit_code = 2
                else:
                    _emit_log(f"[ERROR] unexpected failure: {exc}")
                    exit_code = 1
            if task is not None:
                task.exit_code = exit_code
            self.run_log_queue.put((station_slot, "exit", exit_code))

        worker = threading.Thread(target=_worker, daemon=True)
        task = InProcessRunTask(station_slot, worker, stop_event)
        proc_id = id(task)
        self.run_processes[station_slot] = task
        self._process_stations[proc_id] = [station_slot]
        self._process_readers[proc_id] = worker
        task.start()

        self._update_process_status_display()
        self.run_latest_event_var.set(f"工位 {station_slot} 已启动")
        self.status_var.set(f"已启动工位 {station_slot}。")
        self._update_dashboard_button_states()
        if not self._poll_active:
            self.root.after(100, self._poll_run_log_queue)

    def save_as_template(self) -> None:
        template_name = self.template_name_var.get().strip()
        if not template_name:
            messagebox.showwarning("缺少模板名称", "请先填写模板名称。")
            return

        try:
            config = self._collect_form_data()
            template_path = save_template(self.config_path.parent, template_name, config)
        except (ConfigError, ValueError) as exc:
            messagebox.showerror("模板保存失败", str(exc))
            self.status_var.set(f"模板保存失败: {exc}")
            return

        self.refresh_templates(selected=template_path.stem)
        self.template_name_var.set(template_path.stem)
        self.status_var.set(f"模板已保存: {template_path.name}")
        messagebox.showinfo("模板保存成功", f"已保存模板: {template_path.name}")

    def load_selected_template(self) -> None:
        template_name = self.template_select_var.get().strip()
        if not template_name:
            messagebox.showwarning("未选择模板", "请先选择一个模板。")
            return

        try:
            config = validate_config(load_template(self.config_path.parent, template_name))
        except ConfigError as exc:
            messagebox.showerror("模板加载失败", str(exc))
            self.status_var.set(f"模板加载失败: {exc}")
            return

        self._apply_config_to_form(config)
        self._refresh_dashboard_headers()
        self._reset_dashboard_values()
        self.status_var.set(f"已加载模板: {template_name}")

    def rename_selected_template(self) -> None:
        old_name = self.template_select_var.get().strip()
        new_name = self.template_name_var.get().strip()
        if not old_name:
            messagebox.showwarning("未选择模板", "请先选择一个模板。")
            return
        if not new_name:
            messagebox.showwarning("缺少新名称", "请先输入模板新名称。")
            return

        try:
            new_path = rename_template(self.config_path.parent, old_name, new_name)
        except ConfigError as exc:
            messagebox.showerror("模板重命名失败", str(exc))
            self.status_var.set(f"模板重命名失败: {exc}")
            return

        self.refresh_templates(selected=new_path.stem)
        self.template_name_var.set(new_path.stem)
        self.status_var.set(f"模板已重命名为: {new_path.stem}")
        messagebox.showinfo("模板重命名成功", f"模板已重命名为: {new_path.stem}")

    def delete_selected_template(self) -> None:
        template_name = self.template_select_var.get().strip()
        if not template_name:
            messagebox.showwarning("未选择模板", "请先选择一个模板。")
            return
        if not messagebox.askyesno("确认删除", f"确定删除模板 {template_name} 吗？"):
            return

        try:
            delete_template(self.config_path.parent, template_name)
        except ConfigError as exc:
            messagebox.showerror("模板删除失败", str(exc))
            self.status_var.set(f"模板删除失败: {exc}")
            return

        self.refresh_templates()
        self.status_var.set(f"模板已删除: {template_name}")
        messagebox.showinfo("模板删除成功", f"已删除模板: {template_name}")

    def refresh_templates(self, selected: str | None = None) -> None:
        templates = list_templates(self.config_path.parent)
        self.template_combo["values"] = templates
        if selected and selected in templates:
            self.template_select_var.set(selected)
        elif self.template_select_var.get() not in templates:
            self.template_select_var.set(templates[0] if templates else "")

    def scan_lin_devices(self) -> None:
        devices = self._scan_lin_devices_internal(show_messages=True)
        self._sync_scanned_devices_to_ui(devices)

    def _scan_lin_devices_internal(self, show_messages: bool) -> List[Dict[str, Any]]:
        try:
            from lin_service import LinServiceError
        except Exception as exc:
            if show_messages:
                messagebox.showerror("扫描失败", f"无法加载 LIN 扫描模块: {exc}")
            self.status_var.set(f"扫描失败: {exc}")
            return []

        try:
            devices = self.lin_device_manager.scan_devices_once(force=True)
        except LinServiceError as exc:
            if show_messages:
                messagebox.showerror("扫描失败", str(exc))
            self.status_var.set(f"扫描失败: {exc}")
            return []
        except Exception as exc:
            if show_messages:
                messagebox.showerror("扫描失败", f"USB2XXX 扫描异常: {exc}")
            self.status_var.set(f"扫描失败: {exc}")
            return []

        if show_messages:
            if devices:
                self.status_var.set(f"扫描完成，共发现 {len(devices)} 个 USB2XXX 设备。")
            else:
                self.status_var.set("扫描完成，未发现可用 USB2XXX 设备。")
                messagebox.showwarning("扫描结果", "未发现可用 USB2XXX 设备。")
        return devices

    def use_selected_scanned_device(self) -> None:
        active_slot = int(self.active_station_var.get().strip() or "1")
        serial = self.apply_scanned_device_to_station(active_slot)
        if not serial:
            messagebox.showwarning("无法填入", "请先扫描设备并选择一个序列号。")
            return
        self.status_var.set(f"已将扫描设备填入工位 {active_slot}: {serial}")

    def apply_scanned_device_to_station(self, slot: int) -> str | None:
        selected_serial = self._get_selected_scanned_serial()
        if not selected_serial:
            return None

        row = self.station_rows[slot - 1]
        row["lin_sn"].set(selected_serial)
        row["name"].set(row["name"].get().strip() or f"工位 {slot}")
        self._refresh_dashboard_headers()
        return selected_serial

    def add_step_row(self) -> None:
        current_rows = self._snapshot_rows()
        current_rows.append(self._new_step_payload(len(current_rows) + 1))
        self._render_sequence_rows(current_rows)
        self.status_var.set("已添加新步骤，尚未保存。")

    def remove_last_step_row(self) -> None:
        if len(self.sequence_rows) <= 1:
            messagebox.showwarning("无法删除", "至少需要保留一个测试步骤。")
            return
        current_rows = self._snapshot_rows()[:-1]
        self._render_sequence_rows(current_rows)
        self.status_var.set("已删除最后一步，尚未保存。")

    def move_step_row(self, row_index: int, direction: int) -> None:
        new_index = row_index + direction
        if new_index < 0 or new_index >= len(self.sequence_rows):
            return
        current_rows = self._snapshot_rows()
        current_rows[row_index], current_rows[new_index] = current_rows[new_index], current_rows[row_index]
        self._render_sequence_rows(current_rows)
        self.status_var.set("步骤顺序已调整，尚未保存。")

    def insert_step_row(self, row_index: int) -> None:
        current_rows = self._snapshot_rows()
        current_rows.insert(row_index + 1, self._new_step_payload(len(current_rows) + 1))
        self._render_sequence_rows(current_rows)
        self.status_var.set("已插入新步骤，尚未保存。")

    def duplicate_step_row(self, row_index: int) -> None:
        current_rows = self._snapshot_rows()
        duplicated = dict(current_rows[row_index])
        duplicated["name"] = f"{duplicated['name']}_copy"
        current_rows.insert(row_index + 1, duplicated)
        self._render_sequence_rows(current_rows)
        self.status_var.set("已复制步骤，尚未保存。")

    def delete_step_row(self, row_index: int) -> None:
        if len(self.sequence_rows) <= 1:
            messagebox.showwarning("无法删除", "至少需要保留一个测试步骤。")
            return
        current_rows = self._snapshot_rows()
        del current_rows[row_index]
        self._render_sequence_rows(current_rows)
        self.status_var.set("步骤已删除，尚未保存。")

    def _collect_form_data(self) -> Dict[str, Any]:
        stations: List[Dict[str, Any]] = []
        for row in self.station_rows:
            stations.append(
                {
                    "slot": row["slot"],
                    "name": row["name"].get().strip() or f"工位 {row['slot']}",
                    "enabled": bool(row["enabled"].get()),
                    "lin_sn": row["lin_sn"].get().strip(),
                    "lin_index": int(row["lin_index"].get().strip() or "0"),
                    "scanner_ip": row["scanner_ip"].get().strip(),
                }
            )

        active_station_slot = int(self.active_station_var.get().strip() or "1")
        active_station = stations[active_station_slot - 1]
        sequence = [
            {
                "name": row["name"].get().strip(),
                "power_ratio": int(row["power_ratio"].get().strip()),
                "duration_sec": float(row["duration_sec"].get().strip()),
            }
            for row in self.sequence_rows
        ]

        return {
            "product": self.product_var.get().strip().upper() or DEFAULT_PRODUCT_CODE,
            "active_station_slot": active_station_slot,
            "device": {
                "lin_sn": active_station["lin_sn"],
                "lin_index": active_station["lin_index"],
                "baud_rate": int(self.baud_rate_var.get().strip()),
            },
            "plc": {
                "enabled": bool(self.plc_enabled_var.get()),
                "plc1_ip": self.plc1_ip_var.get().strip(),
                "plc2_ip": self.plc2_ip_var.get().strip(),
            },
            "scan": {
                "scan_start": bool(self.scan_start_var.get()),
            },
            "stations": stations,
            "timing": {
                "send_interval_ms": int(self.send_interval_var.get().strip()),
                "read_interval_ms": int(self.read_interval_var.get().strip()),
                "watchdog_sec": float(self.watchdog_var.get().strip()),
            },
            "step_plan": {
                "cooldown_duration_sec": float(self.cooldown_duration_var.get().strip()),
                "steps": sequence,
            },
            "product_profiles": deepcopy(self._product_profiles),
        }

    def _render_sequence_rows(self, sequence: List[Dict[str, Any]]) -> None:
        for child in self.sequence_container.winfo_children():
            child.destroy()

        container = self.sequence_container
        for column, header in enumerate(["步骤名", "功率%", "持续(s)", "操作"]):
            ttk.Label(container, text=header).grid(row=0, column=column, sticky=tk.W, padx=4, pady=(0, 6))
        container.columnconfigure(0, weight=1)

        self.sequence_rows = []
        for row_index, step in enumerate(sequence):
            grid_row = row_index + 1
            name_var = tk.StringVar(value=str(step["name"]))
            power_var = tk.StringVar(value=str(step["power_ratio"]))
            duration_var = tk.StringVar(value=str(step["duration_sec"]))
            ttk.Entry(container, textvariable=name_var, width=18).grid(
                row=grid_row, column=0, sticky=tk.EW, padx=4, pady=2
            )
            ttk.Entry(container, textvariable=power_var, width=5).grid(
                row=grid_row, column=1, sticky=tk.W, padx=4, pady=2
            )
            ttk.Entry(container, textvariable=duration_var, width=7).grid(
                row=grid_row, column=2, sticky=tk.W, padx=4, pady=2
            )
            button_box = ttk.Frame(container)
            button_box.grid(row=grid_row, column=3, sticky=tk.W, padx=4, pady=2)
            actions = [
                ("上移", lambda idx=row_index: self.move_step_row(idx, -1)),
                ("下移", lambda idx=row_index: self.move_step_row(idx, 1)),
                ("插入", lambda idx=row_index: self.insert_step_row(idx)),
                ("复制", lambda idx=row_index: self.duplicate_step_row(idx)),
                ("删除", lambda idx=row_index: self.delete_step_row(idx)),
            ]
            for action_index, (text, command) in enumerate(actions):
                ttk.Button(button_box, text=text, width=4, style="Compact.TButton", command=command).pack(
                    side=tk.LEFT, padx=(0 if action_index == 0 else 2, 0)
                )
            self.sequence_rows.append(
                {
                    "name": name_var,
                    "power_ratio": power_var,
                    "duration_sec": duration_var,
                }
            )

    def _apply_config_to_form(self, config: Dict[str, Any]) -> None:
        self._form_product_code = str(config.get("product", DEFAULT_PRODUCT_CODE)).strip().upper() or DEFAULT_PRODUCT_CODE
        self._product_profiles = deepcopy(config.get("product_profiles") or {})
        self.product_var.set(str(config.get("product", DEFAULT_PRODUCT_CODE)).strip().upper() or DEFAULT_PRODUCT_CODE)
        self.active_station_var.set(str(config.get("active_station_slot", 1)))
        self.baud_rate_var.set(str(config["device"]["baud_rate"]))
        self.send_interval_var.set(str(config["timing"]["send_interval_ms"]))
        self.read_interval_var.set(str(config["timing"]["read_interval_ms"]))
        self.watchdog_var.set(str(config["timing"]["watchdog_sec"]))
        self.cooldown_duration_var.set(str(config["step_plan"]["cooldown_duration_sec"]))
        self.plc_enabled_var.set(bool(config.get("plc", {}).get("enabled", False)))
        self.scan_start_var.set(bool(config.get("scan", {}).get("scan_start", False)))
        self.plc1_ip_var.set(str(config.get("plc", {}).get("plc1_ip", "192.168.8.180")))
        self.plc2_ip_var.set(str(config.get("plc", {}).get("plc2_ip", "192.168.8.181")))

        stations = config.get("stations", [])
        station_by_slot = {int(station["slot"]): station for station in stations if isinstance(station, dict)}
        for row in self.station_rows:
            station = station_by_slot.get(row["slot"], {})
            row["enabled"].set(bool(station.get("enabled", True)))
            row["name"].set(str(station.get("name", f"工位 {row['slot']}")))
            row["lin_sn"].set(str(station.get("lin_sn", "")))
            row["lin_index"].set(str(station.get("lin_index", 0)))
            row["scanner_ip"].set(str(station.get("scanner_ip", "")))

        self._render_sequence_rows(config["step_plan"]["steps"])
        self.scanned_devices = []
        self.scanned_device_combo["values"] = []
        self.scanned_device_var.set("")

    def _snapshot_rows(self) -> List[Dict[str, str]]:
        return [
            {
                "name": row["name"].get(),
                "power_ratio": row["power_ratio"].get(),
                "duration_sec": row["duration_sec"].get(),
            }
            for row in self.sequence_rows
        ]

    def _new_step_payload(self, sequence_number: int) -> Dict[str, str]:
        return {
            "name": f"Step {sequence_number}",
            "power_ratio": "10",
            "duration_sec": "10",
        }

    def _sync_scanned_devices_to_ui(self, devices: List[Dict[str, Any]]) -> None:
        self.scanned_devices = devices
        labels = [self._format_scanned_device(device) for device in devices]
        self.scanned_device_combo["values"] = labels
        if not labels:
            self.scanned_device_var.set("")
            return

        active_slot = int(self.active_station_var.get().strip() or "1")
        active_serial = self.station_rows[active_slot - 1]["lin_sn"].get().strip()
        for index, device in enumerate(devices):
            if str(device["serial"]) == active_serial:
                self.scanned_device_var.set(labels[index])
                return
        self.scanned_device_var.set(labels[0])

    def _format_scanned_device(self, device: Dict[str, Any]) -> str:
        return f"设备{int(device['scan_index']) + 1} | SN={device['serial']}"

    def _get_selected_scanned_index(self) -> int | None:
        current_value = self.scanned_device_var.get().strip()
        values = list(self.scanned_device_combo["values"])
        if not current_value or current_value not in values:
            return None
        return values.index(current_value)

    def _on_scanned_device_selected(self, _event=None) -> None:
        selected_serial = self._get_selected_scanned_serial()
        if selected_serial:
            self.status_var.set(f"已选中扫描设备: {selected_serial}")

    def _on_scanned_device_var_changed(self, *_args) -> None:
        selected_serial = self._get_selected_scanned_serial()
        if selected_serial:
            self.status_var.set(f"已选中扫描设备: {selected_serial}")

    def _on_active_station_changed(self, *_args) -> None:
        self._refresh_dashboard_headers()

    def _get_selected_scanned_serial(self) -> str | None:
        selected_index = self._get_selected_scanned_index()
        if selected_index is None:
            return None
        return str(self.scanned_devices[selected_index]["serial"])

    def _refresh_dashboard_headers(self) -> None:
        for row in self.station_rows:
            slot = row["slot"]
            name = row["name"].get().strip() or f"工位 {slot}"
            serial = row["lin_sn"].get().strip() or "未配置"
            marker = "运行" if str(slot) == self.active_station_var.get().strip() else "待机"
            if not row["enabled"].get():
                marker = "禁用"
            short = self._short_serial(serial)
            self.dashboard_header_vars[slot].set(f"{name}\n{marker}\n{short}")


    def _reset_dashboard_values(self) -> None:
        for slot in range(1, STATION_COUNT + 1):
            self._reset_dashboard_station(slot)

    def _sync_dashboard_loaded_bindings(self) -> None:
        for row in self.station_rows:
            slot = int(row["slot"])
            enabled = bool(row["enabled"].get())
            serial = row["lin_sn"].get().strip()
            lin_index = row["lin_index"].get().strip() or "0"
            if not enabled:
                self._set_dashboard_cell(slot, "phase", "未启用", state="disabled")
                self._set_dashboard_cell(slot, "result", "禁用", state="disabled")
                continue

            if slot in self.station_binding_errors:
                self._set_dashboard_cell(slot, "phase", "加载失败", state="error")
                self._set_dashboard_cell(slot, "command", f"Index={lin_index}", state="error")
                self._set_dashboard_cell(slot, "summary", f"SN={serial or '未配置'}", state="error")
                self._set_dashboard_cell(slot, "result", "异常", state="error")
                self._set_dashboard_cell(slot, "fault", self.station_binding_errors[slot], state="error")
                continue

            if enabled and serial and slot in self.station_runtime_bindings:
                binding = self.station_runtime_bindings[slot]
                initialized = self.lin_device_manager.is_channel_initialized(
                    binding["lin_sn"],
                    binding["lin_index"],
                    binding["baud_rate"],
                )
                state_key = "ready" if initialized else "idle"
                self._set_dashboard_cell(slot, "phase", "已连接" if initialized else "待连接", state=state_key)
                self._set_dashboard_cell(slot, "command", f"Index={lin_index}", state=state_key)
                self._set_dashboard_cell(slot, "result", "就绪" if initialized else "未连接", state=state_key)
                existing_qr = self.scan_results_by_station.get(slot, "")
                if existing_qr:
                    self._set_dashboard_cell(slot, "scan_result", existing_qr, state="ready")
            elif enabled and serial:
                self._set_dashboard_cell(slot, "phase", "待连接", state="idle")
                self._set_dashboard_cell(slot, "command", f"Index={lin_index}", state="idle")
                self._set_dashboard_cell(slot, "result", "未连接", state="idle")
            elif enabled:
                self._set_dashboard_cell(slot, "phase", "待配置", state="waiting")
                self._set_dashboard_cell(slot, "result", "未配置", state="waiting")

    def _reset_dashboard_station(self, slot: int) -> None:
        for row_key, _ in DASHBOARD_ROWS:
            self.dashboard_cell_vars[row_key][slot].set("")
            self.dashboard_cell_details.pop((row_key, slot), None)
            widget = self.dashboard_cell_widgets.get(row_key, {}).get(slot)
            if widget is not None:
                widget.config(bg=DASHBOARD_COLORS["blank"], fg="#111827")

    def _set_dashboard_cell(
        self,
        slot: int,
        row_key: str,
        value: str,
        state: str | None = None,
        detail: str | None = None,
    ) -> None:
        display = self._dashboard_display_text(value)
        if detail is None and display.replace("\n", "") != value:
            detail = value
        self.dashboard_cell_details[(row_key, slot)] = detail or ""
        if row_key in self.dashboard_cell_vars and slot in self.dashboard_cell_vars[row_key]:
            self.dashboard_cell_vars[row_key][slot].set(display)
        widget = self.dashboard_cell_widgets.get(row_key, {}).get(slot)
        if widget is not None:
            widget.config(bg=self._dashboard_color_for_state(state, value), fg="#111827", justify=tk.CENTER)

    def _dashboard_display_text(self, value: str) -> str:
        limit = self.dashboard_text_limit
        text = value if len(value) <= limit else value[: limit - 1] + "…"
        if len(text) > 14:
            # "fault/0x4:..." or "normal/no_fault": put the detail on its own line.
            text = re.sub(r"^([A-Za-z_]+)/", "\\1/\n", text)
        return text

    def _has_running_station_tasks(self) -> bool:
        for task in self.run_processes.values():
            if task.poll() is None:
                return True
        return False

    def _open_run_window(self) -> None:
        if self.notebook is not None and self.run_log_tab is not None:
            self.notebook.select(self.run_log_tab)

    def _build_run_log_tab(self, parent: ttk.Frame) -> None:
        container = ttk.Frame(parent, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        status_frame = ttk.Frame(container)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(status_frame, text="进程状态").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Label(status_frame, textvariable=self.run_process_status_var).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(status_frame, text="最新事件").grid(row=1, column=0, sticky=tk.NW, padx=(0, 8), pady=(8, 0))
        latest_event_label = ttk.Label(
            status_frame,
            textvariable=self.run_latest_event_var,
            justify=tk.LEFT,
        )
        latest_event_label.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))
        status_frame.columnconfigure(1, weight=1)
        bind_wraplength(latest_event_label, status_frame, margin=90)

        card_frame = ttk.LabelFrame(container, text="运行状态卡片", padding=10)
        card_frame.pack(fill=tk.X, pady=(0, 10))
        card_fields = [
            ("当前步骤", self.run_current_step_var),
            ("当前命令", self.run_command_var),
            ("运行状态", self.run_state_var),
            ("故障状态", self.run_fault_var),
            ("左功率", self.run_left_power_var),
            ("右功率", self.run_right_power_var),
            ("高压", self.run_hv_var),
            ("左温度", self.run_left_temp_var),
            ("右温度", self.run_right_temp_var),
            (self.pcb_temp_label_var, self.run_pcb_temp_var),
        ]
        for index, (label_text, value_var) in enumerate(card_fields):
            row = index // 5
            column = (index % 5) * 2
            label_options = {"textvariable": label_text} if isinstance(label_text, tk.StringVar) else {"text": label_text}
            ttk.Label(card_frame, **label_options).grid(row=row, column=column, sticky=tk.NW, padx=(0, 8), pady=4)
            # Values wrap inside their column so a long fault text cannot push the row off screen.
            value_label = ttk.Label(card_frame, textvariable=value_var, wraplength=160, justify=tk.LEFT, anchor=tk.NW)
            value_label.grid(row=row, column=column + 1, sticky=tk.NSEW, padx=(0, 16), pady=4)
            self._bind_cell_wraplength(value_label)
        for column in range(1, 10, 2):
            card_frame.columnconfigure(column, weight=1, uniform="card_value")
        ttk.Label(card_frame, text="最新汇总").grid(row=2, column=0, sticky=tk.NW, padx=(0, 8), pady=(8, 0))
        summary_label = ttk.Label(
            card_frame,
            textvariable=self.run_summary_var,
            justify=tk.LEFT,
        )
        summary_label.grid(row=2, column=1, columnspan=9, sticky=tk.W, pady=(8, 0))
        bind_wraplength(summary_label, card_frame, margin=110)

        summary_frame = ttk.LabelFrame(container, text="步骤汇总表", padding=10)
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        columns = (
            "station",
            "step",
            "name",
            "power_ratio",
            "max_left",
            "max_right",
            "end_left",
            "end_right",
            "end_run",
            "end_hv",
        )
        self.run_summary_tree = ttk.Treeview(
            summary_frame, columns=columns, show="headings", height=4 if self.compact_layout else 6
        )
        headers = {
            "station": "工位",
            "step": "步骤",
            "name": "名称",
            "power_ratio": "功率比",
            "max_left": "左峰值",
            "max_right": "右峰值",
            "end_left": "左末值",
            "end_right": "右末值",
            "end_run": "末状态",
            "end_hv": "末高压",
        }
        widths = {
            "station": 50,
            "step": 60,
            "name": 150,
            "power_ratio": 80,
            "max_left": 80,
            "max_right": 80,
            "end_left": 80,
            "end_right": 80,
            "end_run": 80,
            "end_hv": 80,
        }
        for column in columns:
            self.run_summary_tree.heading(column, text=headers[column])
            self.run_summary_tree.column(
                column, width=widths[column], minwidth=40, anchor=tk.CENTER, stretch=column == "name"
            )
        self._grid_with_scrollbars(summary_frame, self.run_summary_tree)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(button_frame, text="停止运行", command=self.stop_run_process).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="清空日志", command=self.clear_run_log).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_frame, text="返回看板", command=self._handle_run_window_close).pack(side=tk.RIGHT)

        log_frame = ttk.LabelFrame(container, text="原始日志", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.run_log_text = tk.Text(log_frame, wrap=tk.NONE, font=("Consolas", 10), height=8)
        self._grid_with_scrollbars(log_frame, self.run_log_text)

    @staticmethod
    def _grid_with_scrollbars(frame: tk.Misc, widget: tk.Widget) -> None:
        """Place *widget* in *frame* with vertical and horizontal scrollbars."""
        y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=widget.yview)
        x_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=widget.xview)
        widget.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        widget.grid(row=0, column=0, sticky=tk.NSEW)
        y_scroll.grid(row=0, column=1, sticky=tk.NS)
        x_scroll.grid(row=1, column=0, sticky=tk.EW)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _build_query_tab(self, parent: ttk.Frame) -> None:
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(top_frame, text="查询全部工位", command=self.query_all_stations).pack(side=tk.LEFT)
        ttk.Button(top_frame, text="查询当前工位", command=self.query_active_station).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_frame, text="清空查询结果", command=self.clear_query_results).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_frame, text="导出测试记录", command=self.export_query_records).pack(side=tk.RIGHT)

        info_frame = ttk.LabelFrame(parent, text="查询说明", padding=8)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        info_label = ttk.Label(
            info_frame,
            text="全量查询会逐个读取所有已预加载工位的当前状态，不启动测试流程，只做状态读取。",
            justify=tk.LEFT,
        )
        info_label.pack(anchor=tk.W)
        bind_wraplength(info_label, info_frame)

        # Packed before the expanding tables so it is never squeezed off the bottom.
        filter_frame = ttk.LabelFrame(parent, text="筛选记录", padding=8)
        filter_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        result_frame = ttk.LabelFrame(parent, text="全量查询结果", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True)
        columns = (
            "station",
            "name",
            "sn",
            "index",
            "run_state",
            "fault",
            "left_power",
            "right_power",
            "hv",
            "left_temp",
            "right_temp",
            "pcb_temp",
            "query_time",
        )
        self.query_tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=6)
        headers = {
            "station": "工位",
            "name": "名称",
            "sn": "SN",
            "index": "Index",
            "run_state": "运行状态",
            "fault": "故障状态",
            "left_power": "左功率",
            "right_power": "右功率",
            "hv": "高压",
            "left_temp": "左温度",
            "right_temp": "右温度",
            "pcb_temp": "PCB温度",
            "query_time": "查询时间",
        }
        widths = {
            "station": 60,
            "name": 90,
            "sn": 240,
            "index": 60,
            "run_state": 90,
            "fault": 220,
            "left_power": 80,
            "right_power": 80,
            "hv": 80,
            "left_temp": 80,
            "right_temp": 80,
            "pcb_temp": 80,
            "query_time": 150,
        }
        for column in columns:
            self.query_tree.heading(column, text=headers[column])
            self.query_tree.column(
                column, width=widths[column], minwidth=40, anchor=tk.CENTER, stretch=column == "fault"
            )
        self._grid_with_scrollbars(result_frame, self.query_tree)

        record_frame = ttk.LabelFrame(parent, text="测试完成记录", padding=10)
        record_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        record_columns = (
            "station",
            "name",
            "result",
            "start_time",
            "end_time",
            "sn",
            "index",
            "scan_result",
            "run_state",
            "fault",
            "left_power",
            "right_power",
            "hv",
        )
        self.query_record_tree = ttk.Treeview(record_frame, columns=record_columns, show="headings", height=5)
        record_headers = {
            "station": "工位",
            "name": "名称",
            "result": "结果",
            "start_time": "开始时间",
            "end_time": "结束时间",
            "sn": "SN",
            "index": "Index",
            "scan_result": "二维码",
            "run_state": "运行状态",
            "fault": "故障状态",
            "left_power": "左功率",
            "right_power": "右功率",
            "hv": "高压",
        }
        record_widths = {
            "station": 60,
            "name": 80,
            "result": 70,
            "start_time": 140,
            "end_time": 140,
            "sn": 180,
            "index": 55,
            "scan_result": 160,
            "run_state": 80,
            "fault": 140,
            "left_power": 70,
            "right_power": 70,
            "hv": 70,
        }
        for column in record_columns:
            self.query_record_tree.heading(column, text=record_headers[column])
            self.query_record_tree.column(
                column, width=record_widths[column], minwidth=40, anchor=tk.CENTER, stretch=column == "fault"
            )
        self._grid_with_scrollbars(record_frame, self.query_record_tree)

        # Filter panel (frame created above so it keeps its space)
        ttk.Label(filter_frame, text="开始日期").pack(side=tk.LEFT, padx=(0, 4))
        self.filter_date_start_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.filter_date_start_var, width=12).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(filter_frame, text="结束日期").pack(side=tk.LEFT, padx=(0, 4))
        self.filter_date_end_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.filter_date_end_var, width=12).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(filter_frame, text="二维码").pack(side=tk.LEFT, padx=(0, 4))
        self.filter_qr_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.filter_qr_var, width=22).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(filter_frame, text="筛选", command=self.filter_query_records).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(filter_frame, text="显示全部", command=self._reload_completed_record_tree).pack(side=tk.LEFT)

    def _update_dashboard_button_states(self) -> None:
        running = set()
        seen: set[int] = set()
        for slot, proc in self.run_processes.items():
            if proc.poll() is None:
                pid = id(proc)
                if pid not in seen:
                    seen.add(pid)
                    for s in self._process_stations.get(pid, [slot]):
                        running.add(s)
        for slot in range(1, STATION_COUNT + 1):
            start_btn = self.dashboard_start_buttons.get(slot)
            stop_btn = self.dashboard_stop_buttons.get(slot)
            if start_btn is None or stop_btn is None:
                continue
            if slot in running:
                start_btn.configure(state=tk.DISABLED)
                stop_btn.configure(state=tk.NORMAL)
            else:
                start_btn.configure(state=tk.NORMAL)
                stop_btn.configure(state=tk.DISABLED)

    def _update_process_status_display(self) -> None:
        seen_procs: set[int] = set()
        running_slots: List[int] = []
        for slot, proc in self.run_processes.items():
            if proc.poll() is None and id(proc) not in seen_procs:
                seen_procs.add(id(proc))
                # Get all slots for this process
                for s in self._process_stations.get(id(proc), [slot]):
                    if s not in running_slots:
                        running_slots.append(s)
        if not running_slots:
            self.run_process_status_var.set("未运行")
        else:
            running_slots.sort()
            self.run_process_status_var.set(f"运行中 ({len(running_slots)}/10): 工位 {','.join(str(s) for s in running_slots)}")

    def _handle_run_window_close(self) -> None:
        if self.notebook is not None and self.dashboard_tab is not None:
            self.notebook.select(self.dashboard_tab)

    def _handle_app_close(self) -> None:
        any_running = any(p.poll() is None for p in self.run_processes.values())
        if any_running:
            if not messagebox.askyesno("退出程序", "仍有工位在测试中，是否停止所有测试并退出？"):
                return
            self.stop_run_process()
        self._stop_control_services_internal()
        self._close_station_bindings()
        self.root.destroy()

    def _toggle_fullscreen(self, _event=None) -> None:
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)

    def _exit_fullscreen(self, _event=None) -> None:
        self.is_fullscreen = False
        self.root.attributes("-fullscreen", False)

    def clear_run_log(self) -> None:
        if self.run_log_text is not None and self.run_log_text.winfo_exists():
            self.run_log_text.delete("1.0", tk.END)
        if self.run_summary_tree is not None and self.run_summary_tree.winfo_exists():
            for item_id in self.run_summary_tree.get_children():
                self.run_summary_tree.delete(item_id)
        self.run_summary_var.set("尚无汇总。")

    def clear_query_results(self) -> None:
        if self.query_tree is None or not self.query_tree.winfo_exists():
            return
        for item_id in self.query_tree.get_children():
            self.query_tree.delete(item_id)

    def export_query_records(self) -> None:
        if not self.completed_records:
            messagebox.showwarning("没有可导出的记录", "当前还没有测试完成记录。")
            return
        target_path = filedialog.asksaveasfilename(
            title="导出测试记录",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            initialfile=f"a045_test_records_{time.strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not target_path:
            return
        fieldnames = [
            "station",
            "name",
            "result",
            "start_time",
            "end_time",
            "sn",
            "index",
            "scan_result",
            "run_state",
            "fault",
            "left_power",
            "right_power",
            "hv",
        ]
        with open(target_path, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for record in self.completed_records:
                writer.writerow({key: record.get(key, "") for key in fieldnames})
        self.status_var.set(f"测试记录已导出: {target_path}")
        messagebox.showinfo("导出完成", f"测试记录已导出到:\n{target_path}")

    def query_active_station(self) -> None:
        self.query_station(int(self.active_station_var.get().strip() or "1"))

    def query_all_stations(self) -> None:
        threading.Thread(target=self._query_all_stations_worker, daemon=True).start()

    def _query_all_stations_worker(self) -> None:
        for row in self.station_rows:
            if not bool(row["enabled"].get()):
                continue
            self.query_station(int(row["slot"]), open_tab=False)
            time.sleep(0.05)

    def query_station(self, station_slot: int, open_tab: bool = True) -> None:
        if open_tab and self.notebook is not None and self.query_tab is not None:
            self.notebook.select(self.query_tab)
        try:
            config = validate_config(self._collect_form_data(), station_override=station_slot)
        except (ConfigError, ValueError) as exc:
            self.status_var.set(f"查询失败: {exc}")
            return
        threading.Thread(target=self._query_station_worker, args=(station_slot, config), daemon=True).start()

    def _query_station_worker(self, station_slot: int, config: Dict[str, Any]) -> None:
        row = self.station_rows[station_slot - 1]
        station_name = row["name"].get().strip() or f"工位 {station_slot}"
        serial = row["lin_sn"].get().strip()
        lin_index = row["lin_index"].get().strip() or "0"
        try:
            if station_slot in self.station_binding_errors:
                raise ConfigError(self.station_binding_errors[station_slot])
            binding = self._get_station_runtime_binding(config, station_slot)
            raw_status = self.lin_device_manager.read_status(
                binding["lin_sn"],
                binding["lin_index"],
                binding["baud_rate"],
                config.get("product", DEFAULT_PRODUCT_CODE),
            )
            status = adapt_status(raw_status, config.get("product", DEFAULT_PRODUCT_CODE))
            values = {
                "run_state": status.run_status_text,
                "fault": f"{status.error_level_text}/{status.error_code}",
                "left_power": f"{status.left_power_w}W",
                "right_power": f"{status.right_power_w}W",
                "hv": f"{status.hv_voltage_v}V",
                "left_temp": f"{status.left_temperature_c}C",
                "right_temp": f"{status.right_temperature_c}C",
                "pcb_temp": f"{status.pcb_igbt_temperature_c}C",
            }
        except Exception as exc:
            values = {
                "run_state": "-",
                "fault": str(exc),
                "left_power": "-",
                "right_power": "-",
                "hv": "-",
                "left_temp": "-",
                "right_temp": "-",
                "pcb_temp": "-",
            }

        self.root.after(0, lambda: self._upsert_query_row(station_slot, station_name, serial, lin_index, values))

    def _upsert_query_row(
        self,
        station_slot: int,
        station_name: str,
        serial: str,
        lin_index: str,
        values: Dict[str, str],
    ) -> None:
        if self.query_tree is None or not self.query_tree.winfo_exists():
            return
        row_values = (
            str(station_slot),
            station_name,
            serial or "未配置",
            lin_index,
            values["run_state"],
            values["fault"],
            values["left_power"],
            values["right_power"],
            values["hv"],
            values["left_temp"],
            values["right_temp"],
            values["pcb_temp"],
            time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        existing_item = None
        for item_id in self.query_tree.get_children():
            item_values = self.query_tree.item(item_id, "values")
            if item_values and item_values[0] == str(station_slot):
                existing_item = item_id
                break
        if existing_item is not None:
            self.query_tree.item(existing_item, values=row_values)
        else:
            self.query_tree.insert("", tk.END, values=row_values)

    def _write_plc_result_bg(self, plc, station_slot: int, exit_code: int, scan_ok: bool) -> None:
        try:
            if exit_code in (0, 1):
                plc.write_test_result(station_slot, "PASS" if exit_code == 0 else "FAIL")
            if scan_ok:
                plc.write_status(station_slot, "SCAN_OK", False)
        except Exception:
            pass

    def _record_completed_station_run(self, station_slot: int, result_text: str) -> None:
        meta = self.station_run_meta.pop(station_slot, {})
        snapshot = self.station_live_snapshot.pop(station_slot, {})
        status_history = list(self.station_status_history.pop(station_slot, []))
        scan_result = self.scan_results_by_station.pop(station_slot, "") or ""
        self.scan_results_by_station.pop(station_slot, None)
        record = {
            "station": str(station_slot),
            "name": meta.get("name", f"工位 {station_slot}"),
            "result": result_text,
            "start_time": meta.get("start_time", ""),
            "end_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sn": meta.get("sn", ""),
            "index": meta.get("index", ""),
            "scan_result": str(scan_result).strip(),
            "run_state": snapshot.get("run_state", "-"),
            "fault": snapshot.get("fault", "-"),
            "left_power": snapshot.get("left_power", "-"),
            "right_power": snapshot.get("right_power", "-"),
            "hv": snapshot.get("hv", "-"),
            "left_temp": snapshot.get("left_temp", "-"),
            "right_temp": snapshot.get("right_temp", "-"),
            "pcb_temp": snapshot.get("pcb_temp", "-"),
            "status_history": status_history,
        }
        self.completed_records.append(record)
        self._save_completed_records()
        self._append_completed_record_row(record)

    def _load_completed_records(self) -> None:
        if not RECORDS_FILE.exists():
            self.completed_records = []
            return
        try:
            payload = json.loads(RECORDS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            self.completed_records = []
            self.status_var.set(f"历史记录加载失败: {exc}")
            return
        if isinstance(payload, list):
            self.completed_records = [record for record in payload if isinstance(record, dict)]
        else:
            self.completed_records = []
        self._reload_completed_record_tree()

    def _save_completed_records(self) -> None:
        try:
            RECORDS_FILE.write_text(
                json.dumps(self.completed_records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self.status_var.set(f"历史记录保存失败: {exc}")

    def filter_query_records(self) -> None:
        if self.query_record_tree is None or not self.query_record_tree.winfo_exists():
            return
        date_start = self.filter_date_start_var.get().strip()
        date_end = self.filter_date_end_var.get().strip()
        qr = self.filter_qr_var.get().strip().upper()
        filtered = self.completed_records
        if date_start:
            filtered = [r for r in filtered if r.get("start_time", "")[:10] >= date_start]
        if date_end:
            filtered = [r for r in filtered if r.get("start_time", "")[:10] <= date_end]
        if qr:
            filtered = [r for r in filtered if qr in str(r.get("scan_result", "")).upper()]
        for item_id in self.query_record_tree.get_children():
            self.query_record_tree.delete(item_id)
        for record in reversed(filtered):
            self._append_completed_record_row(record)
        self.status_var.set(f"筛选结果: {len(filtered)} 条记录")

    def _reload_completed_record_tree(self) -> None:
        if self.query_record_tree is None or not self.query_record_tree.winfo_exists():
            return
        for item_id in self.query_record_tree.get_children():
            self.query_record_tree.delete(item_id)
        for record in reversed(self.completed_records):
            self._append_completed_record_row(record)

    def _append_completed_record_row(self, record: Dict[str, str]) -> None:
        if self.query_record_tree is None or not self.query_record_tree.winfo_exists():
            return
        self.query_record_tree.insert(
            "",
            0,
            values=(
                record.get("station", ""),
                record.get("name", ""),
                record.get("result", ""),
                record.get("start_time", ""),
                record.get("end_time", ""),
                record.get("sn", ""),
                record.get("index", ""),
                record.get("scan_result", ""),
                record.get("run_state", ""),
                record.get("fault", ""),
                record.get("left_power", ""),
                record.get("right_power", ""),
                record.get("hv", ""),
            ),
        )

    def stop_station_run(self, station_slot: int) -> None:
        self._stop_station_process(station_slot)

    def _stop_station_process(self, station_slot: int) -> None:
        proc = self.run_processes.get(station_slot)
        if proc is None:
            return
        proc_id = id(proc)
        if proc.poll() is not None:
            for slot in list(self._process_stations.get(proc_id, [station_slot])):
                self.run_processes.pop(slot, None)
            self._process_stations.pop(proc_id, None)
            self._process_readers.pop(proc_id, None)
            self._update_dashboard_button_states()
            self._update_process_status_display()
            return
        slots = self._process_stations.get(proc_id, [station_slot])
        slot_list = ",".join(str(s) for s in slots)
        self._append_run_log(f"[INFO] 正在停止工位 {slot_list} 测试进程...")
        self.run_latest_event_var.set(f"正在停止工位 {slot_list}...")
        proc.terminate()

    def stop_run_process(self) -> None:
        seen: set[int] = set()
        for slot, proc in list(self.run_processes.items()):
            if id(proc) not in seen:
                seen.add(id(proc))
                self._stop_station_process(slot)

    def _read_run_output_for_process(self, proc: subprocess.Popen[str], proc_id: int) -> None:
        station_slots = self._process_stations.get(proc_id, [])
        default_slot = station_slots[0] if station_slots else 0
        is_combined = len(station_slots) > 1
        try:
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\r\n")
                if is_combined:
                    match = re.match(r"^\[Station (\d+)\] (.*)", line)
                    if match:
                        parsed_slot = int(match.group(1))
                        line_content = match.group(2)
                        self.run_log_queue.put((parsed_slot, "line", line_content))
                    else:
                        self.run_log_queue.put((default_slot, "line", line))
                else:
                    self.run_log_queue.put((default_slot, "line", line))
        finally:
            exit_code = proc.wait()
            for slot in station_slots:
                self.run_log_queue.put((slot, "exit", exit_code))

    def _poll_run_log_queue(self) -> None:
        self._poll_active = True
        has_pending_events = False
        while True:
            try:
                station_slot, event_type, payload = self.run_log_queue.get_nowait()
            except queue.Empty:
                break

            has_pending_events = True
            if event_type == "line":
                line = str(payload)
                self._append_run_log(f"[Station {station_slot}] {line}")
                self._update_run_status_from_line(station_slot, line)
            elif event_type == "exit":
                exit_code = int(payload)
                self._append_run_log(f"[PROCESS_EXIT Station {station_slot}] code={exit_code}")
                self.status_var.set(f"工位 {station_slot} 已退出，code={exit_code}")
                if exit_code == 0:
                    result_text = "PASS"
                    result_state = "pass"
                elif exit_code == 2:
                    result_text = "已停止"
                    result_state = "warning"
                else:
                    result_text = "FAIL"
                    result_state = "fail"
                self._set_dashboard_cell(station_slot, "result", result_text, state=result_state)
                if self.plc_controller is not None:
                    plc = self.plc_controller
                    scan_ok = self.scan_start_var.get()
                    code = exit_code
                    threading.Thread(
                        target=lambda: self._write_plc_result_bg(plc, station_slot, code, scan_ok),
                        daemon=True,
                    ).start()
                self._record_completed_station_run(station_slot, result_text)
                self._release_station_binding(station_slot)
                self.scan_results_by_station.pop(station_slot, None)
                # Find and clean the process that owned this station
                proc = self.run_processes.pop(station_slot, None)
                if proc is not None:
                    proc_id = id(proc)
                    # Remove this station from process_stations tracking
                    remaining = self._process_stations.get(proc_id, [])
                    if station_slot in remaining:
                        remaining.remove(station_slot)
                    if not remaining:
                        self._process_stations.pop(proc_id, None)
                        self._process_readers.pop(proc_id, None)
                self._update_dashboard_button_states()
                self._update_process_status_display()

        any_running = False
        seen: set[int] = set()
        for proc in self.run_processes.values():
            if id(proc) not in seen and proc.poll() is None:
                any_running = True
                break
            seen.add(id(proc))
        if has_pending_events or any_running:
            self.root.after(100, self._poll_run_log_queue)
        else:
            self._poll_active = False
            self.run_process_status_var.set("未运行")

    def _append_run_log(self, line: str) -> None:
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self._append_run_log(line))
            return
        if self.run_log_text is None or not self.run_log_text.winfo_exists():
            return
        self.run_log_text.insert(tk.END, line + "\n")
        self.run_log_text.see(tk.END)

    def _update_run_status_from_line(self, station_slot: int, line: str) -> None:
        if line.startswith("[STEP "):
            self.run_latest_event_var.set(line)
            self._update_step_card(line)
            self._update_dashboard_from_step(station_slot, line)
        elif line.startswith("[STATUS]") or line.startswith("[TRANSITION]"):
            self.run_latest_event_var.set(line)
            self._update_status_card(line)
            self._update_dashboard_from_status(station_slot, line)
            self._snapshot_station_status_from_line(station_slot, line)
        elif line.startswith("[STEP_SUMMARY]"):
            self.run_latest_event_var.set(line)
            self.run_summary_var.set(line)
            self._update_summary_table(station_slot, line)
            self._update_dashboard_summary(station_slot, line)
        elif line.startswith("[WARN]"):
            self.run_latest_event_var.set(line)
        elif line.startswith("[ERROR]"):
            self.run_latest_event_var.set(line)
            self._set_dashboard_cell(station_slot, "result", "ERROR", state="error")
        elif line.startswith("Summary:"):
            self.run_latest_event_var.set(line)
            self.run_summary_var.set(line)
            self._set_dashboard_cell(station_slot, "summary", line)

    def _update_step_card(self, line: str) -> None:
        match = re.match(r"^\[STEP ([^\]]+)\] (.+?) \| power_ratio=(.+?) \| duration=(.+)$", line)
        if not match:
            return
        step_index, step_name, power_ratio, duration = match.groups()
        self.run_current_step_var.set(f"{step_index} {step_name}")
        self.run_command_var.set(f"{power_ratio} / {duration}")

    def _update_status_card(self, line: str) -> None:
        values = self._extract_status_fields(line)
        if "run" in values:
            self.run_state_var.set(values["run"])
        if "fault" in values:
            self.run_fault_var.set(values["fault"])
        if "left_power" in values:
            self.run_left_power_var.set(values["left_power"])
        if "right_power" in values:
            self.run_right_power_var.set(values["right_power"])
        if "hv" in values:
            self.run_hv_var.set(values["hv"])
        if "left_temp" in values:
            self.run_left_temp_var.set(values["left_temp"])
        if "right_temp" in values:
            self.run_right_temp_var.set(values["right_temp"])
        if "pcb_temp" in values:
            self.run_pcb_temp_var.set(values["pcb_temp"])

    def _extract_status_fields(self, line: str) -> Dict[str, str]:
        patterns = {
            "run": r"run=([^\s]+)",
            "fault": r"fault=([^\s]+)",
            "left_power": r"left_power=([^\s]+)",
            "right_power": r"right_power=([^\s]+)",
            "left_temp": r"left_temp=([^\s]+)",
            "right_temp": r"right_temp=([^\s]+)",
            "pcb_temp": r"pcb_temp=([^\s]+)",
            "hv": r"hv=([^\s]+)",
        }
        values: Dict[str, str] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                values[key] = match.group(1)
        return values

    def _snapshot_station_status_from_line(self, station_slot: int, line: str) -> None:
        values = self._extract_status_fields(line)
        if not values:
            return
        current_values = {
            "run_state": values.get("run", "-"),
            "fault": values.get("fault", "-"),
            "left_power": values.get("left_power", "-"),
            "right_power": values.get("right_power", "-"),
            "hv": values.get("hv", "-"),
            "left_temp": values.get("left_temp", "-"),
            "right_temp": values.get("right_temp", "-"),
            "pcb_temp": values.get("pcb_temp", "-"),
        }
        snapshot = self.station_live_snapshot.setdefault(station_slot, {})
        for key, value in current_values.items():
            if value != "-":
                snapshot[key] = value
        history = self.station_status_history.setdefault(station_slot, [])
        history_entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S")}
        history_entry.update(snapshot)
        comparable_entry = {k: v for k, v in history_entry.items() if k != "time"}
        last_entry = history[-1] if history else None
        last_comparable = {k: v for k, v in last_entry.items() if k != "time"} if last_entry else None
        if comparable_entry != last_comparable:
            history.append(history_entry)
            if len(history) > STATUS_HISTORY_LIMIT:
                del history[:-STATUS_HISTORY_LIMIT]
        meta = self.station_run_meta.get(station_slot, {})
        if meta:
            self._upsert_query_row(
                station_slot,
                meta.get("name", f"工位 {station_slot}"),
                meta.get("sn", ""),
                meta.get("index", "0"),
                snapshot,
            )

    def _update_summary_table(self, station_slot: int, line: str) -> None:
        if self.run_summary_tree is None or not self.run_summary_tree.winfo_exists():
            return

        values = self._parse_summary_line(line)
        if not values:
            return

        station_str = str(station_slot)
        row_values = (
            station_str,
            values["step"],
            values["name"],
            values["power_ratio"],
            values["max_left"],
            values["max_right"],
            values["end_left"],
            values["end_right"],
            values["end_run"],
            values["end_hv"],
        )
        existing_item = None
        for item_id in self.run_summary_tree.get_children():
            item_values = self.run_summary_tree.item(item_id, "values")
            if item_values and item_values[0] == station_str and item_values[1] == values["step"]:
                existing_item = item_id
                break
        if existing_item is not None:
            self.run_summary_tree.item(existing_item, values=row_values)
        else:
            self.run_summary_tree.insert("", tk.END, values=row_values)

    def _parse_summary_line(self, line: str) -> Dict[str, str] | None:
        a050_match = re.match(
            r"^\[STEP_SUMMARY\] "
            r"step=(?P<step>\S+) "
            r"name=(?P<name>.+?) "
            r"power_ratio=(?P<power_ratio>\S+) "
            r"max_power=(?P<max_power>\S+) "
            r"end_power=(?P<end_power>\S+) "
            r"end_hv=(?P<end_hv>\S+) "
            r"end_temp1=(?P<end_temp1>\S+) "
            r"end_temp2=(?P<end_temp2>\S+)$",
            line,
        )
        if a050_match:
            values = a050_match.groupdict()
            return {
                "step": values["step"],
                "name": values["name"],
                "power_ratio": values["power_ratio"],
                "max_left": values["max_power"],
                "max_right": values["max_power"],
                "end_left": values["end_power"],
                "end_right": values["end_power"],
                "end_run": "normal_operation",
                "end_hv": values["end_hv"],
            }

        pattern = re.compile(
            r"^\[STEP_SUMMARY\] "
            r"step=(?P<step>\S+) "
            r"name=(?P<name>.+?) "
            r"power_ratio=(?P<power_ratio>\S+)"
            r"(?: max_left=(?P<max_left>\S+) max_right=(?P<max_right>\S+) "
            r"end_left=(?P<end_left>\S+) end_right=(?P<end_right>\S+) "
            r"end_run=(?P<end_run>\S+) end_hv=(?P<end_hv>\S+).*)?"
            r"(?: result=(?P<result>\S+))?$"
        )
        match = pattern.match(line)
        if not match:
            return None

        values = match.groupdict()
        return {
            "step": values.get("step", "-"),
            "name": values.get("name", "-"),
            "power_ratio": values.get("power_ratio", "-"),
            "max_left": values.get("max_left") or values.get("result") or "-",
            "max_right": values.get("max_right") or "-",
            "end_left": values.get("end_left") or "-",
            "end_right": values.get("end_right") or "-",
            "end_run": values.get("end_run") or "-",
            "end_hv": values.get("end_hv") or "-",
        }

    def _update_dashboard_from_step(self, station_slot: int, line: str) -> None:
        match = re.match(r"^\[STEP ([^\]]+)\] (.+?) \| power_ratio=(.+?) \| duration=(.+)$", line)
        if not match:
            return
        step_index, step_name, power_ratio, duration = match.groups()
        self._set_dashboard_cell(station_slot, "phase", f"{step_index} {step_name}", state="running")
        self._set_dashboard_cell(station_slot, "command", f"{power_ratio} / {duration}", state="running")
        self._set_dashboard_cell(station_slot, "result", "运行中", state="running")

    def _update_dashboard_from_status(self, station_slot: int, line: str) -> None:
        values = self._extract_status_fields(line)
        mapping = {
            "run": "run_state",
            "fault": "fault",
            "left_power": "left_power",
            "right_power": "right_power",
            "hv": "hv",
            "left_temp": "left_temp",
            "right_temp": "right_temp",
            "pcb_temp": "pcb_temp",
        }
        for source_key, row_key in mapping.items():
            if source_key in values:
                val = values[source_key]
                if source_key == "run" and any(
                    marker in val.lower() for marker in ("fault", "degraded", "error")
                ):
                    self._set_dashboard_cell(station_slot, row_key, val, state="error")
                    self._check_fault_timeout(station_slot)
                elif source_key == "run":
                    self.station_fault_start.pop(station_slot, None)
                    self.station_fault_plc_sent.pop(station_slot, None)
                    self._set_dashboard_cell(station_slot, row_key, val)
                elif source_key == "fault":
                    if val in ("normal/no_fault", "normal/0x0", "normal", ""):
                        self._set_dashboard_cell(station_slot, row_key, val, state="ready")
                    else:
                        self._set_dashboard_cell(station_slot, row_key, val, state="error")
                else:
                    self._set_dashboard_cell(station_slot, row_key, val)

    def _check_fault_timeout(self, station_slot: int) -> None:
        now = time.time()
        if station_slot not in self.station_fault_start:
            self.station_fault_start[station_slot] = now
            return
        if now - self.station_fault_start[station_slot] > 10:
            if not self.station_fault_plc_sent.get(station_slot):
                if self.plc_controller is not None:
                    threading.Thread(
                        target=lambda: self._write_fault_to_plc(station_slot),
                        daemon=True,
                    ).start()
                self.station_fault_plc_sent[station_slot] = True

    def _write_fault_to_plc(self, station_slot: int) -> None:
        try:
            self.plc_controller.write_status(station_slot, "FAIL", True)
            self._append_run_log(f"[FAULT] 工位 {station_slot} 故障超10s，已发 FAIL 信号到 PLC")
        except Exception:
            pass

    def _update_dashboard_summary(self, station_slot: int, line: str) -> None:
        summary = self._parse_summary_line(line)
        if not summary:
            return
        compact = f"第{summary['step']}步 {summary['end_left']}/{summary['end_right']} {summary['end_hv']}"
        self._set_dashboard_cell(station_slot, "summary", compact, state="blank", detail=line)
        self._set_dashboard_cell(station_slot, "result", summary["end_run"], state="blank")


def main() -> int:
    root = tk.Tk()
    config_path = Path(__file__).resolve().parent / CONFIG_FILE
    SettingsApp(root, config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
