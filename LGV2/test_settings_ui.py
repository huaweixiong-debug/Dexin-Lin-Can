#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试设置页面中的新开关
"""

import tkinter as tk
from test_monitor_ui import TestMonitorUI
import json
import os

def test_settings_ui():
    """测试设置页面UI"""
    print("测试设置页面UI...")
    
    # 创建根窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    # 创建UI实例
    ui = TestMonitorUI(root)
    
    # 创建设置页面UI
    print("创建设置页面UI...")
    ui.create_settings_ui()
    
    # 检查新增的开关变量是否存在
    if hasattr(ui, 'scan_start_var'):
        print(f"  ✓ scan_start_var 存在: {ui.scan_start_var.get()}")
    else:
        print("  ✗ scan_start_var 不存在")
        
    if hasattr(ui, 'print_label_qr_var'):
        print(f"  ✓ print_label_qr_var 存在: {ui.print_label_qr_var.get()}")
    else:
        print("  ✗ print_label_qr_var 不存在")
    
    # 检查配置文件中是否保存了这些设置
    config_file = ui.config_file
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"  配置文件中的 scan_start: {config.get('scan_start', '未设置')}")
        print(f"  配置文件中的 print_label_qr: {config.get('print_label_qr', '未设置')}")
    else:
        print("  ✗ 配置文件不存在")
    
    # 销毁根窗口
    root.destroy()
    print("✓ 测试完成")

if __name__ == "__main__":
    print("=" * 60)
    print("测试设置页面中的新开关")
    print("=" * 60)
    print()
    
    test_settings_ui()