#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证测试序列生成是否符合要求
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Main import TestFlowManager

def test_sequence_generation():
    """测试测试序列生成"""
    print("🧪 验证测试序列生成...")
    
    # 创建测试流程管理器实例
    test_flow = TestFlowManager()
    
    # 模拟产品设置
    test_flow.product_settings = {
        'high_voltage_undervoltage_time': 10,
        'high_voltage_undervoltage_recovery_time': 10,
        'high_voltage_overvoltage_time': 10,
        'high_voltage_overvoltage_recovery_time': 10,
        '0%_power_time_1': 10,
        '100%_power_time': 10,
        '0%_power_time_2': 10,
        '70%_power_time': 10,
        '0%_power_time_3': 10,
        '50%_power_time': 10,
        '0%_power_time_4': 10,
        '30%_power_time': 10,
        '10%_power_time': 10,
        '0%_power_time_5': 10
    }
    
    # 生成测试序列
    test_flow.generate_test_sequence()
    
    # 验证测试序列
    print(f"\n📋 生成的测试序列（共 {len(test_flow.test_sequence)} 个步骤）：")
    # 打印完整的测试序列结构，包括所有索引
    for idx in range(len(test_flow.test_sequence)):
        try:
            step = test_flow.test_sequence[idx]
            print(f"   索引 {idx} (step_num={step['step_num']}) - {step['name']}: 电压={step['voltage']}V, 功率={step['power_percent']}%, 使能={step['enable']}")
        except Exception as e:
            print(f"   索引 {idx} - 错误: {e}")
    # 打印完整的测试序列内容，用于调试
    print(f"\n🔧 完整测试序列内容：")
    print(test_flow.test_sequence)
    
    # 检查第一步是否为初始状态
    first_step = test_flow.test_sequence[0]
    if first_step['name'] == '初始状态' and first_step['voltage'] == 13.0:
        print("✅ 第一步正确设置为初始状态（13V）")
    else:
        print(f"❌ 第一步设置错误: {first_step}")
        return False
    
    # 检查测试顺序是否正确
    expected_order = ['初始状态', '高压欠压', '高压欠压恢复', '高压过压', '高压过压恢复']
    actual_order = [step['name'] for step in test_flow.test_sequence[:5]]
    
    if actual_order == expected_order:
        print("✅ 测试顺序正确")
    else:
        print(f"❌ 测试顺序错误: 预期 {expected_order}, 实际 {actual_order}")
        return False
    
    print("🎉 所有验证通过！")
    return True

if __name__ == "__main__":
    test_sequence_generation()
