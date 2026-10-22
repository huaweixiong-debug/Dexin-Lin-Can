import tkinter as tk
from tkinter import ttk
import calendar
from datetime import datetime

class DatePickerDialog(tk.Toplevel):
    def __init__(self, parent, initial_date=None, title="选择日期时间"):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.parent = parent
        
        if initial_date:
            if isinstance(initial_date, str):
                try:
                    self.current_date = datetime.strptime(initial_date, "%Y-%m-%d %H:%M:%S")
                except:
                    self.current_date = datetime.now()
            else:
                self.current_date = initial_date
        else:
            self.current_date = datetime.now()
            
        # Year and Month
        self.year = tk.IntVar(value=self.current_date.year)
        self.month = tk.IntVar(value=self.current_date.month)
        self.day = tk.IntVar(value=self.current_date.day)
        
        # Time
        self.hour = tk.IntVar(value=self.current_date.hour)
        self.minute = tk.IntVar(value=self.current_date.minute)
        self.second = tk.IntVar(value=self.current_date.second)
        
        self.setup_ui()
        
        # Modal setup
        self.transient(parent)
        self.grab_set()
        
        # Center relative to parent
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")
        
        self.wait_window(self)

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # --- Header: Year/Month Navigation ---
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(header_frame, text="<<", width=3, command=self.prev_year).pack(side="left")
        ttk.Button(header_frame, text="<", width=3, command=self.prev_month).pack(side="left")
        
        self.lbl_header = ttk.Label(header_frame, text="", font=("Arial", 10, "bold"), anchor="center")
        self.lbl_header.pack(side="left", fill="x", expand=True)
        
        ttk.Button(header_frame, text=">", width=3, command=self.next_month).pack(side="left")
        ttk.Button(header_frame, text=">>", width=3, command=self.next_year).pack(side="left")
        
        # --- Calendar Grid ---
        self.cal_frame = ttk.Frame(main_frame)
        self.cal_frame.pack(fill="both", expand=True)
        
        days = ["一", "二", "三", "四", "五", "六", "日"]
        for i, day in enumerate(days):
            ttk.Label(self.cal_frame, text=day, anchor="center", width=4).grid(row=0, column=i, sticky="nsew")
            
        self.day_buttons = []
        for r in range(6):
            row_btns = []
            for c in range(7):
                btn = tk.Button(self.cal_frame, text="", width=4, relief="flat", 
                                command=lambda r=r, c=c: self.on_day_click(r, c))
                btn.grid(row=r+1, column=c, sticky="nsew", padx=1, pady=1)
                row_btns.append(btn)
            self.day_buttons.append(row_btns)
            
        self.refresh_calendar()
        
        # --- Time Selection ---
        time_frame = ttk.LabelFrame(main_frame, text="时间 (时:分:秒)", padding="5")
        time_frame.pack(fill="x", pady=10)
        
        ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self.hour, width=3, format="%02.0f").pack(side="left", padx=2)
        ttk.Label(time_frame, text=":").pack(side="left")
        ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.minute, width=3, format="%02.0f").pack(side="left", padx=2)
        ttk.Label(time_frame, text=":").pack(side="left")
        ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.second, width=3, format="%02.0f").pack(side="left", padx=2)
        
        # --- Buttons ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(btn_frame, text="确定", command=self.on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right")
        
    def refresh_calendar(self):
        y = self.year.get()
        m = self.month.get()
        d = self.day.get()
        
        self.lbl_header.config(text=f"{y}年 {m}月")
        
        cal = calendar.monthcalendar(y, m)
        
        self.date_map = {} # (row, col) -> day
        
        for r in range(6):
            for c in range(7):
                btn = self.day_buttons[r][c]
                if r < len(cal):
                    day_num = cal[r][c]
                else:
                    day_num = 0
                    
                if day_num == 0:
                    btn.config(text="", state="disabled", bg="#f0f0f0")
                else:
                    btn.config(text=str(day_num), state="normal")
                    self.date_map[(r, c)] = day_num
                    if day_num == d:
                        btn.config(bg="#ADD8E6") # Selected
                    else:
                        btn.config(bg="white")
                        
    def on_day_click(self, r, c):
        if (r, c) in self.date_map:
            day = self.date_map[(r, c)]
            self.day.set(day)
            self.refresh_calendar()
            
    def prev_month(self):
        m = self.month.get()
        y = self.year.get()
        m -= 1
        if m < 1:
            m = 12
            y -= 1
        self.month.set(m)
        self.year.set(y)
        self.adjust_day()
        self.refresh_calendar()
        
    def next_month(self):
        m = self.month.get()
        y = self.year.get()
        m += 1
        if m > 12:
            m = 1
            y += 1
        self.month.set(m)
        self.year.set(y)
        self.adjust_day()
        self.refresh_calendar()
        
    def prev_year(self):
        self.year.set(self.year.get() - 1)
        self.adjust_day()
        self.refresh_calendar()
        
    def next_year(self):
        self.year.set(self.year.get() + 1)
        self.adjust_day()
        self.refresh_calendar()
        
    def adjust_day(self):
        # Ensure day is valid for new month
        _, max_days = calendar.monthrange(self.year.get(), self.month.get())
        if self.day.get() > max_days:
            self.day.set(max_days)

    def on_ok(self):
        try:
            # Get values safely
            try:
                h = self.hour.get()
                m = self.minute.get()
                s = self.second.get()
            except tk.TclError:
                # Handle empty or invalid spinbox values
                h, m, s = 0, 0, 0
                print("Warning: Invalid time values, defaulting to 00:00:00")

            dt = datetime(
                self.year.get(), self.month.get(), self.day.get(),
                h, m, s
            )
            self.result = dt.strftime("%Y-%m-%d %H:%M:%S")
            print(f"DEBUG: Selected datetime: {self.result}")
            self.destroy()
        except Exception as e:
            print(f"Error in on_ok: {e}")
            # Don't destroy if error, let user retry? Or destroy?
            # Better to show error
            tk.messagebox.showerror("错误", "无效的日期或时间")

def ask_datetime(parent, initial_value=None):
    dlg = DatePickerDialog(parent, initial_value)
    # DatePickerDialog已经在初始化时显示并等待用户操作
    # 不需要调用show()方法
    return dlg.result
