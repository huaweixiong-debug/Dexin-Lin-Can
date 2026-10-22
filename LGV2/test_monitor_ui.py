import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import sys
import time
import datetime
import database
from manual_test_controller import ManualTestController
from loading_view import LoadingWindow

# 添加USB2CAN目录到Python搜索路径
usb2can_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'USB2CAN')
sys.path.append(usb2can_dir)

# 导入USB设备相关模块
USB2XXXLib_available = False

# 导入必要的模块
from ctypes import *
import os
import platform

# 在导入USB设备模块之前，先设置PATH环境变量
print("=== 在导入USB设备模块之前设置PATH环境变量 ===")
print(f"USB2CAN目录: {usb2can_dir}")

if os.path.exists(usb2can_dir):
    os.environ['PATH'] = usb2can_dir + ';' + os.environ['PATH']
    print(f"已添加USB2CAN目录到系统PATH")
    
    # 添加USB2CAN/libs/windows/x86_64或x86目录到系统路径
    windows_libs_dir = os.path.join(usb2can_dir, 'libs', 'windows')
    if os.path.exists(windows_libs_dir):
        print(f"Windows库目录: {windows_libs_dir}")
        
        # 尝试64位DLL
        x86_64_dir = os.path.join(windows_libs_dir, 'x86_64')
        if os.path.exists(x86_64_dir):
            os.environ['PATH'] = x86_64_dir + ';' + os.environ['PATH']
            print(f"已添加64位DLL目录到系统PATH: {x86_64_dir}")
        
        # 尝试32位DLL
        x86_dir = os.path.join(windows_libs_dir, 'x86')
        if os.path.exists(x86_dir):
            os.environ['PATH'] = x86_dir + ';' + os.environ['PATH']
            print(f"已添加32位DLL目录到系统PATH: {x86_dir}")

# 检查Python架构
python_arch = platform.architecture()[0]
print(f"Python架构: {python_arch}")

# 尝试导入USB设备相关模块
usb_device_available = False
try:
    from usb_device import *
    from usb2can import *
    usb_device_available = True
    print("成功在模块级别导入USB设备相关模块")
except ImportError as e:
    print(f"在模块级别导入USB设备相关模块错误: {e}")
    usb_device_available = False

# 初始化USB设备模块
def init_usb_device_module():
    """初始化USB设备模块，确保libusb-1.0.dll和USB2XXX.dll文件能正确加载"""
    global USB2XXXLib_available
    
    print("=== 开始初始化USB设备模块 ===")
    
    try:
        # 检查USB设备相关模块是否可用
        global usb_device_available
        if usb_device_available:
            print("USB设备相关模块已在模块级别成功导入")
        else:
            print("USB设备相关模块在模块级别导入失败，无法在函数内部重试导入")
        
        USB2XXXLib_available = usb_device_available
        if USB2XXXLib_available:
            print("USB设备模块初始化成功")
        else:
            print("USB设备模块初始化失败")
    except ImportError as e:
        print(f"导入USB设备模块错误: {e}")
        import traceback
        traceback.print_exc()
        USB2XXXLib_available = False
    except Exception as e:
        print(f"初始化USB设备模块错误: {e}")
        import traceback
        traceback.print_exc()
        USB2XXXLib_available = False
    finally:
        print(f"=== USB设备模块初始化完成，状态: {USB2XXXLib_available} ===")
        return USB2XXXLib_available

# 检查设备驱动

def check_device_driver():
    """检查USB设备驱动是否正确安装
    
    Returns:
        bool: 驱动是否正确安装
    """
    print("=== 开始检查设备驱动 ===")
    
    try:
        # 检查操作系统类型
        if platform.system() != "Windows":
            print("当前操作系统不是Windows，跳过驱动检查")
            return True
        
        # 检查USB2XXX.dll文件是否存在
        usb2can_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'USB2CAN')
        usb2xxx_path = os.path.join(usb2can_dir, 'USB2XXX.dll')
        
        if os.path.exists(usb2xxx_path):
            print(f"USB2XXX.dll文件存在: {usb2xxx_path}")
        else:
            print(f"USB2XXX.dll文件不存在: {usb2xxx_path}")
            return False
        
        # 检查libusb-1.0.dll文件是否存在
        libusb_path = os.path.join(usb2can_dir, 'libusb-1.0.dll')
        
        if os.path.exists(libusb_path):
            print(f"libusb-1.0.dll文件存在: {libusb_path}")
        else:
            print(f"libusb-1.0.dll文件不存在: {libusb_path}")
            return False
        
        # 尝试加载DLL文件，检查驱动是否正确安装
        try:
            # 尝试加载libusb-1.0.dll
            print("尝试加载libusb-1.0.dll，检查驱动是否正确安装...")
            cdll.LoadLibrary(libusb_path)
            print("成功加载libusb-1.0.dll，驱动安装正确")
            
            # 尝试加载USB2XXX.dll
            print("尝试加载USB2XXX.dll，检查驱动是否正确安装...")
            cdll.LoadLibrary(usb2xxx_path)
            print("成功加载USB2XXX.dll，驱动安装正确")
            
            return True
        except Exception as e:
            print(f"加载DLL文件错误，驱动可能未正确安装: {e}")
            return False
    except Exception as e:
        print(f"检查设备驱动错误: {e}")
        return False
    finally:
        print("=== 设备驱动检查完成 ===")

# 初始化USB设备模块
init_usb_device_module()

class TestMonitorUI:
    def __init__(self, root):
        self.root = root
        self.root.title("德鑫指控低压PTC综测老化设备")
        # Set to zoomed state (maximized) to fit screen and respect taskbar
        self.root.state('zoomed')
        
        # Set Icon
        try:
            if os.path.exists("win11_logo.ico"):
                self.root.iconbitmap("win11_logo.ico")
        except Exception as e:
            print(f"Failed to set icon: {e}")

        # Configure global grid weights
        # Row 0: Notebook (Main content) - Weight 2 (Expand)
        # Row 1: Log Area - Weight 1 (More visible)
        self.root.grid_rowconfigure(0, weight=2)
        self.root.grid_rowconfigure(1, weight=1, minsize=200)  # Minimum height 200px
        self.root.grid_columnconfigure(0, weight=1)
        
        # Storage for status cells: (station_idx, item_idx) -> Label widget
        self.status_cells = {}
        
        # Callbacks
        self.start_callback = None
        self.stop_callback = None
        self.calibration_start_callback = None
        self.calibration_stop_callback = None

        # Load config
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            self.config_file = os.path.join(base_dir, "config.json")
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            print(f"DEBUG: __file__={__file__}")
            print(f"DEBUG: abspath={os.path.abspath(__file__)}")
            print(f"DEBUG: base_dir={base_dir}")
            self.config_file = os.path.join(base_dir, "config.json")
            print(f"DEBUG: config_file={self.config_file}")
            
        self.load_config()

        # Current User State
        self.current_user = None # None means logged out
        self.current_role = None

        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # --- Tab 1: Test Page ---
        self.test_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.test_frame, text='测试页面')
        
        # --- Tab 2: Settings Page ---
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text='设置页面')
        
        # --- Tab 3: Query Page ---
        self.items_data = [
             (0, "等待", "准备就绪"), 
             (1, "实际电压", "Waiting..."), 
             (2, "实际电流", "Waiting..."), 
             (3, "100%功率", "Waiting..."), 
             (4, "100%功率反馈电压", "Waiting..."), 
             (5, "100%功率反馈电流", "Waiting..."), 
             (6, "0%功率", "Waiting..."), 
             (7, "80%功率", "Waiting..."), 
             (8, "80%功率反馈电压", "Waiting..."), 
             (9, "80%功率反馈电流", "Waiting..."), 
             (10, "0%功率", "Waiting..."), 
             (11, "60%功率", "Waiting..."), 
             (12, "60%功率反馈电压", "Waiting..."), 
             (13, "60%功率反馈电流", "Waiting..."), 
             (14, "0%功率", "Waiting..."), 
             (15, "40%功率", "Waiting..."), 
             (16, "40%功率反馈电压", "Waiting..."), 
             (17, "40%功率反馈电流", "Waiting..."), 
             (18, "0%功率", "Waiting..."), 
             (19, "PTC温度", "Waiting..."), 
             (20, "实际功率", "Waiting..."), 
             (21, "测试倒计时", "Waiting..."), 
             (22, "故障状态", "Waiting..."), 
             (23, "温度", "Waiting...")
        ]

        # --- Tab 3: Query Page ---
        self.query_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.query_frame, text='查询页面')
        
        # --- Tab 4: Data Visualization Page ---
        self.visualization_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.visualization_frame, text='数据可视化')
        
        # --- Log Area (Bottom) ---
        self.create_log_ui()

        # Define columns headers
        self.headers = ["序号", "项目"] + [f"测试 {i}" for i in range(1, 11)]
        
        # Build the UIs
        self.create_grid_ui()
        self.create_settings_ui()
        
        # Create Query UI last because it depends on items_data which is defined above but create_query_ui was moved to bottom class definition
        self.create_query_ui()
        
        # Create Data Visualization UI
        self.create_visualization_ui()
        
        # Create Log UI
        self.create_log_ui()
    
    def create_log_ui(self):
        """Create a scrolled text area for logging at the bottom"""
        self.log_frame = ttk.LabelFrame(self.root, text="系统日志 (System Log)")
        self.log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame, state='disabled', height=10)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
    def on_tab_changed(self, event):
        """Handle tab switching events"""
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")
        
        if tab_text in ["查询页面", "设置页面", "电压校准", "手动诊断"]:
            self.log_frame.grid_remove() # Hide log frame
            # Give all space to the notebook and remove minimum size constraint
            self.root.grid_rowconfigure(0, weight=1)
            self.root.grid_rowconfigure(1, weight=0, minsize=0) 

            # Update End Time to Now when entering Query Page
            if tab_text == "查询页面":
                try:
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Check if widget exists
                    if hasattr(self, 'entry_end_time'):
                        self.entry_end_time.delete(0, tk.END)
                        self.entry_end_time.insert(0, now_str)
                except Exception as e:
                    print(f"Error auto-updating end time: {e}")
        else:
            self.log_frame.grid() # Show log frame
            # Restore weights
            self.root.grid_rowconfigure(0, weight=3)
            self.root.grid_rowconfigure(1, weight=1)

    def log_message(self, message):
        """Append message to the log area with timestamp"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, full_msg)
        self.log_text.see(tk.END) # Auto scroll to end
        self.log_text.config(state='disabled')

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print(f"Config loaded successfully from {self.config_file}")
            except Exception as e:
                print(f"Error loading config: {e}")
                self.config = {"products": [], "hardware_settings": {}}
        else:
            self.config = {"products": [], "hardware_settings": {}}

    def save_config(self, progress_title="保存配置", show_message=True):
        loader = None
        try:
            # Create Loading Window
            loader = LoadingWindow(self.root, title=progress_title, start_message="正在初始化...")
            loader.update_progress(5, "正在准备保存...")
            time.sleep(0.1)

            # 确保配置字典中有必要的键
            if "hardware_settings" not in self.config:
                self.config["hardware_settings"] = {}
            if "wind_speed_settings" not in self.config:
                self.config["wind_speed_settings"] = {}
            if "plc_settings" not in self.config:
                self.config["plc_settings"] = {}
            if "products" not in self.config:
                self.config["products"] = []

            # 1. Gather hardware settings from UI
            loader.update_progress(20, "正在收集硬件配置...")
            time.sleep(0.1)
            
            for i in range(1, 11):
                station_key = f"工位{i}"
                if station_key in self.hardware_entries:
                    entries = self.hardware_entries[station_key]
                    can_sn = entries["can_sn"].get()
                    can_channel = entries["can_channel"].get()
                    scanner_ip = entries["scanner_ip"].get()
                    
                    self.config["hardware_settings"][station_key] = {
                        "can_sn": can_sn,
                        "can_channel": can_channel,
                        "scanner_ip": scanner_ip
                    }
                    
                    self.log_message(f"保存工位{i}配置: CAN SN={can_sn}, Channel={can_channel}, Scanner IP={scanner_ip}")
            
            # 2. Gather wind speed settings from UI
            loader.update_progress(40, "正在收集风速设置...")
            time.sleep(0.1)
            
            self.config["wind_speed_settings"] = {
                "plc1_wind_speed": self.wind_speed_entries["plc1"].get(),
                "plc2_wind_speed": self.wind_speed_entries["plc2"].get()
            }
            
            # 保存PLC IP设置
            self.config["plc_settings"] = {
                "plc1_ip": self.plc_ip_entries["plc1_ip"].get(),
                "plc2_ip": self.plc_ip_entries["plc2_ip"].get()
            }
            
            # 3. Gather product settings (times) from Table UI
            loader.update_progress(60, "正在收集产品参数...")
            time.sleep(0.1)
            
            # We iterate through all rows in the product table
            new_products = []
            
            # Helper to get all test keys (columns)
            # We assume all products have the same structure as the first one or a default list
            # For simplicity, we'll use the column headers we created dynamically
            
            # The structure of self.prod_table_entries is:
            # { row_index: { 'name': widget, 'times': { 'test_name': widget, ... } } }
            
            for row_idx, data in self.prod_table_entries.items():
                name_val = data['name'].get().strip()
                if not name_val: continue # Skip empty rows
                
                times_dict = {}
                for test_name, entry_widget in data['times'].items():
                    try:
                        val = int(entry_widget.get())
                    except ValueError:
                        val = 0 # Default to 0 if invalid
                    times_dict[test_name] = val
                
                powers_dict = {}
                for power_name, entry_widget in data['powers'].items():
                    try:
                        val = float(entry_widget.get())
                    except ValueError:
                        val = 0.0 # Default to 0 if invalid
                    powers_dict[power_name] = val
                
                # 获取Part Number
                part_number = data.get('part_number', {}).get() if isinstance(data.get('part_number'), tk.Entry) else ""
                
                new_products.append({
                    "name": name_val,
                    "times": times_dict,
                    "powers": powers_dict,
                    "part_number": part_number
                })
            
            self.config["products"] = new_products
            
            # 4. 保存扫码和标签设置
            loader.update_progress(70, "正在收集扫码和标签设置...")
            time.sleep(0.1)
            
            self.config["scan_start"] = self.scan_start_var.get()
            self.config["print_label_qr"] = self.print_label_qr_var.get()
            
            loader.update_progress(80, "正在写入配置文件...")
            time.sleep(0.1)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            # 调用配置保存回调，更新风速设置
            loader.update_progress(90, "正在更新系统状态...")
            if hasattr(self, 'config_save_callback') and self.config_save_callback:
                self.config_save_callback()
            
            loader.update_progress(100, "保存成功!")
            time.sleep(0.5)
            loader.destroy()
            
            if show_message:
                messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            if loader:
                loader.destroy()
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def create_grid_ui(self):
        # Configure columns weights for the test frame
        # Index (0) has weight 0 and fixed width
        self.test_frame.grid_columnconfigure(0, weight=0, minsize=40) 
        # Item (1) has weight 0 and fixed width
        self.test_frame.grid_columnconfigure(1, weight=0, minsize=150) 
        
        # Test cols (2-11) should have equal width
        for i in range(2, 12):
            self.test_frame.grid_columnconfigure(i, weight=1, minsize=100) # Ensure minimum width

        # --- Row 0: Headers ---
        for col_idx, text in enumerate(self.headers):
            width = 12 if col_idx >= 2 else (5 if col_idx == 0 else 20)
            lbl = tk.Label(self.test_frame, text=text, font=('Arial', 10, 'bold'), 
                           relief="solid", borderwidth=1, bg="#e0e0e0", width=width)
            lbl.grid(row=0, column=col_idx, sticky="nsew")
        
        # --- Row 1: Product Selection & Control Buttons ---
        
        # --- Product Selection Combobox for Test Page ---
        # Add a frame for product selection at the top left (spanning col 0 and 1)
        prod_sel_frame = tk.Frame(self.test_frame, relief="solid", borderwidth=1, bg="#f0f0f0")
        prod_sel_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        
        tk.Label(prod_sel_frame, text="产品型号:", bg="#f0f0f0").pack(side="left", padx=5)
        
        self.current_product_var = tk.StringVar()
        product_names = [p["name"] for p in self.config.get("products", [])]
        if product_names:
            self.current_product_var.set(product_names[0])
            
        self.product_combobox = ttk.Combobox(prod_sel_frame, textvariable=self.current_product_var, values=product_names, width=10)
        self.product_combobox.pack(side="left", padx=5, fill="x", expand=True)
        # Bind event to refresh if needed later
        self.product_combobox.bind("<<ComboboxSelected>>", self.on_test_product_selected)

        # --- Control Buttons for each test column ---
        for i in range(1, 11):
            col_idx = i + 1
            btn_frame = tk.Frame(self.test_frame, relief="solid", borderwidth=1)
            btn_frame.grid(row=1, column=col_idx, sticky="nsew")
            
            # Start/Stop buttons
            # Use smaller font or condensed text to fit
            btn_start = tk.Button(btn_frame, text="开始", font=('Arial', 8), bg="#90ee90", command=lambda x=i: self.start_test(x))
            btn_stop = tk.Button(btn_frame, text="结束", font=('Arial', 8), bg="#ffcccb", command=lambda x=i: self.stop_test(x))
            
            btn_start.pack(side="left", fill="both", expand=True, padx=1, pady=1)
            btn_stop.pack(side="left", fill="both", expand=True, padx=1, pady=1)

        # --- Row 2 to 32: Data ---
        total_rows = len(self.items_data)
        
        # Configure row weights so they expand evenly to fill the screen
        # Row 0 (Header) and Row 1 (Buttons) can be fixed height or weighted less
        self.test_frame.grid_rowconfigure(0, weight=0, minsize=30) # Header
        self.test_frame.grid_rowconfigure(1, weight=0, minsize=30) # Buttons
        
        current_grid_row = 2
        for r in range(total_rows):
            item = self.items_data[r]
            idx, name, status = item[0], item[1], item[2]
            
            # Skip items with index 31-34
            if 31 <= idx <= 34:
                continue
            
            # Configure row weight
            self.test_frame.grid_rowconfigure(current_grid_row, weight=1) # Data rows expand
            
            # Col 0: Index
            tk.Label(self.test_frame, text=str(idx), relief="solid", borderwidth=1).grid(row=current_grid_row, column=0, sticky="nsew")
            
            # Col 1: Name
            tk.Label(self.test_frame, text=name, anchor="w", padx=5, relief="solid", borderwidth=1).grid(row=current_grid_row, column=1, sticky="nsew")
            
            # Col 2-11: Status
            for c in range(10):
                col_idx = c + 2
                station_id = c + 1  # 1-10
                # Use fixed width for cells to prevent resizing
                lbl = tk.Label(self.test_frame, text=status, relief="solid", borderwidth=1, bg="white", width=12)
                lbl.grid(row=current_grid_row, column=col_idx, sticky="nsew")
                
                # Store reference: (station_id, item_index)
                # Ensure idx matches items_data definition
                self.status_cells[(station_id, idx)] = lbl
            
            current_grid_row += 1

    def set_start_callback(self, callback):
        self.start_callback = callback

    def set_stop_callback(self, callback):
        self.stop_callback = callback
        
    def set_config_save_callback(self, callback):
        """设置配置保存回调"""
        self.config_save_callback = callback

    def start_test(self, station_idx):
        """开始测试"""
        if self.start_callback:
            self.start_callback(station_idx)

    def stop_test(self, station_idx):
        """停止测试"""
        if self.stop_callback:
            self.stop_callback(station_idx)

    def update_cell(self, station_idx, item_idx, text, bg_color=None):
        """Update a specific cell in the grid"""
        if (station_idx, item_idx) in self.status_cells:
            lbl = self.status_cells[(station_idx, item_idx)]
            lbl.config(text=str(text))
            if bg_color:
                lbl.config(bg=bg_color)
                
    def get_cell_text(self, station_idx, item_idx):
        if (station_idx, item_idx) in self.status_cells:
            return self.status_cells[(station_idx, item_idx)].cget("text")
        return ""

    def get_station_config(self, station_idx):
        """Get hardware config for a specific station"""
        key = f"工位{station_idx}"
        
        # 1. Get base config from file/memory
        config = self.config.get("hardware_settings", {}).get(key, {}).copy()
        
        # 2. Override with current UI values if available
        if hasattr(self, 'hardware_entries') and key in self.hardware_entries:
            entries = self.hardware_entries[key]
            
            # Map UI 'can_sn' to config 'can_sn'
            if "can_sn" in entries:
                config["can_sn"] = entries["can_sn"].get()
                
            # Map UI 'can_channel' to config 'can_channel'
            if "can_channel" in entries:
                config["can_channel"] = entries["can_channel"].get()
                
            # Map UI 'scanner_ip' to config 'scanner_ip'
            if "scanner_ip" in entries:
                config["scanner_ip"] = entries["scanner_ip"].get()
        
        # 3. 验证配置是否完整
        if not config.get("can_sn") or config.get("can_sn") == "请选择设备" or config.get("can_sn") == "未检测到设备":
            self.log_message(f"警告: 工位{station_idx}的CAN设备配置不完整")
            return None
        
        return config

    def get_current_product_config(self):
        """Get settings for the currently selected product"""
        product_name = self.current_product_var.get()
        for prod in self.config.get("products", []):
            if prod["name"] == product_name:
                return prod
        return None

    def on_test_product_selected(self, event):
        selected = self.current_product_var.get()
        print(f"Selected product for testing: {selected}")
        # Here you would typically update test parameters or limits based on the selected product

    def create_settings_ui(self):
        # Create a main container frame without scrollbar
        scrollable_frame = ttk.Frame(self.settings_frame)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Make sure widgets are properly laid out
        def update_layout():
            scrollable_frame.update_idletasks()
        
        # --- User Management Section ---
        user_frame = ttk.LabelFrame(scrollable_frame, text="用户管理")
        user_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_current_user = ttk.Label(user_frame, text="当前用户: 未登录", foreground="red")
        self.lbl_current_user.pack(side="left", padx=10)
        
        self.btn_login = ttk.Button(user_frame, text="登录", command=self.show_login_dialog)
        self.btn_login.pack(side="left", padx=5)
        
        self.btn_logout = ttk.Button(user_frame, text="登出", command=self.logout, state='disabled')
        self.btn_logout.pack(side="left", padx=5)
        
        self.btn_change_pwd = ttk.Button(user_frame, text="修改密码", command=self.show_change_password_dialog, state='disabled')
        self.btn_change_pwd.pack(side="left", padx=5)
        
        self.btn_manage_users = ttk.Button(user_frame, text="用户管理", command=self.show_user_management, state='disabled')
        self.btn_manage_users.pack(side="left", padx=5)

        # --- Section 1: Product Test Settings (Table View) ---
        tk.Label(scrollable_frame, text="产品测试设置", font=('Arial', 11, 'bold')).pack(anchor="w", padx=10, pady=5)
        
        # Create a container frame for the table
        table_frame = ttk.Frame(scrollable_frame)
        table_frame.pack(fill="x", padx=10, pady=5)
        
        # Define columns based on the first product or a standard list
        # Standard list of keys based on user input example
        # Tuples of (Display Name, Unique Key)
        self.power_target_map = [
            ("100%功率参数设置", "100%功率参数设置"), 
            ("0%功率参数设置", "0%功率参数设置_1"), 
            ("80%功率参数设置", "80%功率参数设置"), 
            ("0%功率参数设置", "0%功率参数设置_2"), 
            ("60%功率参数设置", "60%功率参数设置"), 
            ("0%功率参数设置", "0%功率参数设置_3"), 
            ("40%功率参数设置", "40%功率参数设置"), 
            ("0%功率参数设置", "0%功率参数设置_4")
        ]
        
        self.duration_map = [
            ("100%功率时间设置", "100%功率时间设置"), 
            ("0%功率时间设置", "0%功率时间设置_1"), 
            ("80%功率时间设置", "80%功率时间设置"), 
            ("0%功率时间设置", "0%功率时间设置_2"), 
            ("60%功率时间设置", "60%功率时间设置"), 
            ("0%功率时间设置", "0%功率时间设置_3"), 
            ("40%功率时间设置", "40%功率时间设置"), 
            ("0%功率时间设置", "0%功率时间设置_4")
        ]
        
        # Headers: Index, Product Name, Part Number, [Time Keys...], [Power Keys...]
        headers = ["序号", "产品型号", "Part Number"] + [x[0] for x in self.power_target_map] + [x[0] for x in self.duration_map]
        
        # Column 0: Index (narrower)
        lbl_idx = tk.Label(table_frame, text=headers[0], font=('SimHei', 8), 
                       relief="solid", borderwidth=1, bg="#e0e0e0", width=4)
        lbl_idx.grid(row=0, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)

        # Column 1: Product Name
        lbl_name = tk.Label(table_frame, text=headers[1], font=('SimHei', 8), 
                       relief="solid", borderwidth=1, bg="#e0e0e0", width=8)
        lbl_name.grid(row=0, column=1, sticky="nsew")
        table_frame.grid_columnconfigure(1, weight=1)
        
        # Column 2: Part Number
        lbl_part = tk.Label(table_frame, text=headers[2], font=('SimHei', 8), 
                       relief="solid", borderwidth=1, bg="#e0e0e0", width=12)
        lbl_part.grid(row=0, column=2, sticky="nsew")
        table_frame.grid_columnconfigure(2, weight=1)

        # Other columns (Time Keys)
        for col in range(3, len(headers)):
            text = headers[col]
            # Using smaller font
            lbl = tk.Label(table_frame, text=text, font=('SimHei', 8), 
                           relief="solid", borderwidth=1, bg="#e0e0e0", width=8) # Further reduced width
            lbl.grid(row=0, column=col, sticky="nsew")
            table_frame.grid_columnconfigure(col, weight=1) # Equal weight for all columns

        # Load products
        products = self.config.get("products", [])
        self.prod_table_entries = {}
        
        # Ensure at least 10 rows for products
        display_products = products[:]
        while len(display_products) < 10:
             display_products.append({
                 "name": "", 
                 "times": {k: 0 for _, k in self.power_target_map}, 
                 "powers": {k: 0 for _, k in self.duration_map}, 
                 "part_number": ""
             })
        
        # Limit to 10 rows as requested
        for i, prod in enumerate(display_products[:10]):
            row = i + 1
            entries = {'times': {}, 'powers': {}}
            
            # Index
            tk.Label(table_frame, text=str(i+1), relief="solid", borderwidth=1, width=4).grid(row=row, column=0, sticky="nsew")
            
            # Name
            e_name = tk.Entry(table_frame, width=8, font=('Arial', 8))
            e_name.insert(0, prod.get("name", ""))
            e_name.grid(row=row, column=1, sticky="nsew")
            entries['name'] = e_name
            
            # Part Number
            e_part = tk.Entry(table_frame, width=12, font=('Arial', 8))
            e_part.insert(0, prod.get("part_number", ""))
            e_part.grid(row=row, column=2, sticky="nsew")
            entries['part_number'] = e_part
            
            # Time Values (Power Targets)
            times = prod.get("times", {})
            print(f"DEBUG: Loading times for {prod.get('name')}: {times}")
            for j, (display_name, unique_key) in enumerate(self.power_target_map):
                col = j + 3  # 调整列索引，因为增加了Part Number列
                e_time = tk.Entry(table_frame, width=8, font=('Arial', 8))
                
                # Try unique key first, then fallback to display name (legacy)
                if unique_key in times:
                    val = times[unique_key]
                elif display_name in times:
                    val = times[display_name]
                else:
                    val = 0
                
                print(f"DEBUG: Key='{unique_key}', Val={val}")
                e_time.insert(0, str(val))
                e_time.grid(row=row, column=col, sticky="nsew")
                entries['times'][unique_key] = e_time 
            
            # Power Values (Durations)
            powers = prod.get("powers", {})
            for j, (display_name, unique_key) in enumerate(self.duration_map):
                col = j + 3 + len(self.power_target_map)  # 调整列索引，在时间列之后
                e_power = tk.Entry(table_frame, width=10, font=('Arial', 8))
                
                if unique_key in powers:
                    val = powers[unique_key]
                elif display_name in powers:
                    val = powers[display_name]
                else:
                    val = 0

                e_power.insert(0, str(val))
                e_power.grid(row=row, column=col, sticky="nsew")
                entries['powers'][unique_key] = e_power
                
            self.prod_table_entries[i] = entries

        # --- Section 2: Hardware Settings (10 Stations) ---
        # Hardware Settings
        hw_frame = ttk.LabelFrame(scrollable_frame, text="工位硬件通讯设置")
        hw_frame.pack(fill="x", expand=False, padx=10, pady=10)
        
        # 添加刷新设备按钮
        refresh_frame = ttk.Frame(hw_frame)
        refresh_frame.pack(fill="x", padx=5, pady=5)
        self.refresh_devices_btn = ttk.Button(refresh_frame, text="刷新CAN设备", command=self.on_refresh_devices)
        self.refresh_devices_btn.pack(side="left", padx=5)
        
        # Split into two columns: Stations 1-5 (Left) and 6-10 (Right)
        hw_left = ttk.Frame(hw_frame)
        hw_left.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        hw_right = ttk.Frame(hw_frame)
        hw_right.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
        # Headers for Hardware Settings
        headers = ["工位", "CAN SN", "CAN通道", "Scanner IP"]
        
        # Helper to create headers
        def create_hw_headers(parent):
            for col, text in enumerate(headers):
                tk.Label(parent, text=text, font=('Arial', 8, 'bold')).grid(row=0, column=col, padx=3, pady=3, sticky="w")
        
        create_hw_headers(hw_left)
        create_hw_headers(hw_right)
            
        self.hardware_entries = {}
        self.device_info = {}  # 存储设备信息映射
        hardware_data = self.config.get("hardware_settings", {})
        
        # 初始设备列表
        self.device_list = []
        
        for i in range(1, 11):
            station_key = f"工位{i}"
            station_data = hardware_data.get(station_key, {})
            
            # Determine target frame (Left: 1-5, Right: 6-10)
            target_frame = hw_left if i <= 5 else hw_right
            row = i if i <= 5 else i - 5
            
            tk.Label(target_frame, text=station_key, font=('Arial', 8)).grid(row=row, column=0, padx=3, pady=1, sticky="w")
            
            entries = {}
            
            # CAN SN - 替换为下拉菜单，调整宽度确保文字显示完全
            e_can_sn = ttk.Combobox(target_frame, width=45, font=('Arial', 8), state="readonly")
            e_can_sn.set(station_data.get("can_sn", "请选择设备"))
            e_can_sn.grid(row=row, column=1, padx=3, pady=1)
            entries["can_sn"] = e_can_sn
            
            # CAN通道 - 新增下拉菜单
            e_can_channel = ttk.Combobox(target_frame, width=8, font=('Arial', 8), values=["0", "1"], state="readonly")
            e_can_channel.set(station_data.get("can_channel", "0"))
            e_can_channel.grid(row=row, column=2, padx=3, pady=1)
            entries["can_channel"] = e_can_channel
            
            # Scanner IP - 调整列位置
            e_ip = tk.Entry(target_frame, width=20, font=('Arial', 8))
            e_ip.insert(0, station_data.get("scanner_ip", ""))
            e_ip.grid(row=row, column=3, padx=3, pady=1)
            entries["scanner_ip"] = e_ip
            
            self.hardware_entries[station_key] = entries
        
        # 初始刷新设备列表，但保留配置文件中的CAN SN值
        current_can_sn_values = {}
        current_can_channel_values = {}
        for station_key, entries in self.hardware_entries.items():
            if "can_sn" in entries:
                current_can_sn_values[station_key] = entries["can_sn"].get()
            if "can_channel" in entries:
                current_can_channel_values[station_key] = entries["can_channel"].get()
        
        # 延迟执行设备扫描，确保UI和USB设备模块已经完全初始化
        def delayed_scan():
            self.log_message("开始延迟扫描CAN设备...")
            
            # 检查设备驱动是否正确安装
            self.log_message("检查设备驱动是否正确安装...")
            driver_ok = check_device_driver()
            
            if not driver_ok:
                self.log_message("设备驱动未正确安装，可能会影响CAN设备扫描")
            else:
                self.log_message("设备驱动安装正确")
            
            # 确保USB设备模块已经初始化
            if not USB2XXXLib_available:
                self.log_message("USB设备模块未初始化，尝试重新初始化...")
                # 尝试重新初始化USB设备模块
                init_usb_device_module()
            
            # 执行设备扫描
            self.on_refresh_devices()
            
            # 恢复配置文件中的CAN SN值和通道值
            for station_key, can_sn_value in current_can_sn_values.items():
                if station_key in self.hardware_entries:
                    if "can_sn" in self.hardware_entries[station_key]:
                        combobox = self.hardware_entries[station_key]["can_sn"]
                        if can_sn_value:
                            combobox.set(can_sn_value)
                            self.log_message(f"恢复工位{station_key}的CAN SN配置: {can_sn_value}")
                    if "can_channel" in self.hardware_entries[station_key] and station_key in current_can_channel_values:
                        channel_combobox = self.hardware_entries[station_key]["can_channel"]
                        channel_value = current_can_channel_values[station_key]
                        if channel_value:
                            channel_combobox.set(channel_value)
                            self.log_message(f"恢复工位{station_key}的CAN通道配置: {channel_value}")
            
            self.log_message("延迟扫描CAN设备完成")
        
        # 使用after方法延迟执行设备扫描，确保UI已经完全初始化
        self.root.after(2000, delayed_scan)
        
        # Wind Speed Control Section
        wind_frame = ttk.LabelFrame(scrollable_frame, text="风速控制 (PLC)")
        wind_frame.pack(fill="x", padx=10, pady=8)
        
        # 创建风速控制文本框
        self.wind_speed_entries = {}
        self.plc_ip_entries = {}
        wind_speed_settings = self.config.get("wind_speed_settings", {})
        plc_settings = self.config.get("plc_settings", {})
        
        # PLC1 IP设置
        tk.Label(wind_frame, text="PLC1 IP地址:", font=('Arial', 9)).grid(row=0, column=0, padx=3, pady=3, sticky="w")
        e_plc1_ip = tk.Entry(wind_frame, width=15, font=('Arial', 9))
        e_plc1_ip.insert(0, plc_settings.get("plc1_ip", "192.168.10.221"))
        e_plc1_ip.grid(row=0, column=1, padx=3, pady=3)
        self.plc_ip_entries["plc1_ip"] = e_plc1_ip
        
        # PLC1风速控制（1-5工位）
        tk.Label(wind_frame, text="PLC1 VD300 - 控制1-5工位风速:", font=('Arial', 9)).grid(row=1, column=0, padx=3, pady=3, sticky="w")
        e_plc1 = tk.Entry(wind_frame, width=8, font=('Arial', 9))
        e_plc1.insert(0, wind_speed_settings.get("plc1_wind_speed", ""))
        e_plc1.grid(row=1, column=1, padx=3, pady=3)
        self.wind_speed_entries["plc1"] = e_plc1
        tk.Label(wind_frame, text="(0-50 Hz)", font=('Arial', 9)).grid(row=1, column=2, padx=3, pady=3, sticky="w")
        
        # PLC2 IP设置
        tk.Label(wind_frame, text="PLC2 IP地址:", font=('Arial', 9)).grid(row=2, column=0, padx=3, pady=3, sticky="w")
        e_plc2_ip = tk.Entry(wind_frame, width=15, font=('Arial', 9))
        e_plc2_ip.insert(0, plc_settings.get("plc2_ip", "192.168.10.222"))
        e_plc2_ip.grid(row=2, column=1, padx=3, pady=3)
        self.plc_ip_entries["plc2_ip"] = e_plc2_ip
        
        # PLC2风速控制（6-10工位）
        tk.Label(wind_frame, text="PLC2 VD300 - 控制6-10工位风速:", font=('Arial', 9)).grid(row=3, column=0, padx=3, pady=3, sticky="w")
        e_plc2 = tk.Entry(wind_frame, width=8, font=('Arial', 9))
        e_plc2.insert(0, wind_speed_settings.get("plc2_wind_speed", ""))
        e_plc2.grid(row=3, column=1, padx=3, pady=3)
        self.wind_speed_entries["plc2"] = e_plc2
        tk.Label(wind_frame, text="(0-50 Hz)", font=('Arial', 9)).grid(row=3, column=2, padx=3, pady=3, sticky="w")
        
        # 扫码和标签设置
        self.scan_label_frame = ttk.LabelFrame(scrollable_frame, text="扫码和标签设置")
        self.scan_label_frame.pack(fill="x", padx=10, pady=8)
        
        # 是否扫码启动
        self.scan_start_var = tk.BooleanVar(value=self.config.get("scan_start", False))
        self.scan_start_checkbutton = tk.Checkbutton(self.scan_label_frame, text="是否扫码启动（默认关闭）", variable=self.scan_start_var, font=('Arial', 9))
        self.scan_start_checkbutton.grid(row=0, column=0, padx=3, pady=5, sticky="w")
        
        # 是否打印标签二维码
        self.print_label_qr_var = tk.BooleanVar(value=self.config.get("print_label_qr", True))
        self.print_label_qr_checkbutton = tk.Checkbutton(self.scan_label_frame, text="是否打印标签二维码（默认开启）", variable=self.print_label_qr_var, font=('Arial', 9))
        self.print_label_qr_checkbutton.grid(row=1, column=0, padx=3, pady=5, sticky="w")
        
        # Save Button
        self.save_btn = tk.Button(scrollable_frame, text="保存所有配置", bg="#ADD8E6", font=('Arial', 10), command=self.save_config)
        self.save_btn.pack(pady=15, ipadx=15)
        
        # Initial State Update
        self.update_settings_state()
        
        # Update layout finally
        update_layout()

    def update_settings_state(self):
        """Enable/Disable settings based on login state"""
        is_logged_in = self.current_user is not None
        state = 'normal' if is_logged_in else 'disabled' # For Entry
        readonly_state = 'readonly' if not is_logged_in else 'normal' # For Entry (if we want read-only)
        
        # Actually, user wants "gray and unmodifiable" -> disabled state is best for gray
        
        # Update UI elements
        if is_logged_in:
            self.lbl_current_user.config(text=f"当前用户: {self.current_user} ({self.current_role})", foreground="green")
            self.btn_login.config(state='disabled')
            self.btn_logout.config(state='normal')
            self.btn_change_pwd.config(state='normal')
            if self.current_role == 'admin':
                self.btn_manage_users.config(state='normal')
            else:
                self.btn_manage_users.config(state='disabled')
            self.save_btn.config(state='normal', bg="#ADD8E6")
        else:
            self.lbl_current_user.config(text="当前用户: 未登录 (只读模式)", foreground="red")
            self.btn_login.config(state='normal')
            self.btn_logout.config(state='disabled')
            self.btn_manage_users.config(state='disabled')
            self.btn_change_pwd.config(state='disabled')
            self.save_btn.config(state='disabled', bg="#f0f0f0")

        # Disable/Enable all product entries
        if hasattr(self, 'prod_table_entries'):
            for row_data in self.prod_table_entries.values():
                row_data['name'].config(state=state)
                for entry in row_data['times'].values():
                    entry.config(state=state)
                for entry in row_data['powers'].values():
                    entry.config(state=state)
                # Disable/Enable part number entry
                if 'part_number' in row_data:
                    row_data['part_number'].config(state=state)
                    
        # Disable/Enable all hardware entries
        if hasattr(self, 'hardware_entries'):
            for station_data in self.hardware_entries.values():
                for entry in station_data.values():
                    entry.config(state=state)
        
        # Disable/Enable wind speed entries
        if hasattr(self, 'wind_speed_entries'):
            for entry in self.wind_speed_entries.values():
                entry.config(state=state)
        
        # Disable/Enable PLC IP entries
        if hasattr(self, 'plc_ip_entries'):
            for entry in self.plc_ip_entries.values():
                entry.config(state=state)
        
        # Disable/Enable scan and label settings checkboxes
        if hasattr(self, 'scan_start_checkbutton'):
            self.scan_start_checkbutton.config(state=state)
        if hasattr(self, 'print_label_qr_checkbutton'):
            self.print_label_qr_checkbutton.config(state=state)
        
        # Reset boolean variables to config values when not logged in
        if not is_logged_in:
            if hasattr(self, 'scan_start_var'):
                self.scan_start_var.set(self.config.get("scan_start", False))
            if hasattr(self, 'print_label_qr_var'):
                self.print_label_qr_var.set(self.config.get("print_label_qr", True))

    def show_login_dialog(self):
        """显示登录对话框"""
        LoginDialog(self.root, self.on_login_success)

    def on_login_success(self, username, role):
        self.current_user = username
        self.current_role = role
        self.update_settings_state()
        messagebox.showinfo("登录成功", f"欢迎回来, {username}")

    def logout(self):
        self.current_user = None
        self.current_role = None
        self.update_settings_state()
        messagebox.showinfo("登出", "您已成功登出")

    def show_user_management(self):
        """显示用户管理对话框"""
        UserManagementDialog(self.root)

    def show_change_password_dialog(self):
        """显示修改密码对话框"""
        if self.current_user:
            ChangePasswordDialog(self.root, self.current_user)
        else:
            messagebox.showinfo("提示", "请先登录")

    def show_date_picker(self, entry_widget):
        current_val = entry_widget.get()
        dlg = DatePickerDialog(self.root, current_val)
        if dlg.result:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, dlg.result)
    
    def create_visualization_ui(self):
        """创建数据可视化页面UI"""
        # 使用grid布局管理器
        self.visualization_frame.grid_columnconfigure(0, weight=1)
        self.visualization_frame.grid_rowconfigure(0, weight=0)
        self.visualization_frame.grid_rowconfigure(1, weight=1)
        
        # --- 控制区域 ---
        control_frame = ttk.LabelFrame(self.visualization_frame, text="可视化控制")
        control_frame.grid(row=0, column=0, padx=10, pady=5, sticky="we")
        
        # 时间范围选择
        tk.Label(control_frame, text="开始时间:", font=('Arial', 9)).grid(row=0, column=0, padx=5, pady=3, sticky="w")
        self.vis_start_time = tk.Entry(control_frame, width=16, font=('Arial', 9))
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        self.vis_start_time.insert(0, one_week_ago.strftime("%Y-%m-%d 00:00:00"))
        self.vis_start_time.grid(row=0, column=1, padx=5, pady=3, sticky="we")
        self.vis_start_time.bind("<Button-1>", lambda event: self.show_date_picker(self.vis_start_time))
        
        tk.Label(control_frame, text="结束时间:", font=('Arial', 9)).grid(row=0, column=2, padx=5, pady=3, sticky="w")
        self.vis_end_time = tk.Entry(control_frame, width=16, font=('Arial', 9))
        self.vis_end_time.insert(0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.vis_end_time.grid(row=0, column=3, padx=5, pady=3, sticky="we")
        self.vis_end_time.bind("<Button-1>", lambda event: self.show_date_picker(self.vis_end_time))
        
        # 工位选择
        tk.Label(control_frame, text="工位:", font=('Arial', 9)).grid(row=1, column=0, padx=5, pady=3, sticky="w")
        self.vis_station_var = tk.StringVar(value="全部")
        station_options = ["全部"] + [str(i) for i in range(1, 11)]
        self.vis_station_combo = ttk.Combobox(control_frame, textvariable=self.vis_station_var, values=station_options, width=8)
        self.vis_station_combo.grid(row=1, column=1, padx=5, pady=3, sticky="we")
        
        # 产品型号选择
        tk.Label(control_frame, text="产品型号:", font=('Arial', 9)).grid(row=1, column=2, padx=5, pady=3, sticky="w")
        self.vis_product_var = tk.StringVar(value="全部")
        product_names = [p["name"] for p in self.config.get("products", [])]
        product_options = ["全部"] + product_names
        self.vis_product_combo = ttk.Combobox(control_frame, textvariable=self.vis_product_var, values=product_options, width=12)
        self.vis_product_combo.grid(row=1, column=3, padx=5, pady=3, sticky="we")
        
        # 图表类型选择
        tk.Label(control_frame, text="图表类型:", font=('Arial', 9)).grid(row=2, column=0, padx=5, pady=3, sticky="w")
        self.vis_chart_var = tk.StringVar(value="测试结果分布")
        chart_options = ["测试结果分布", "工位测试效率", "测试时间趋势"]
        self.vis_chart_combo = ttk.Combobox(control_frame, textvariable=self.vis_chart_var, values=chart_options, width=12)
        self.vis_chart_combo.grid(row=2, column=1, padx=5, pady=3, sticky="we")
        
        # 生成图表按钮
        self.btn_generate_chart = ttk.Button(control_frame, text="生成图表", command=self.generate_chart)
        self.btn_generate_chart.grid(row=2, column=2, columnspan=2, padx=5, pady=3, sticky="we")
        
        # 配置列权重
        control_frame.grid_columnconfigure(0, weight=0)
        control_frame.grid_columnconfigure(1, weight=1)
        control_frame.grid_columnconfigure(2, weight=0)
        control_frame.grid_columnconfigure(3, weight=1)
        
        # --- 图表展示区域 ---
        chart_frame = ttk.LabelFrame(self.visualization_frame, text="图表展示")
        chart_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        # 创建图表容器
        self.chart_canvas_frame = ttk.Frame(chart_frame)
        self.chart_canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
    def generate_chart(self):
        """生成图表"""
        try:
            # 导入matplotlib库
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import numpy as np
            
            # 获取查询参数
            start_time = self.vis_start_time.get()
            end_time = self.vis_end_time.get()
            station_selection = self.vis_station_var.get()
            product = self.vis_product_var.get()
            chart_type = self.vis_chart_var.get()
            
            # 构建查询参数
            station_id = None
            if station_selection != "全部":
                try:
                    station_id = int(station_selection)
                except ValueError:
                    pass
            
            # 查询数据库
            results = database.query_records(
                start_time=start_time, 
                end_time=end_time, 
                station_id=station_id,
                scan_result=None,
                label_qr=None
            )
            
            # 过滤产品
            filtered_results = []
            for r in results:
                if product != "全部" and product and r['product_model'] != product:
                    continue
                filtered_results.append(r)
            
            if not filtered_results:
                messagebox.showinfo("提示", "没有找到匹配的数据")
                return
            
            # 清空现有图表
            for widget in self.chart_canvas_frame.winfo_children():
                widget.destroy()
            
            # 创建图表
            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)
            
            if chart_type == "测试结果分布":
                # 统计通过/失败数量
                pass_count = 0
                fail_count = 0
                
                for r in filtered_results:
                    details = r.get('details', {})
                    is_fail = False
                    for k, v in details.items():
                        if isinstance(v, str) and ("FAIL" in v or "Fail" in v):
                            is_fail = True
                            break
                    if is_fail:
                        fail_count += 1
                    else:
                        pass_count += 1
                
                # 绘制饼图
                labels = ['通过', '失败']
                sizes = [pass_count, fail_count]
                colors = ['#90EE90', '#FFCCCB']
                ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax.axis('equal')
                ax.set_title('测试结果分布')
                
            elif chart_type == "工位测试效率":
                # 统计各工位的测试数量
                station_counts = {}
                for r in filtered_results:
                    station = r['station_id']
                    if station in station_counts:
                        station_counts[station] += 1
                    else:
                        station_counts[station] = 1
                
                # 排序工位
                stations = sorted(station_counts.keys())
                counts = [station_counts[s] for s in stations]
                
                # 绘制柱状图
                ax.bar(stations, counts, color='#87CEEB')
                ax.set_xlabel('工位')
                ax.set_ylabel('测试数量')
                ax.set_title('工位测试效率')
                ax.set_xticks(stations)
                
            elif chart_type == "测试时间趋势":
                # 按日期分组统计测试数量
                date_counts = {}
                for r in filtered_results:
                    # 提取日期部分
                    date = r['completion_time'].split(' ')[0]
                    if date in date_counts:
                        date_counts[date] += 1
                    else:
                        date_counts[date] = 1
                
                # 排序日期
                dates = sorted(date_counts.keys())
                counts = [date_counts[d] for d in dates]
                
                # 绘制折线图
                ax.plot(dates, counts, marker='o', color='#FF6347')
                ax.set_xlabel('日期')
                ax.set_ylabel('测试数量')
                ax.set_title('测试时间趋势')
                ax.tick_params(axis='x', rotation=45)
                fig.tight_layout()
            
            # 创建画布并显示
            canvas = FigureCanvasTkAgg(fig, master=self.chart_canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # 添加统计信息
            stats_frame = ttk.LabelFrame(self.chart_canvas_frame, text="统计信息")
            stats_frame.pack(fill="x", padx=10, pady=5)
            
            total_tests = len(filtered_results)
            avg_time = 0
            
            # 计算平均测试时间（如果有时间数据）
            # 这里简化处理，实际应该从details中提取
            
            stats_text = f"总测试次数: {total_tests}\n"
            stats_text += f"平均测试时间: N/A\n"
            stats_text += f"数据时间范围: {start_time} 至 {end_time}"
            
            tk.Label(stats_frame, text=stats_text, justify="left").pack(padx=10, pady=5)
            
        except ImportError as e:
            messagebox.showerror("错误", f"导入matplotlib库失败: {e}\n请确保已安装matplotlib库")
        except Exception as e:
            messagebox.showerror("错误", f"生成图表失败: {e}")
            import traceback
            traceback.print_exc()

    def create_query_ui(self):
        """创建查询页面UI"""
        # Use a regular frame instead of canvas to avoid scrolling
        scrollable_frame = ttk.Frame(self.query_frame)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Query Controls Section ---
        query_controls_frame = ttk.LabelFrame(scrollable_frame, text="查询条件")
        query_controls_frame.pack(fill="x", padx=10, pady=5)
        
        # 使用grid布局管理器并配置列权重
        query_controls_frame.grid_columnconfigure(0, weight=0)
        query_controls_frame.grid_columnconfigure(1, weight=1)
        query_controls_frame.grid_columnconfigure(2, weight=0)
        query_controls_frame.grid_columnconfigure(3, weight=1)
        query_controls_frame.grid_columnconfigure(4, weight=0)
        query_controls_frame.grid_columnconfigure(5, weight=1)
        query_controls_frame.grid_columnconfigure(6, weight=0)
        query_controls_frame.grid_columnconfigure(7, weight=0)
        
        # Row 0: Time range
        # Start time
        tk.Label(query_controls_frame, text="开始时间:", font=('Arial', 9)).grid(row=0, column=0, padx=5, pady=3, sticky="w")
        self.entry_start_time = tk.Entry(query_controls_frame, width=18, font=('Arial', 9))
        # 设置默认开始时间为一周前，以便包含之前的记录
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        self.entry_start_time.insert(0, one_week_ago.strftime("%Y-%m-%d 00:00:00"))
        self.entry_start_time.grid(row=0, column=1, padx=5, pady=3, sticky="we")
        self.entry_start_time.bind("<Button-1>", lambda event: self.show_date_picker(self.entry_start_time))
        
        # End time
        tk.Label(query_controls_frame, text="结束时间:", font=('Arial', 9)).grid(row=0, column=2, padx=5, pady=3, sticky="w")
        self.entry_end_time = tk.Entry(query_controls_frame, width=18, font=('Arial', 9))
        self.entry_end_time.insert(0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.entry_end_time.grid(row=0, column=3, padx=5, pady=3, sticky="we")
        self.entry_end_time.bind("<Button-1>", lambda event: self.show_date_picker(self.entry_end_time))
        
        # Row 1: Product and Station
        # Product selection
        tk.Label(query_controls_frame, text="产品型号:", font=('Arial', 9)).grid(row=1, column=0, padx=5, pady=3, sticky="w")
        self.product_var = tk.StringVar()
        product_names = [p["name"] for p in self.config.get("products", [])]
        # 添加"全部"选项
        product_options = ["全部"] + product_names
        self.product_combobox = ttk.Combobox(query_controls_frame, textvariable=self.product_var, values=product_options, width=15)
        # 默认选择"全部"
        self.product_combobox.current(0)
        self.product_combobox.grid(row=1, column=1, padx=5, pady=3, sticky="we")
        
        # Station selection
        tk.Label(query_controls_frame, text="工位选择:", font=('Arial', 9)).grid(row=1, column=2, padx=5, pady=3, sticky="w")
        self.station_var = tk.StringVar(value="全部")
        station_options = ["全部"] + [str(i) for i in range(1, 11)]
        self.station_combo = ttk.Combobox(query_controls_frame, textvariable=self.station_var, values=station_options, width=10)
        self.station_combo.grid(row=1, column=3, padx=5, pady=3, sticky="we")
        
        # Row 2: Barcode and Label QR
        # Barcode
        tk.Label(query_controls_frame, text="条码:", font=('Arial', 9)).grid(row=2, column=0, padx=5, pady=3, sticky="w")
        self.barcode_var = tk.StringVar()
        self.barcode_entry = tk.Entry(query_controls_frame, textvariable=self.barcode_var, width=20, font=('Arial', 9))
        self.barcode_entry.grid(row=2, column=1, padx=5, pady=3, sticky="we")
        
        # Label QR
        tk.Label(query_controls_frame, text="标签二维码:", font=('Arial', 9)).grid(row=2, column=2, padx=5, pady=3, sticky="w")
        self.label_qr_var = tk.StringVar()
        self.label_qr_entry = tk.Entry(query_controls_frame, textvariable=self.label_qr_var, width=20, font=('Arial', 9))
        self.label_qr_entry.grid(row=2, column=3, padx=5, pady=3, sticky="we")
        
        # Row 3: Buttons
        button_frame = ttk.Frame(query_controls_frame)
        button_frame.grid(row=3, column=0, columnspan=8, padx=5, pady=5, sticky="e")
        
        # Query Button
        self.btn_query = ttk.Button(button_frame, text="查询", command=self.on_query)
        self.btn_query.pack(side="left", padx=5)
        
        # Export Button
        self.btn_export = ttk.Button(button_frame, text="导出", command=self.on_export)
        self.btn_export.pack(side="left", padx=5)
        
        # Clear Button
        self.btn_clear = ttk.Button(button_frame, text="清空", command=self.on_clear_query)
        self.btn_clear.pack(side="left", padx=5)

        # --- Query Results Section ---
        results_frame = ttk.LabelFrame(scrollable_frame, text="查询结果")
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 1. Define Base Columns
        base_columns = ["序号", "测试时间", "产品型号", "条码", "标签二维码", "工位", "测试结果"]
        base_col_ids = ["id", "time", "product", "barcode", "label_qr", "station", "result"]
        
        # 2. Define Dynamic Columns (用户确认的测试数据项)
        dynamic_col_names = [
            "100%功率",
            "100%功率反馈电压",
            "100%功率反馈电流",
            "80%功率",
            "80%功率反馈电压",
            "80%功率反馈电流",
            "60%功率",
            "60%功率反馈电压",
            "60%功率反馈电流",
            "40%功率",
            "40%功率反馈电压",
            "40%功率反馈电流",
            "故障状态"
        ]
        
        # 为每个动态列创建唯一的列ID
        dynamic_col_ids = []
        for i, name in enumerate(dynamic_col_names):
            # 使用列名作为ID，确保唯一性
            col_id = name.replace("%", "_percent").replace(" ", "_").lower()
            dynamic_col_ids.append(col_id)
        
        all_col_ids = base_col_ids + dynamic_col_ids
        
        # Create Treeview
        self.tree = ttk.Treeview(results_frame, columns=all_col_ids, show="headings", height=25)
        
        # 3. Setup Headers and Widths
        # Base Columns
        self.tree.heading("id", text="序号")
        self.tree.column("id", width=50, anchor="center")
        
        self.tree.heading("time", text="测试时间")
        self.tree.column("time", width=140, anchor="center")
        
        self.tree.heading("product", text="产品型号")
        self.tree.column("product", width=100, anchor="center")
        
        self.tree.heading("barcode", text="条码")
        self.tree.column("barcode", width=120, anchor="center")
        
        self.tree.heading("label_qr", text="标签二维码")
        self.tree.column("label_qr", width=150, anchor="center")
        
        self.tree.heading("station", text="工位")
        self.tree.column("station", width=50, anchor="center")
        
        self.tree.heading("result", text="结果")
        self.tree.column("result", width=60, anchor="center")
        
        # Dynamic Columns
        for i, col_id in enumerate(dynamic_col_ids):
            name = dynamic_col_names[i]
            self.tree.heading(col_id, text=name)
            # 根据列名调整宽度
            if "电压" in name or "电流" in name:
                self.tree.column(col_id, width=120, anchor="center")
            else:
                self.tree.column(col_id, width=100, anchor="center")
        
        # Add tooltip functionality for truncated content
        self.tooltip = None
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", self.on_tree_leave)
        
        # Add scrollbars
        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Optional: Double click to see details (still useful if screen is small)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 启动时不再自动执行查询，避免弹出不必要的弹窗
        # 如果需要测试查询功能，可以手动点击查询按钮

    def on_query(self):
        """处理查询请求"""
        start_time = self.entry_start_time.get()
        end_time = self.entry_end_time.get()
        product = self.product_var.get()
        station_selection = self.station_var.get()
        barcode = self.barcode_var.get().strip()
        label_qr = self.label_qr_var.get().strip()
        
        print(f"Query parameters: start_time={start_time}, end_time={end_time}, product={product}, station_selection={station_selection}, barcode={barcode}, label_qr={label_qr}")
        
        station_id = None
        if station_selection != "全部":
            try:
                station_id = int(station_selection)
                print(f"Station ID: {station_id}")
            except ValueError:
                # 如果不是数字，可能是"全部"选项，不报错
                print(f"Station selection is not a number: {station_selection}")
                pass

        # 清空现有结果
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # Query from database
            print("Calling database.query_records...")
            results = database.query_records(
                start_time=start_time, 
                end_time=end_time, 
                station_id=station_id,
                scan_result=barcode if barcode else None,
                label_qr=label_qr if label_qr else None
            )
            print(f"Database returned {len(results)} results")
            
            # Pre-filter results to calculate correct display indices
            filtered_results = []
            print(f"Filtering results for product: {product}")
            for r in results:
                print(f"Record product_model: {r['product_model']}")
                if product != "全部" and product and r['product_model'] != product:
                    print(f"Skipping record with product_model: {r['product_model']}")
                    continue
                filtered_results.append(r)
            
            total_count = len(filtered_results)
            print(f"Filtered results count: {total_count}")
            
            # Store results for detail view
            self.current_query_results = {r['id']: r for r in filtered_results}
            # Map tree item IDs to record IDs for double-click handling
            self.tree_item_map = {}
            
            count = 0
            for i, r in enumerate(filtered_results):
                # Calculate display index: Newest (first) gets highest index
                display_index = total_count - i
                
                # Determine "Result" (Pass/Fail)
                test_result = "通过"
                details = r.get('details', {})
                for k, v in details.items():
                    if isinstance(v, str) and ("FAIL" in v or "0x2" in v and "恢复" not in str(k)): # Rough check
                        # Note: This logic is imperfect because we need to know which item failed.
                        # But for now, if any value says "FAIL", it's a fail.
                        pass
                
                # Check scan_result or other indicators if needed.
                # Assuming 'scan_result' is just the barcode.
                
                # Prepare Row Values
                # Base: ["id", "time", "product", "barcode", "label_qr", "station", "result"]
                row_values = [
                    display_index, # Display Index (N, N-1, ... 1)
                    r['completion_time'],
                    r['product_model'],
                    r['scan_result'] if r['scan_result'] else "N/A",
                    r.get('label_qr', ""),
                    r['station_id'],
                    test_result
                ]
                
                # Dynamic: 用户确认的测试数据项
                # 按照用户确认的列首顺序提取数据
                dynamic_values = [
                    details.get("100%功率", ""),
                    details.get("100%功率反馈电压", ""),
                    details.get("100%功率反馈电流", ""),
                    details.get("80%功率", ""),
                    details.get("80%功率反馈电压", ""),
                    details.get("80%功率反馈电流", ""),
                    details.get("60%功率", ""),
                    details.get("60%功率反馈电压", ""),
                    details.get("60%功率反馈电流", ""),
                    details.get("40%功率", ""),
                    details.get("40%功率反馈电压", ""),
                    details.get("40%功率反馈电流", ""),
                    details.get("故障状态", "")
                ]
                
                # 添加动态值到行数据
                row_values.extend(dynamic_values)
                
                # Update result based on value content
                for val in dynamic_values:
                    if "FAIL" in str(val) or "Fail" in str(val):
                        test_result = "失败"
                        break
                
                # Update result column (index 6)
                row_values[6] = test_result
                
                item_id = self.tree.insert("", "end", values=row_values, tags=('fail' if test_result == "失败" else 'pass',))
                self.tree_item_map[item_id] = r['id']
                count += 1
                
            self.tree.tag_configure('fail', foreground='red')
            self.tree.tag_configure('pass', foreground='green')
            
            if count == 0:
                self.log_message("未找到匹配的记录")
                messagebox.showinfo("查询结果", "未找到匹配的记录，请检查查询条件")
            else:
                self.log_message(f"找到 {count} 条记录")
                messagebox.showinfo("查询结果", f"找到 {count} 条记录")
                
        except Exception as e:
            self.log_message(f"查询出错: {e}")
            import traceback
            traceback.print_exc()

    def on_tree_double_click(self, event):
        """Handle double click on query result"""
        item_id = self.tree.selection()
        if not item_id:
            return
            
        # Get the tree item ID (e.g., 'I001')
        tree_id = item_id[0]
        
        # Look up the real database ID using our map
        if hasattr(self, 'tree_item_map') and tree_id in self.tree_item_map:
            record_id = self.tree_item_map[tree_id]
            if hasattr(self, 'current_query_results') and record_id in self.current_query_results:
                record = self.current_query_results[record_id]
                self.show_details_popup(record)
            
    def on_export(self):
        """导出查询结果"""
        try:
            import csv
            import os
            from datetime import datetime
            
            # 获取当前查询结果
            if not hasattr(self, 'current_query_results') or not self.current_query_results:
                messagebox.showinfo("导出", "请先执行查询操作获取数据")
                return
            
            # 创建导出文件路径
            export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "导出数据")
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(export_dir, f"测试数据_{timestamp}.csv")
            
            # 准备数据
            results = list(self.current_query_results.values())
            
            # 写入CSV文件
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # 定义字段名
                fieldnames = ['序号', '测试时间', '产品型号', '条码', '标签二维码', '工位', '测试结果']
                
                # 添加用户确认的动态字段
                dynamic_fieldnames = [
                    "100%功率",
                    "100%功率反馈电压",
                    "100%功率反馈电流",
                    "80%功率",
                    "80%功率反馈电压",
                    "80%功率反馈电流",
                    "60%功率",
                    "60%功率反馈电压",
                    "60%功率反馈电流",
                    "40%功率",
                    "40%功率反馈电压",
                    "40%功率反馈电流",
                    "故障状态"
                ]
                
                fieldnames.extend(dynamic_fieldnames)
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # 写入数据
                for i, r in enumerate(results):
                    row = {
                        '序号': i + 1,
                        '测试时间': r['completion_time'],
                        '产品型号': r['product_model'],
                        '条码': r['scan_result'] if r['scan_result'] else "N/A",
                        '标签二维码': r.get('label_qr', ""),
                        '工位': r['station_id'],
                        '测试结果': "通过" # 默认通过，实际应该根据详情判断
                    }
                    
                    # 添加用户确认的动态字段数据
                    details = r.get('details', {})
                    for field in dynamic_fieldnames:
                        row[field] = details.get(field, "")
                    
                    # 更新测试结果
                    test_result = "通过"
                    for field in dynamic_fieldnames:
                        value = details.get(field, "")
                        if "FAIL" in str(value) or "Fail" in str(value):
                            test_result = "失败"
                            break
                    row['测试结果'] = test_result
                    
                    writer.writerow(row)
            
            self.log_message(f"导出数据成功: {filename}")
            messagebox.showinfo("导出成功", f"数据已导出到: {filename}")
        except Exception as e:
            self.log_message(f"导出数据失败: {e}")
            messagebox.showerror("导出失败", f"导出数据失败: {e}")
    
    def on_clear_query(self):
        """清空查询条件"""
        # 清空时间
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        self.entry_start_time.delete(0, tk.END)
        self.entry_start_time.insert(0, one_week_ago.strftime("%Y-%m-%d 00:00:00"))
        
        self.entry_end_time.delete(0, tk.END)
        self.entry_end_time.insert(0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # 清空产品型号
        self.product_combobox.current(0)
        
        # 清空工位选择
        self.station_combo.current(0)
        
        # 清空条码
        self.barcode_entry.delete(0, tk.END)
        
        # 清空标签二维码
        self.label_qr_entry.delete(0, tk.END)
        
        # 清空查询结果
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.log_message("查询条件已清空")
    
    def on_refresh_devices(self):
        """处理刷新设备按钮点击事件"""
        self.log_message("开始刷新CAN设备列表...")
        
        # 检查UI是否已经完全初始化
        if not hasattr(self, 'hardware_entries') or not self.hardware_entries:
            self.log_message("UI未完全初始化，延迟更新设备列表...")
            # 延迟执行设备列表更新
            self.root.after(1000, self.on_refresh_devices)
            return
        
        # 调用设备扫描方法，添加重试机制
        device_list, device_info = self.refresh_can_devices(max_retries=3, retry_delay=1.0)
        
        # 更新设备列表和设备信息映射
        self.device_list = device_list
        self.device_info = device_info
        
        # 记录扫描结果
        if device_list:
            self.log_message(f"成功扫描到 {len(device_list)} 个CAN设备")
        else:
            self.log_message("未扫描到CAN设备")
        
        # 更新所有工位的CAN SN下拉菜单
        updated_count = 0
        
        for station_key, entries in self.hardware_entries.items():
            if "can_sn" in entries:
                combobox = entries["can_sn"]
                
                # 检查combobox是否已经完全初始化
                if combobox:
                    # 设置下拉菜单值
                    combobox['values'] = device_list
                    # 如果没有设备，显示提示信息
                    if not device_list:
                        combobox.set("未检测到设备")
                    # 否则保持当前选择或设置为第一个设备
                    elif not combobox.get() or combobox.get() not in device_list:
                        combobox.set(device_list[0] if device_list else "请选择设备")
                    updated_count += 1
        
        self.log_message(f"已更新 {updated_count} 个工位的CAN SN下拉菜单")
        self.log_message("CAN设备列表刷新完成")
    
    def refresh_can_devices(self, max_retries=3, retry_delay=1.0):
        """刷新CAN设备列表
        
        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            
        Returns:
            list: 设备列表，每个元素是设备显示名称
            dict: 设备信息映射，键是设备显示名称，值是设备句柄
        """
        device_list = []
        device_info = {}
        
        try:
            # 检查USB设备模块是否可用
            if not USB2XXXLib_available:
                self.log_message("USB设备模块不可用，无法扫描设备")
                return device_list, device_info
            
            # 尝试扫描设备，最多重试max_retries次
            for retry in range(max_retries):
                self.log_message(f"开始第 {retry+1} 次扫描CAN设备...")
                
                try:
                    # 扫描设备
                    DevHandles = (c_uint * 20)()
                    ret = USB_ScanDevice(byref(DevHandles))
                    
                    if ret == 0:
                        self.log_message(f"第 {retry+1} 次扫描未检测到USB2CAN设备")
                        if retry < max_retries - 1:
                            self.log_message(f"{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            return device_list, device_info
                    
                    self.log_message(f"第 {retry+1} 次扫描检测到 {ret} 个设备")
                    
                    # 遍历设备，获取序列号
                    for i in range(ret):
                        device_handle = DevHandles[i]
                        
                        # 尝试打开设备
                        try:
                            ret_open = USB_OpenDevice(device_handle)
                            
                            if bool(ret_open):
                                # 获取设备信息
                                try:
                                    USB2XXXInfo = DEVICE_INFO()
                                    USB2XXXFunctionString = (c_char * 256)()
                                    ret_info = DEV_GetDeviceInfo(device_handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))
                                    
                                    if bool(ret_info):
                                        # 构建序列号字符串
                                        try:
                                            serial_parts = []
                                            # DEVICE_INFO结构体中的SerialNumber是c_uint*3类型，固定长度为3
                                            for j in range(3):
                                                serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                                            device_serial = ''.join(serial_parts)
                                            
                                            # 获取设备功能
                                            try:
                                                function_string = bytes(USB2XXXFunctionString.value).decode('ascii')
                                                
                                                # 构建设备显示名称
                                                device_name = f"设备{i}: 序列号={device_serial} (功能: {function_string})"
                                                device_list.append(device_name)
                                                device_info[device_name] = device_handle
                                                
                                                self.log_message(f"发现设备: {device_name}")
                                            except Exception as e:
                                                self.log_message(f"解析设备功能错误: {str(e)}")
                                        except Exception as e:
                                            self.log_message(f"构建序列号错误: {str(e)}")
                                    else:
                                        self.log_message(f"设备{i}获取信息失败")
                                except Exception as e:
                                    self.log_message(f"获取设备信息错误: {str(e)}")
                                finally:
                                    # 关闭设备
                                    try:
                                        USB_CloseDevice(device_handle)
                                    except Exception as e:
                                        self.log_message(f"关闭设备{i}错误: {str(e)}")
                            else:
                                self.log_message(f"设备{i}打开失败")
                        except Exception as e:
                            self.log_message(f"设备{i}操作错误: {str(e)}")
                    
                    # 如果成功扫描到设备，跳出重试循环
                    if device_list:
                        break
                    elif retry < max_retries - 1:
                        self.log_message(f"未发现可用设备，{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                except Exception as e:
                    self.log_message(f"第 {retry+1} 次扫描错误: {str(e)}")
                    if retry < max_retries - 1:
                        self.log_message(f"{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
        
        except Exception as e:
            self.log_message(f"刷新设备列表错误: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return device_list, device_info
    
    def show_details_popup(self, record):
        """Show detailed test data in a popup window"""
        popup = tk.Toplevel(self.root)
        popup.title(f"测试详情 - ID: {record['id']}")
        popup.geometry("800x600")
        
        # Header Info
        header_frame = ttk.Frame(popup)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(header_frame, text=f"测试时间: {record['completion_time']}", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky="w", padx=10)
        tk.Label(header_frame, text=f"产品: {record['product_model']}", font=('Arial', 10)).grid(row=0, column=1, sticky="w", padx=10)
        tk.Label(header_frame, text=f"工位: {record['station_id']}", font=('Arial', 10)).grid(row=0, column=2, sticky="w", padx=10)
        tk.Label(header_frame, text=f"条码: {record['scan_result']}", font=('Arial', 10)).grid(row=0, column=3, sticky="w", padx=10)
        
        # Details Table
        detail_frame = ttk.Frame(popup)
        detail_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("项目", "结果/数值")
        tree = ttk.Treeview(detail_frame, columns=columns, show="headings")
        tree.heading("项目", text="项目")
        tree.heading("结果/数值", text="结果/数值")
        tree.column("项目", width=300)
        tree.column("结果/数值", width=400)
        
        vsb = ttk.Scrollbar(detail_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Populate Details
        details = record.get('details', {})
        # Map indices to names if possible
        # We can use self.items_data to map index to name
        
        # Convert items_data to dict for easy lookup
        items_map = {item[0]: item[1] for item in self.items_data}
        
        # Sort keys numerically if they are numbers
        sorted_keys = []
        for k in details.keys():
            try:
                sorted_keys.append(int(k))
            except:
                pass
        sorted_keys.sort()
        
        for k in sorted_keys:
            name = items_map.get(k, f"Item {k}")
            value = details.get(str(k), "")
            
            tag = 'normal'
            if "FAIL" in str(value):
                tag = 'fail'
            elif "PASS" in str(value):
                tag = 'pass'
                
            tree.insert("", "end", values=[name, value], tags=(tag,))
            
        tree.tag_configure('fail', foreground='red')
        tree.tag_configure('pass', foreground='green')
        
        # Add Close Button
        btn_close = ttk.Button(popup, text="关闭", command=popup.destroy)
        btn_close.pack(pady=10)
    
    def __init__(self, root):
        """初始化测试监控UI"""
        self.root = root
        self.root.title("德鑫指控低压PTC综测老化设备")
        # Set to zoomed state (maximized) to fit screen and respect taskbar
        self.root.state('zoomed')
        
        # Set Icon
        try:
            if os.path.exists("win11_logo.ico"):
                self.root.iconbitmap("win11_logo.ico")
        except Exception as e:
            print(f"Failed to set icon: {e}")

        # Configure global grid weights
        # Row 0: Notebook (Main content) - Weight 2 (Expand)
        # Row 1: Log Area - Weight 1 (More visible)
        self.root.grid_rowconfigure(0, weight=2)
        self.root.grid_rowconfigure(1, weight=1, minsize=200)  # Minimum height 200px
        self.root.grid_columnconfigure(0, weight=1)
        
        # Storage for status cells: (station_idx, item_idx) -> Label widget
        self.status_cells = {}
        
        # Callbacks
        self.start_callback = None
        self.stop_callback = None
        self.calibration_start_callback = None
        self.calibration_stop_callback = None

        # Load config
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            self.config_file = os.path.join(base_dir, "config.json")
        else:
            self.config_file = "config.json"
            
        self.load_config()
        
        # 存储默认列宽，用于恢复
        self.default_column_widths = {
            "time": 140,
            "product": 100,
            "barcode": 120,
            "label_qr": 150,
            "station": 50,
            "result": 60
        }
        
        # Current User State
        self.current_user = None # None means logged out
        self.current_role = None

        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # --- Tab 1: Test Page ---
        self.test_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.test_frame, text='测试页面')
        
        # --- Tab 2: Settings Page ---
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text='设置页面')
        
        # --- Tab 3: Query Page ---
        self.query_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.query_frame, text='查询页面')
        
        self.items_data = [
             (0, "等待", "准备就绪"), 
             (1, "工作电压", "Waiting..."), 
             (2, "工作电流", "Waiting..."), 
             (3, "100%功率", "Waiting..."), 
             (4, "100%功率反馈电压", "Waiting..."), 
             (5, "100%功率反馈电流", "Waiting..."), 
             (6, "0%功率", "Waiting..."), 
             (7, "80%功率", "Waiting..."), 
             (8, "80%功率反馈电压", "Waiting..."), 
             (9, "80%功率反馈电流", "Waiting..."), 
             (10, "0%功率", "Waiting..."), 
             (11, "60%功率", "Waiting..."), 
             (12, "60%功率反馈电压", "Waiting..."), 
             (13, "60%功率反馈电流", "Waiting..."), 
             (14, "0%功率", "Waiting..."), 
             (15, "40%功率", "Waiting..."), 
             (16, "40%功率反馈电压", "Waiting..."), 
             (17, "40%功率反馈电流", "Waiting..."), 
             (18, "0%功率", "Waiting..."), 
             (19, "温度", "Waiting..."), 
             (20, "CAN设备状态", "Waiting..."), 
             (21, "测试倒计时", "Waiting..."), 
             (22, "标签二维码", "Waiting..."), 
             (23, "测试结果", "Waiting..."), 
        ]
        
        # --- Tab 4: Calibration Page ---
        self.calibration_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.calibration_frame, text='电压校准')
        
        # --- Tab 5: Manual Test Page ---
        self.manual_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_frame, text='手动诊断')
        
        # --- Tab 6: Data Visualization Page ---
        self.visualization_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.visualization_frame, text='数据可视化')
        
        # Define columns headers
        self.headers = ["序号", "项目"] + [f"测试 {i}" for i in range(1, 11)]
        
        # Build the UIs
        # Create Log UI first to avoid AttributeError when other methods fail
        self.create_log_ui()
        
        self.create_grid_ui()
        self.create_settings_ui()
        
        # Create Query UI last because it depends on items_data which is defined above but create_query_ui was moved to bottom class definition
        self.create_query_ui()
    
    def on_tree_motion(self, event):
        """Handle mouse motion over tree items to adjust column width for full content display"""
        # Get the item and column under the mouse cursor
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        if item and column:
            # Get the column index
            col_idx = int(column.replace('#', '')) - 1
            
            # Get the cell value
            values = self.tree.item(item, 'values')
            if values and col_idx < len(values):
                # Get value and ensure it's a string
                value = values[col_idx]
                value_str = str(value) if value is not None else ""
                
                # Get the column ID
                col_id = self.tree['columns'][col_idx]
                
                # Calculate required width (approx 8px per character for default font)
                # Use minimum width from default settings or 100px as fallback
                min_width = self.default_column_widths.get(col_id, 100)
                required_width = max(min_width, len(value_str) * 8 + 20)  # Minimum width, plus padding
                
                # Adjust column width
                self.tree.column(col_id, width=required_width)
            else:
                # Restore column widths when not over a valid cell
                self.restore_column_widths()
        else:
            # Restore column widths when mouse leaves tree
            self.restore_column_widths()
    
    def on_tree_leave(self, event):
        """Handle mouse leaving the tree widget"""
        self.restore_column_widths()
    
    def restore_column_widths(self):
        """Restore default column widths"""
        # Restore all columns to their default widths
        for col_id, width in self.default_column_widths.items():
            try:
                self.tree.column(col_id, width=width, anchor="center")
            except:
                pass

# 导入必要的对话框类
from date_picker import DatePickerDialog

# 导入登录相关的对话框类
from login_dialog import LoginDialog, UserManagementDialog, ChangePasswordDialog

# 临时注释掉DateTimePickerDialog导入，使用DatePickerDialog代替
# from date_time_picker import DateTimePickerDialog

# 启动应用程序
if __name__ == "__main__":
    root = tk.Tk()
    app = TestMonitorUI(root)
    root.mainloop()