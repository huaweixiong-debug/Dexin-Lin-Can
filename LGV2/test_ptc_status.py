#!/usr/bin/env python3
"""
测试PTC状态输出格式
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Main import LINManager

# 创建LINManager实例
lin_manager = LINManager()

# 模拟发送LIN消息，测试PTC状态输出格式
print("\n=== 测试PTC状态输出格式 ===")

# 测试不同功率和使能状态下的输出
print("\n1. 测试功率50%，使能1:")
lin_manager.send_lin_message(50, 1)

print("\n2. 测试功率0%，使能0:")
lin_manager.send_lin_message(0, 0)

print("\n3. 测试功率100%，使能1:")
lin_manager.send_lin_message(100, 1)

print("\n=== 测试完成 ===")
