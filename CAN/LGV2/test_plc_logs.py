#!/usr/bin/env python3
"""
测试PLC通讯日志功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import logger
from plc_controller import PLCController
import time

def test_plc_connection_logs():
    """测试PLC连接日志"""
    print("=" * 60)
    print("测试PLC连接日志")
    print("=" * 60)
    
    # 创建PLC控制器
    plc = PLCController()
    
    # 设置日志回调
    def log_callback(message):
        print(f"[UI Log] {message}")
    
    plc.set_log_callback(log_callback)
    
    # 测试连接
    print("\n1. 测试PLC连接...")
    plc.connect()
    
    # 等待连接建立
    time.sleep(2)
    
    # 测试写入状态
    print("\n2. 测试写入PLC状态...")
    try:
        # 测试写入扫码OK信号
        plc.write_status(1, 'SCAN_OK', True)
        time.sleep(0.5)
        
        # 测试写入测试合格信号
        plc.write_status(1, 'PASS', True)
        time.sleep(0.5)
        
        # 测试写入测试不合格信号
        plc.write_status(1, 'FAIL', False)
        time.sleep(0.5)
        
    except Exception as e:
        print(f"写入测试失败: {e}")
    
    # 测试写入测试结果
    print("\n3. 测试写入测试结果...")
    try:
        plc.write_test_result(1, 'PASS')
        time.sleep(0.5)
        
        plc.write_test_result(2, 'FAIL')
        time.sleep(0.5)
        
    except Exception as e:
        print(f"测试结果写入失败: {e}")
    
    # 测试断开连接
    print("\n4. 测试断开连接...")
    plc.disconnect()
    
    print("\n" + "=" * 60)
    print("PLC连接日志测试完成")
    print("=" * 60)

def test_plc_monitoring_logs():
    """测试PLC监控日志"""
    print("\n" + "=" * 60)
    print("测试PLC监控日志")
    print("=" * 60)
    
    # 创建PLC控制器
    plc = PLCController()
    
    # 设置日志回调
    def log_callback(message):
        print(f"[UI Log] {message}")
    
    plc.set_log_callback(log_callback)
    
    # 启动PLC控制器
    print("\n1. 启动PLC监控...")
    plc.start()
    
    # 运行监控一段时间
    print("\n2. 运行PLC监控10秒...")
    print("在此期间，PLC控制器会定期检查连接状态和读取信号")
    
    try:
        for i in range(10):
            print(f"监控运行中... {i+1}/10 秒")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n监控被用户中断")
    
    # 停止PLC控制器
    print("\n3. 停止PLC监控...")
    # 注意：由于PLC控制器在后台线程运行，我们无法直接停止它
    # 在实际应用中，系统关闭时会自动停止
    
    print("\n" + "=" * 60)
    print("PLC监控日志测试完成")
    print("=" * 60)

def test_log_levels():
    """测试不同日志级别"""
    print("\n" + "=" * 60)
    print("测试日志级别")
    print("=" * 60)
    
    print("\n测试不同级别的日志输出:")
    print("-" * 40)
    
    logger.debug("这是一条DEBUG级别的日志")
    logger.info("这是一条INFO级别的日志")
    logger.warning("这是一条WARNING级别的日志")
    logger.error("这是一条ERROR级别的日志")
    
    print("\n" + "=" * 60)
    print("日志级别测试完成")
    print("=" * 60)

def main():
    """主测试函数"""
    print("PLC通讯日志功能测试")
    print("=" * 60)
    
    try:
        # 测试日志级别
        test_log_levels()
        
        # 测试PLC连接日志
        test_plc_connection_logs()
        
        # 测试PLC监控日志
        test_plc_monitoring_logs()
        
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())