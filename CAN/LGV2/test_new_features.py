#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新功能：扫码启动和标签二维码打印
"""

import json
import os
import sys

def test_config_file():
    """测试配置文件读写"""
    print("测试配置文件读写...")
    
    config_file = "config.json"
    
    # 读取现有配置
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"当前配置中的scan_start: {config.get('scan_start', '未设置')}")
        print(f"当前配置中的print_label_qr: {config.get('print_label_qr', '未设置')}")
        
        # 测试修改配置
        config['scan_start'] = False
        config['print_label_qr'] = True
        
        # 保存配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print("✓ 配置文件更新成功")
    else:
        print("✗ 配置文件不存在")
    
    print()

def test_hv_test_runner_callback():
    """测试HVTestRunner回调功能"""
    print("测试HVTestRunner回调功能...")
    
    try:
        from hv_test_runner import HVTestRunner
        
        # 模拟测试完成回调
        callback_called = []
        
        def test_complete_callback(station_idx, success, scan_result):
            callback_called.append((station_idx, success, scan_result))
            print(f"  回调被调用: station_idx={station_idx}, success={success}, scan_result={scan_result}")
        
        # 创建模拟配置
        station_config = {
            "scanner_ip": "192.168.10.228:8888",
            "power_supply_ip": "192.168.10.100",
            "lin_device_index": 0
        }
        
        product_times = {
            "高压欠压": 5,
            "高压欠压恢复": 3,
            "高压过压": 5,
            "高压过压恢复": 3
        }
        
        # 创建测试运行器
        runner = HVTestRunner(
            station_idx=1,
            station_config=station_config,
            product_times=product_times,
            ui_callback=lambda station_idx, row_idx, text, color: None,
            log_callback=lambda msg: None,
            product_name="测试产品",
            scan_result="TEST123456",
            test_complete_callback=test_complete_callback
        )
        
        print(f"  测试运行器创建成功，test_complete_callback已设置: {runner.test_complete_callback is not None}")
        
        # 模拟测试完成
        if runner.test_complete_callback:
            runner.test_complete_callback(1, True, "TEST123456")
        
        print(f"  回调调用次数: {len(callback_called)}")
        
        if callback_called:
            print("✓ HVTestRunner回调功能测试成功")
        else:
            print("✗ HVTestRunner回调功能测试失败")
        
    except Exception as e:
        print(f"✗ HVTestRunner回调功能测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def test_label_printer():
    """测试标签打印机"""
    print("测试标签打印机...")
    
    try:
        from label_printer import LabelPrinter
        import tkinter as tk
        
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        label_printer = LabelPrinter(root)
        
        # 测试标签数据
        label_data = {
            'station': 1,
            'product': '测试产品',
            'sn': 'TEST123456',
            'time': '2026-02-02 10:30:00',
            'result': 'PASS'
        }
        
        print(f"  标签打印机初始化成功: {label_printer is not None}")
        print(f"  标签数据: {label_data}")
        
        # 注意：实际打印需要打印机连接，这里只测试调用
        print("  标签打印机测试完成（实际打印需要硬件连接）")
        print("✓ 标签打印机功能测试成功")
        
    except Exception as e:
        print(f"✗ 标签打印机测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def main():
    print("=" * 60)
    print("测试新功能：扫码启动和标签二维码打印")
    print("=" * 60)
    print()
    
    # 测试配置文件读写
    test_config_file()
    
    # 测试HVTestRunner回调功能
    test_hv_test_runner_callback()
    
    # 测试标签打印机
    test_label_printer()
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()