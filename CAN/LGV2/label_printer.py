import tkinter as tk
from tkinter import ttk, messagebox
import qrcode
from PIL import Image, ImageTk
import datetime
import os
import tempfile
from tkinter import font
import json
import logging

# 创建logger
logger = logging.getLogger("LGV2")

# 跨平台兼容性检查
is_windows = os.name == 'nt'

if is_windows:
    try:
        import win32print
        import win32ui
        import win32con
        import win32gui
        from PIL import ImageWin
        windows_print_supported = True
    except ImportError:
        windows_print_supported = False
else:
    windows_print_supported = False

class LabelPrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("产品标签打印机")
        self.root.geometry("1000x750")
        self.root.resizable(True, True)
        
        # 固定文本内容
        self.product_name = "PTC assembly"
        self.specifications = "1000W/13VDC"
        self.version = "HW0.0.1 SW00.00.01"
        self.p_no = "AA061000"
        self.part_number = "H081683084"
        
        # 序列号存储
        self.serial_numbers = {}

        # 调整参数状态
        self.text_scale_factor = 1.0
        self.line_spacing_delta = 0
        self.text_x_offset = 0
        self.text_y_offset = 0
        self.qr_size_delta = 0  # 像素增量
        self.qr_x_offset = 0
        self.qr_y_offset = 0
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建输入区域
        self.input_frame = ttk.LabelFrame(self.main_frame, text="输入设置", padding="10")
        self.input_frame.pack(fill=tk.X, pady=10)
        
        # 工位号输入
        ttk.Label(self.input_frame, text="工位号 (2位数字):").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.station_var = tk.StringVar()
        self.station_entry = ttk.Entry(self.input_frame, textvariable=self.station_var, width=10)
        self.station_entry.grid(row=0, column=1, padx=10, pady=5)
        
        # 打印数量设置
        ttk.Label(self.input_frame, text="打印数量:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        self.print_count_var = tk.IntVar(value=1)
        self.print_count_spinbox = ttk.Spinbox(self.input_frame, from_=1, to=999, textvariable=self.print_count_var, width=10)
        self.print_count_spinbox.grid(row=1, column=1, padx=10, pady=5)
        
        # 创建预览和控制区域
        self.preview_control_frame = ttk.Frame(self.main_frame)
        self.preview_control_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 调整布局顺序：先创建右侧面板以确保其固定在右侧，再创建左侧预览区域填充剩余空间
        
        # 右侧：控制面板（包含操作和微调）
        self.right_panel = ttk.Frame(self.preview_control_frame, width=200)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.right_panel.pack_propagate(False)  # 防止内部组件影响面板宽度

        # 左侧：预览区域
        self.preview_frame = ttk.LabelFrame(self.preview_control_frame, text="标签预览", padding="10")
        self.preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建预览画布
        self.preview_canvas = tk.Canvas(self.preview_frame, width=400, height=200, bg="white")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Configure>", self.update_preview)
        
        # 1. 操作区域
        self.control_frame = ttk.LabelFrame(self.right_panel, text="操作", padding="10")
        self.control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 生成按钮
        self.generate_btn = ttk.Button(self.control_frame, text="生成标签", command=self.generate_label)
        self.generate_btn.pack(pady=5, fill=tk.X)
        
        # 打印按钮
        self.print_btn = ttk.Button(self.control_frame, text="打印", command=self.print_label)
        self.print_btn.pack(pady=5, fill=tk.X)
        
        # 打印机设置按钮 (解决走纸/大小问题)
        self.props_btn = ttk.Button(self.control_frame, text="打印机属性 (解决走纸问题)", command=self.open_printer_props)
        self.props_btn.pack(pady=5, fill=tk.X)

        # DPI 设置
        dpi_frame = ttk.Frame(self.control_frame)
        dpi_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dpi_frame, text="强制DPI:").pack(side=tk.LEFT)
        self.dpi_var = tk.IntVar(value=203)
        self.dpi_combo = ttk.Combobox(dpi_frame, textvariable=self.dpi_var, values=[96, 203, 300, 600], width=5)
        self.dpi_combo.pack(side=tk.RIGHT)
        
        # 保存设置按钮
        self.save_btn = ttk.Button(self.control_frame, text="保存设置", command=self.save_settings)
        self.save_btn.pack(pady=5, fill=tk.X)
        
        # 退出按钮
        self.exit_btn = ttk.Button(self.control_frame, text="退出", command=self.root.quit)
        self.exit_btn.pack(pady=5, fill=tk.X)

        # 2. 微调区域
        self.adjust_frame = ttk.LabelFrame(self.right_panel, text="布局微调", padding="10")
        self.adjust_frame.pack(fill=tk.X, pady=5)

        # 辅助函数：创建控制组
        def create_control_group(parent, title, prefix, update_func):
            frame = ttk.LabelFrame(parent, text=title, padding="5")
            frame.pack(fill=tk.X, pady=5)
            
            # 大小控制
            size_frame = ttk.Frame(frame)
            size_frame.pack(fill=tk.X, pady=2)
            ttk.Label(size_frame, text="大小:").pack(side=tk.LEFT)
            ttk.Button(size_frame, text="-", width=3, command=lambda: update_func(prefix, 'size', -1)).pack(side=tk.RIGHT)
            ttk.Button(size_frame, text="+", width=3, command=lambda: update_func(prefix, 'size', 1)).pack(side=tk.RIGHT, padx=2)

            # 位置控制
            pos_frame = ttk.Frame(frame)
            pos_frame.pack(fill=tk.X, pady=2)
            
            # 上下左右布局
            btn_grid = ttk.Frame(pos_frame)
            btn_grid.pack(anchor=tk.CENTER)
            
            ttk.Button(btn_grid, text="↑", width=3, command=lambda: update_func(prefix, 'y', -2)).grid(row=0, column=1)
            ttk.Button(btn_grid, text="←", width=3, command=lambda: update_func(prefix, 'x', -2)).grid(row=1, column=0)
            ttk.Button(btn_grid, text="↓", width=3, command=lambda: update_func(prefix, 'y', 2)).grid(row=1, column=1)
            ttk.Button(btn_grid, text="→", width=3, command=lambda: update_func(prefix, 'x', 2)).grid(row=1, column=2)

        # 创建文字微调 (自定义，包含间距)
        text_frame = ttk.LabelFrame(self.adjust_frame, text="文字设置", padding="5")
        text_frame.pack(fill=tk.X, pady=5)

        # 文字大小 (Scale 2%)
        t_size_frame = ttk.Frame(text_frame)
        t_size_frame.pack(fill=tk.X, pady=2)
        ttk.Label(t_size_frame, text="大小(2%):").pack(side=tk.LEFT)
        ttk.Button(t_size_frame, text="-", width=3, command=lambda: self.adjust_layout('text', 'scale', -0.02)).pack(side=tk.RIGHT)
        ttk.Button(t_size_frame, text="+", width=3, command=lambda: self.adjust_layout('text', 'scale', 0.02)).pack(side=tk.RIGHT, padx=2)

        # 文字间距
        t_space_frame = ttk.Frame(text_frame)
        t_space_frame.pack(fill=tk.X, pady=2)
        ttk.Label(t_space_frame, text="间距:").pack(side=tk.LEFT)
        ttk.Button(t_space_frame, text="-", width=3, command=lambda: self.adjust_layout('text', 'spacing', -1)).pack(side=tk.RIGHT)
        ttk.Button(t_space_frame, text="+", width=3, command=lambda: self.adjust_layout('text', 'spacing', 1)).pack(side=tk.RIGHT, padx=2)

        # 文字位置
        t_pos_frame = ttk.Frame(text_frame)
        t_pos_frame.pack(fill=tk.X, pady=2)
        t_btn_grid = ttk.Frame(t_pos_frame)
        t_btn_grid.pack(anchor=tk.CENTER)
        ttk.Button(t_btn_grid, text="↑", width=3, command=lambda: self.adjust_layout('text', 'y', -2)).grid(row=0, column=1)
        ttk.Button(t_btn_grid, text="←", width=3, command=lambda: self.adjust_layout('text', 'x', -2)).grid(row=1, column=0)
        ttk.Button(t_btn_grid, text="↓", width=3, command=lambda: self.adjust_layout('text', 'y', 2)).grid(row=1, column=1)
        ttk.Button(t_btn_grid, text="→", width=3, command=lambda: self.adjust_layout('text', 'x', 2)).grid(row=1, column=2)
        
        # 创建二维码微调
        qr_frame = ttk.LabelFrame(self.adjust_frame, text="二维码设置", padding="5")
        qr_frame.pack(fill=tk.X, pady=5)
        
        # 二维码大小
        qr_size_frame = ttk.Frame(qr_frame)
        qr_size_frame.pack(fill=tk.X, pady=2)
        ttk.Label(qr_size_frame, text="大小:").pack(side=tk.LEFT)
        ttk.Button(qr_size_frame, text="-", width=3, command=lambda: self.adjust_layout('qr', 'size', -1)).pack(side=tk.RIGHT)
        ttk.Button(qr_size_frame, text="+", width=3, command=lambda: self.adjust_layout('qr', 'size', 1)).pack(side=tk.RIGHT, padx=2)
        
        # 二维码位置
        qr_pos_frame = ttk.Frame(qr_frame)
        qr_pos_frame.pack(fill=tk.X, pady=2)
        qr_btn_grid = ttk.Frame(qr_pos_frame)
        qr_btn_grid.pack(anchor=tk.CENTER)
        ttk.Button(qr_btn_grid, text="↑", width=3, command=lambda: self.adjust_layout('qr', 'y', -2)).grid(row=0, column=1)
        ttk.Button(qr_btn_grid, text="←", width=3, command=lambda: self.adjust_layout('qr', 'x', -2)).grid(row=1, column=0)
        ttk.Button(qr_btn_grid, text="↓", width=3, command=lambda: self.adjust_layout('qr', 'y', 2)).grid(row=1, column=1)
        ttk.Button(qr_btn_grid, text="→", width=3, command=lambda: self.adjust_layout('qr', 'x', 2)).grid(row=1, column=2)
        
        # 状态信息
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=10)

        # 提示用户调整打印机设置
        self.tips_label = ttk.Label(self.main_frame, text="提示: 若打印大小不正确或走纸异常，请点击'打印机设置'调整", foreground="red")
        self.tips_label.pack(fill=tk.X, padx=10)
        
        # 绑定事件
        self.station_var.trace_add("write", lambda *args: self.update_preview())
        self.print_count_var.trace_add("write", lambda *args: self.update_preview())
        
        # 加载设置
        self.load_settings()

    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists("printer_config.json"):
                with open("printer_config.json", "r") as f:
                    settings = json.load(f)
                    self.text_scale_factor = settings.get("text_scale_factor", 1.0)
                    self.line_spacing_delta = settings.get("line_spacing_delta", 0)
                    self.text_x_offset = settings.get("text_x_offset", 0)
                    self.text_y_offset = settings.get("text_y_offset", 0)
                    self.qr_size_delta = settings.get("qr_size_delta", 0)
                    self.qr_x_offset = settings.get("qr_x_offset", 0)
                    self.qr_y_offset = settings.get("qr_y_offset", 0)
                    # 还可以加载上次的工位号
                    self.station_var.set(settings.get("station_id", ""))
                    self.dpi_var.set(settings.get("dpi", 203))
        except Exception as e:
            print(f"加载设置失败: {e}")

    def save_settings(self):
        """保存设置"""
        try:
            settings = {
                "text_scale_factor": self.text_scale_factor,
                "line_spacing_delta": self.line_spacing_delta,
                "text_x_offset": self.text_x_offset,
                "text_y_offset": self.text_y_offset,
                "qr_size_delta": self.qr_size_delta,
                "qr_x_offset": self.qr_x_offset,
                "qr_y_offset": self.qr_y_offset,
                "station_id": self.station_var.get(),
                "dpi": self.dpi_var.get()
            }
            with open("printer_config.json", "w") as f:
                json.dump(settings, f, indent=4)
            messagebox.showinfo("成功", "设置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {str(e)}")

    def adjust_layout(self, target, attr, delta):
        """处理布局调整"""
        if target == 'text':
            if attr == 'scale':
                self.text_scale_factor += delta
                # 限制最小缩放
                if self.text_scale_factor < 0.1:
                    self.text_scale_factor = 0.1
            elif attr == 'spacing':
                self.line_spacing_delta += delta
            elif attr == 'x':
                self.text_x_offset += delta
            elif attr == 'y':
                self.text_y_offset += delta
        elif target == 'qr':
            if attr == 'size':
                self.qr_size_delta += delta * 5 # 二维码调整步长稍大
            elif attr == 'x':
                self.qr_x_offset += delta
            elif attr == 'y':
                self.qr_y_offset += delta
        
        self.update_preview()
        
    def open_printer_props(self):
        """打开打印机属性对话框"""
        try:
            printer_name = win32print.GetDefaultPrinter()
            h_printer = win32print.OpenPrinter(printer_name)
            try:
                # 调用 DocumentProperties 显示配置对话框
                # hWnd, hPrinter, pDeviceName, pDevModeOutput, pDevModeInput, fMode
                win32print.DocumentProperties(int(self.root.winfo_id()), h_printer, printer_name, None, None, 14) # DM_IN_BUFFER | DM_OUT_BUFFER | DM_IN_PROMPT = 14
            finally:
                win32print.ClosePrinter(h_printer)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开打印机属性: {str(e)}")

    def generate_batch_number(self, station_id):
        """生成批次号"""
        if not station_id or len(station_id) != 2 or not station_id.isdigit():
            raise ValueError("工位号必须是2位数字")
        
        # 获取当前日期（8位，YYYYMMDD）
        today = datetime.datetime.now()
        date_str = today.strftime("%Y%m%d")
        
        # 生成序列号 - 每天重置，所有工位共用一个序号
        data_dir = "d:\\data"
        seq_file = os.path.join(data_dir, f"batch_seq_{date_str}.txt")
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # 读取当天序号
        if os.path.exists(seq_file):
            with open(seq_file, "r") as f:
                try:
                    current_seq = int(f.read().strip())
                except:
                    current_seq = 0
        else:
            current_seq = 0
        
        # 增加序号
        current_seq += 1
        
        # 保存序号
        with open(seq_file, "w") as f:
            f.write(str(current_seq))
        
        serial_number = f"{current_seq:04d}"
        
        # 组合批次号
        batch_number = f"{station_id}{date_str}{serial_number}"
        return batch_number
    
    def generate_qr_code(self, data):
        """生成二维码"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        return img
    
    def update_preview(self, event=None):
        """更新预览"""
        try:
            station_id = self.station_var.get()
            if not station_id or len(station_id) != 2 or not station_id.isdigit():
                return
            
            # 生成批次号
            batch_number = self.generate_batch_number(station_id)
            
            # 生成二维码内容
            qr_content = f"{self.part_number}{batch_number}"
            
            # 生成二维码
            qr_img = self.generate_qr_code(qr_content)
            
            # 调整二维码大小
            # 预览时先不resize，等到计算出布局后再resize
            # qr_img = qr_img.resize((100, 100)) 
            
            # 清空画布
            self.preview_canvas.delete("all")
            
            # 绘制标签边框 (40mm x 20mm 的比例)
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            # 如果画布尚未显示（宽度为1），使用默认大小
            if canvas_width <= 1:
                canvas_width = 400
                canvas_height = 200
            
            label_width = canvas_width * 0.8
            label_height = label_width * 0.5  # 40x20mm = 2:1比例
            x0 = (canvas_width - label_width) / 2
            y0 = (canvas_height - label_height) / 2
            x1 = x0 + label_width
            y1 = y0 + label_height
            
            self.preview_canvas.create_rectangle(x0, y0, x1, y1, outline="black", width=1)
            
            # 设置字体
            base_font_size = int(10 * self.text_scale_factor) # 缩小基础字体以适应6行文本
            # 所有字体加粗
            normal_font = font.Font(size=base_font_size, weight="bold")
            bold_font = font.Font(size=base_font_size, weight="bold")
            
            # 绘制文本内容
            # 计算文本总高度以垂直居中
            # 行高随字体缩放 + 间距调整
            line_height = int(18 * self.text_scale_factor) + self.line_spacing_delta # 减小行高
            num_lines = 6
            total_text_height = num_lines * line_height
            
            # 文字区域占据左侧 55%
            text_section_width = label_width * 0.55
            
            # 垂直居中起始 Y 坐标
            text_start_y = y0 + (label_height - total_text_height) / 2
            text_x = x0 + 20 + self.text_x_offset # 应用水平偏移
            text_y = text_start_y + self.text_y_offset # 应用垂直偏移
            
            self.preview_canvas.create_text(text_x, text_y, text=f"Product name: {self.product_name}", anchor=tk.W, font=normal_font)
            text_y += line_height
            self.preview_canvas.create_text(text_x, text_y, text=f"Specifications: {self.specifications}", anchor=tk.W, font=normal_font)
            text_y += line_height
            self.preview_canvas.create_text(text_x, text_y, text=f"Part number: {self.part_number}", anchor=tk.W, font=bold_font)
            text_y += line_height
            self.preview_canvas.create_text(text_x, text_y, text=f"Version: {self.version}", anchor=tk.W, font=normal_font)
            text_y += line_height
            self.preview_canvas.create_text(text_x, text_y, text=f"Batch number: {batch_number}", anchor=tk.W, font=bold_font)
            text_y += line_height
            self.preview_canvas.create_text(text_x, text_y, text=f"P/NO: {self.p_no}", anchor=tk.W, font=normal_font)
            
            # 绘制二维码 - 右侧 45% 区域居中
            qr_section_start_x = x0 + text_section_width
            qr_section_width = label_width * 0.45
            
            # 计算二维码在预览中的显示尺寸 (确保适应区域，最大化)
            qr_display_size = min(qr_section_width * 0.95, label_height * 0.95)
            qr_display_size = int(qr_display_size) + self.qr_size_delta
            
            # 重新调整预览用的二维码大小
            if qr_display_size < 10: qr_display_size = 10 # 最小尺寸保护
            
            # 使用 NEAREST 算法保持二维码边缘锐利，避免模糊
            preview_qr_img = qr_img.resize((qr_display_size, qr_display_size), Image.Resampling.NEAREST)
            self.qr_photo = ImageTk.PhotoImage(preview_qr_img)
            
            # 计算居中坐标
            qr_x = qr_section_start_x + (qr_section_width - qr_display_size) / 2 + self.qr_x_offset
            qr_y = y0 + (label_height - qr_display_size) / 2 + self.qr_y_offset
            
            self.preview_canvas.create_image(qr_x, qr_y, anchor=tk.NW, image=self.qr_photo)
            
            # 更新状态
            self.status_var.set(f"就绪 - 批次号: {batch_number}")
            
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
    
    def generate_label(self):
        """生成标签"""
        try:
            station_id = self.station_var.get()
            if not station_id or len(station_id) != 2 or not station_id.isdigit():
                messagebox.showerror("错误", "请输入有效的2位数字工位号")
                return
            
            self.update_preview()
            messagebox.showinfo("成功", "标签生成成功")
            
        except Exception as e:
            messagebox.showerror("错误", f"生成标签失败: {str(e)}")
    
    def print_label(self, label_data=None):
        """打印标签
        
        Args:
            label_data: 标签数据字典，包含以下字段：
                - station: 工位号
                - product: 产品名称
                - sn: 序列号
                - time: 时间
                - result: 测试结果
                - part_number: 部件号（可选）
        
        Returns:
            str: 二维码内容
        """
        try:
            logger.info(f"=== Label printer print_label called with data: {label_data} ===")
            
            # 如果提供了外部数据，使用外部数据
            if label_data:
                station_id = str(label_data.get('station', '01')).zfill(2)
                scan_result = label_data.get('sn', '')
                product_name = label_data.get('product', self.product_name)
                # 使用提供的part_number或默认值
                part_number = label_data.get('part_number', self.part_number)
                logger.info(f"Using external data - Station: {station_id}, Product: {product_name}, Part Number: {part_number}")
            else:
                # 从UI控件获取数据
                station_id = self.station_var.get()
                if not station_id or len(station_id) != 2 or not station_id.isdigit():
                    messagebox.showerror("错误", "请输入有效的2位数字工位号")
                    return None
                scan_result = ""
                product_name = self.product_name
                part_number = self.part_number
                logger.info(f"Using UI data - Station: {station_id}, Product: {product_name}, Part Number: {part_number}")
            
            print_count = self.print_count_var.get()
            logger.info(f"Print count: {print_count}")
            
            # 生成批次号
            logger.info(f"Generating batch number for station {station_id}")
            batch_number = self.generate_batch_number(station_id)
            logger.info(f"Generated batch number: {batch_number}")
            
            # 生成二维码内容 - 使用 part_number + 批次号
            qr_content = f"{part_number}{batch_number}"
            logger.info(f"Generated QR content: {qr_content}")
            
            # 确保d:\data目录存在
            data_dir = "d:\\data"
            if not os.path.exists(data_dir):
                logger.info(f"Creating data directory: {data_dir}")
                os.makedirs(data_dir)
            
            # 保存文本信息到label.txt（按要求的格式）
            label_text = f"Product name: {product_name}\n"
            label_text += f"Specifications: {self.specifications}\n"
            label_text += f"Part number: {part_number}\n"
            label_text += f"Version: {self.version}\n"
            label_text += f"Batch number: {batch_number}\n"
            label_text += f"P/NO: {self.p_no}\n"
            
            label_file = os.path.join(data_dir, "label.txt")
            logger.info(f"Saving label.txt to: {label_file}")
            with open(label_file, "w", encoding="utf-8") as f:
                f.write(label_text)
            logger.info(f"label.txt saved successfully")
            
            # 保存二维码信息到barcode.txt
            barcode_file = os.path.join(data_dir, "barcode.txt")
            logger.info(f"Saving barcode.txt to: {barcode_file}")
            with open(barcode_file, "w", encoding="utf-8") as f:
                f.write(qr_content)
            logger.info(f"barcode.txt saved successfully")
            
            # 调用BarTender打印
            bartender_path = "C:\\Program Files\\Seagull\\BarTender Suite\\bartend.exe"
            btw_file = os.path.join(data_dir, "label.btw")
            
            if os.path.exists(bartender_path):
                logger.info(f"BarTender found at: {bartender_path}")
                import subprocess
                # 构建命令
                command = f'"{bartender_path}" /P /X "{btw_file}"'
                logger.info(f"Executing BarTender command: {command}")
                # 执行命令
                subprocess.run(command, shell=True)
                
                # 更新状态
                if hasattr(self, 'status_var'):
                    self.status_var.set(f"已通过BarTender打印 {print_count} 份标签")
                if not label_data:  # 只有从UI调用时才显示消息框
                    messagebox.showinfo("打印", f"成功通过BarTender打印标签")
                logger.info(f"Label printed via BarTender for station {station_id}")
            else:
                # BarTender未安装
                logger.warning(f"BarTender not found at: {bartender_path}")
                if not label_data:  # 只有从UI调用时才显示消息框
                    messagebox.showwarning("警告", "BarTender未找到。标签信息已保存，但无法自动打印。")
                if hasattr(self, 'status_var'):
                    self.status_var.set("BarTender未找到，标签信息已保存")
                logger.warning(f"BarTender not found, label info saved for station {station_id}")
            
            # 返回二维码内容
            logger.info(f"=== Label printing completed successfully for station {station_id}, returning QR content: {qr_content} ===")
            return qr_content
        except Exception as e:
            error_msg = f"打印失败: {str(e)}"
            logger.error(f"=== Label printing failed: {error_msg} ===")
            import traceback
            traceback.print_exc()
            if not label_data:  # 只有从UI调用时才显示消息框
                messagebox.showerror("错误", error_msg)
            # 抛出异常，以便上层调用者能够捕获
            raise
    
    def _print_image(self, image_path):
        """打印图像"""
        h_printer = None
        try:
            # 获取默认打印机
            printer_name = win32print.GetDefaultPrinter()
            
            # 直接使用默认打印机配置，不强制修改 DEVMODE
            # 因为强制修改可能会导致打印机重新校准(走纸)或参数不匹配
            
            # 创建设备上下文
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(printer_name)
            
            # 开始打印作业
            hDC.StartDoc(image_path)
            hDC.StartPage()
            
            # 打开图像
            bmp = Image.open(image_path)
            dib = ImageWin.Dib(bmp)
            
            # 计算打印位置和大小 (确保严格按照 40mm x 20mm 打印)
            # 优先使用用户设置的 DPI，否则获取打印机 DPI
            user_dpi = self.dpi_var.get()
            if user_dpi > 0:
                dpi_x = user_dpi
                dpi_y = user_dpi
            else:
                dpi_x = hDC.GetDeviceCaps(win32con.LOGPIXELSX)
                dpi_y = hDC.GetDeviceCaps(win32con.LOGPIXELSY)
            
            # 目标尺寸: 40mm x 20mm
            # 1 inch = 25.4 mm
            target_width_px = int(40 / 25.4 * dpi_x)
            target_height_px = int(20 / 25.4 * dpi_y)
            
            # 打印图像 (缩放至目标物理尺寸)
            dib.draw(hDC.GetHandleOutput(), (0, 0, target_width_px, target_height_px))
            
            # 结束打印作业
            hDC.EndPage()
            hDC.EndDoc()
            
            # 清理
            win32gui.DeleteDC(hDC.GetHandleOutput())
            
        except Exception as e:
            raise Exception(f"打印失败: {str(e)}")
        finally:
            if h_printer:
                win32print.ClosePrinter(h_printer)

if __name__ == "__main__":
    root = tk.Tk()
    app = LabelPrinter(root)
    root.mainloop()
