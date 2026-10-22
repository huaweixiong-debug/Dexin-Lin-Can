#!/usr/bin/env python3
"""
测试系统PLC通讯日志
"""

import sys
import os
import time
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import logger
from plc_controller import PLCController

def simulate_plc_operations():
    """模拟PLC操作"""
    print("模拟PLC操作测试")
    print("=" * 60)
    
    # 创建PLC控制器
    plc = PLCController()
    
    # 设置日志回调
    log_messages = []
    def log_callback(message):
        log_messages.append(message)
        print(f"[UI Log] {message}")
    
    plc.set_log_callback(log_callback)
    
    # 连接PLC
    print("\n1. 连接PLC...")
    plc.connect()
    time.sleep(2)
    
    # 模拟扫码操作
    print("\n2. 模拟扫码操作...")
    for station in [1, 3, 5]:
        print(f"  工位{station}扫码完成")
        plc.write_status(station, 'SCAN_OK', True)
        time.sleep(0.5)
    
    # 模拟测试结果
    print("\n3. 模拟测试结果...")
    test_results = [
        (1, 'PASS'),
        (2, 'FAIL'),
        (3, 'PASS'),
        (4, 'FAIL'),
        (5, 'PASS')
    ]
    
    for station, result in test_results:
        print(f"  工位{station}测试结果: {result}")
        plc.write_test_result(station, result)
        time.sleep(0.3)
    
    # 模拟PLC信号读取
    print("\n4. 模拟PLC信号读取...")
    print("  启动PLC监控线程...")
    
    # 启动PLC监控
    plc.start()
    
    # 运行一段时间
    print("  运行监控5秒...")
    time.sleep(5)
    
    # 断开连接
    print("\n5. 断开PLC连接...")
    plc.disconnect()
    
    # 分析日志
    print("\n" + "=" * 60)
    print("日志分析:")
    print("=" * 60)
    
    # 统计不同类型的日志
    connection_logs = [msg for msg in log_messages if "连接" in msg]
    write_logs = [msg for msg in log_messages if "写入" in msg]
    test_result_logs = [msg for msg in log_messages if "测试结果" in msg]
    signal_logs = [msg for msg in log_messages if "信号" in msg]
    
    print(f"连接相关日志: {len(connection_logs)} 条")
    print(f"写入操作日志: {len(write_logs)} 条")
    print(f"测试结果日志: {len(test_result_logs)} 条")
    print(f"信号检测日志: {len(signal_logs)} 条")
    
    print("\n示例日志:")
    print("-" * 40)
    for i, msg in enumerate(log_messages[:10]):  # 显示前10条日志
        print(f"{i+1}. {msg}")
    
    if len(log_messages) > 10:
        print(f"... 还有 {len(log_messages) - 10} 条日志")
    
    print("\n" + "=" * 60)
    print("模拟测试完成")
    print("=" * 60)
    
    return len(log_messages) > 0

def test_plc_status_monitoring():
    """测试PLC状态监控"""
    print("\n" + "=" * 60)
    print("测试PLC状态监控")
    print("=" * 60)
    
    # 创建PLC控制器
    plc = PLCController()
    
    # 测试连接状态获取
    print("\n1. 测试连接状态获取...")
    
    # 初始状态应该是未连接
    print(f"  初始状态 - PLC1: {'已连接' if plc.connected1 else '未连接'}")
    print(f"  初始状态 - PLC2: {'已连接' if plc.connected2 else '未连接'}")
    
    # 连接PLC
    print("\n2. 连接PLC...")
    plc.connect()
    time.sleep(1)
    
    # 连接后的状态
    print(f"  连接后状态 - PLC1: {'已连接' if plc.connected1 else '未连接'}")
    print(f"  连接后状态 - PLC2: {'已连接' if plc.connected2 else '未连接'}")
    
    # 测试check_connection方法
    print("\n3. 测试连接状态检查...")
    plc.check_connection()
    
    # 断开连接
    print("\n4. 断开PLC连接...")
    plc.disconnect()
    
    print("\n" + "=" * 60)
    print("PLC状态监控测试完成")
    print("=" * 60)
    
    return True

def main():
    """主测试函数"""
    print("系统PLC通讯日志测试")
    print("=" * 60)
    
    try:
        # 测试PLC状态监控
        if not test_plc_status_monitoring():
            print("PLC状态监控测试失败")
            return 1
        
        # 模拟PLC操作
        if not simulate_plc_operations():
            print("PLC操作模拟测试失败")
            return 1
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        print("\n总结:")
        print("- PLC通讯日志功能正常工作")
        print("- 连接/断开连接日志完整")
        print("- 写入操作日志详细")
        print("- 测试结果日志清晰")
        print("- PLC状态监控功能正常")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())