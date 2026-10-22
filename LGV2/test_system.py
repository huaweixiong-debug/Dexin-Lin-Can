#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试系统功能
"""

import sys
import os
import time
import threading
from logger import logger

def test_scanner():
    """测试扫码枪功能"""
    print("=" * 80)
    print("测试扫码枪功能")
    print("=" * 80)
    
    try:
        from scanner_new import Scanner
        
        # 创建扫码枪实例
        scanner = Scanner('192.168.10.228', port=8888, mode='client')
        
        print("1. 测试连接...")
        if scanner.connect():
            print("✓ 扫码枪连接成功")
        else:
            print("✗ 扫码枪连接失败")
            return False
        
        print("2. 测试扫码...")
        print("   请使用扫码枪扫描条码...")
        result = scanner.scan(timeout=10)
        if result:
            print(f"✓ 扫码成功: {result}")
        else:
            print("✗ 扫码失败或超时")
        
        scanner.disconnect()
        print("3. 扫码枪已断开连接")
        
        return True
        
    except Exception as e:
        print(f"✗ 扫码枪测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_plc_controller():
    """测试PLC控制器功能"""
    print("\n" + "=" * 80)
    print("测试PLC控制器功能")
    print("=" * 80)
    
    try:
        from plc_controller import PLCController
        
        # 创建PLC控制器实例
        plc = PLCController()
        
        print("1. 测试PLC连接...")
        plc.connect()
        
        if plc.connected1 or plc.connected2:
            print("✓ PLC连接成功")
            print(f"   PLC1连接状态: {plc.connected1}")
            print(f"   PLC2连接状态: {plc.connected2}")
        else:
            print("✗ PLC连接失败")
            return False
        
        print("2. 测试PLC状态写入...")
        try:
            # 测试写入扫码OK信号
            plc.write_status(1, 'SCAN_OK', True)
            print("✓ 扫码OK信号写入成功")
            
            # 等待1秒
            time.sleep(1)
            
            # 清除扫码OK信号
            plc.write_status(1, 'SCAN_OK', False)
            print("✓ 扫码OK信号清除成功")
            
        except Exception as e:
            print(f"✗ PLC写入测试失败: {e}")
            return False
        
        print("3. 测试PLC监控线程...")
        try:
            # 设置回调函数
            def on_start(station_idx):
                print(f"   PLC启动信号回调: 工位{station_idx}")
            
            def on_stop(station_idx):
                print(f"   PLC停止信号回调: 工位{station_idx}")
            
            plc.set_callbacks(on_start, on_stop)
            
            # 启动监控线程
            plc.start()
            print("✓ PLC监控线程启动成功")
            
            # 运行5秒
            print("   监控线程运行中，请操作PLC按钮...")
            time.sleep(5)
            
            # 停止监控线程
            plc.stop()
            print("✓ PLC监控线程停止成功")
            
        except Exception as e:
            print(f"✗ PLC监控测试失败: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ PLC控制器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_main_app():
    """测试主应用程序功能"""
    print("\n" + "=" * 80)
    print("测试主应用程序功能")
    print("=" * 80)
    
    try:
        import tkinter as tk
        from Main import MainApp
        
        print("1. 创建Tkinter窗口...")
        root = tk.Tk()
        root.withdraw()  # 隐藏窗口
        
        print("2. 创建主应用程序...")
        app = MainApp(root)
        
        print("3. 测试UI更新...")
        # 测试线程安全的UI更新
        app.thread_safe_update_ui(1, 0, "测试扫码结果", "#90EE90")
        print("✓ UI更新测试成功")
        
        print("4. 测试日志记录...")
        app.thread_safe_log_message("测试日志消息")
        print("✓ 日志记录测试成功")
        
        print("5. 测试扫码回调...")
        # 模拟扫码结果
        app.on_scan_result(1, "TEST123456")
        print("✓ 扫码回调测试成功")
        
        print("6. 测试启动测试...")
        # 需要先设置扫码结果
        app.scan_results[1] = "TEST123456"
        app.station_status[1] = 'waiting_start'
        app.on_start_test(1)
        print("✓ 启动测试测试成功")
        
        print("7. 测试停止测试...")
        app.on_stop_test(1)
        print("✓ 停止测试测试成功")
        
        print("8. 测试紧急停止...")
        app.on_emergency_stop(1)
        print("✓ 紧急停止测试成功")
        
        print("9. 测试复位...")
        app.on_reset(1)
        print("✓ 复位测试成功")
        
        # 关闭窗口
        root.destroy()
        
        return True
        
    except Exception as e:
        print(f"✗ 主应用程序测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hv_test_runner():
    """测试高压测试运行器功能"""
    print("\n" + "=" * 80)
    print("测试高压测试运行器功能")
    print("=" * 80)
    
    try:
        from hv_test_runner import HVTestRunner
        
        print("1. 创建测试配置...")
        # 创建模拟配置
        station_config = {
            "scanner_ip": "192.168.10.228:8888",
            "power_supply_ip": "192.168.10.100",
            "lin_device_index": 0
        }
        
        product_times = {
            "hv_undervoltage": 5,
            "current_max": 10,
            "voltage_sequence": 15
        }
        
        print("2. 创建测试运行器...")
        # 创建测试运行器
        runner = HVTestRunner(
            station_idx=1,
            station_config=station_config,
            product_times=product_times,
            ui_callback=lambda station_idx, row_idx, text, color: print(f"UI更新: 工位{station_idx}, 行{row_idx}, 文本: {text}"),
            log_callback=lambda msg: print(f"日志: {msg}"),
            product_name="测试产品",
            scan_result="TEST123456"
        )
        
        print("3. 测试运行器初始化...")
        print(f"   工位索引: {runner.station_idx}")
        print(f"   产品名称: {runner.product_name}")
        print(f"   扫码结果: {runner.scan_result}")
        print("✓ 运行器初始化成功")
        
        print("4. 测试运行器停止...")
        runner.stop()
        print("✓ 运行器停止测试成功")
        
        return True
        
    except Exception as e:
        print(f"✗ 高压测试运行器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始系统功能测试")
    print("=" * 80)
    
    tests = [
        ("扫码枪功能", test_scanner),
        ("PLC控制器功能", test_plc_controller),
        ("主应用程序功能", test_main_app),
        ("高压测试运行器功能", test_hv_test_runner),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n开始测试: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                print(f"✓ {test_name}测试通过")
            else:
                print(f"✗ {test_name}测试失败")
        except Exception as e:
            print(f"✗ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 打印测试结果汇总
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        if success:
            print(f"✓ {test_name}: 通过")
            passed += 1
        else:
            print(f"✗ {test_name}: 失败")
            failed += 1
    
    print(f"\n总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    
    if failed == 0:
        print("\n✓ 所有测试通过！")
        return 0
    else:
        print("\n✗ 有测试失败，请检查问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())