#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的PLC通讯
"""

import sys
import os
import time
from logger import logger

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

def test_plc_controller():
    """测试PLC控制器修复"""
    print("=" * 80)
    print("测试修复后的PLC控制器")
    print("=" * 80)
    
    try:
        from plc_controller import PLCController
        
        print("1. 创建PLC控制器实例...")
        plc = PLCController()
        print("✓ PLC控制器实例创建成功")
        
        print("2. 测试内存区域定义...")
        print(f"   M区类型: {plc.plc_mem_area}")
        print("✓ 内存区域定义成功")
        
        print("3. 测试PLC连接...")
        plc.connect()
        
        if plc.connected1 or plc.connected2:
            print("✓ PLC连接成功")
            print(f"   PLC1连接状态: {'已连接' if plc.connected1 else '未连接'}")
            print(f"   PLC2连接状态: {'已连接' if plc.connected2 else '未连接'}")
        else:
            print("✗ PLC连接失败")
            return False
        
        print("4. 测试PLC读取...")
        # 手动调用监控循环一次
        plc.monitor_loop()
        print("✓ PLC读取测试完成")
        
        print("5. 测试PLC写入...")
        # 测试写入扫码OK信号
        plc.write_status(1, 'SCAN_OK', True)
        print("✓ PLC写入测试完成")
        
        print("6. 测试关闭连接...")
        plc.disconnect()
        print("✓ PLC连接已关闭")
        
        print("\n" + "=" * 80)
        print("✅ PLC控制器修复测试通过！")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n✗ PLC控制器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 测试PLC控制器
    test_plc_controller()
    
    print("\n测试完成。请检查日志文件了解详细信息。")
