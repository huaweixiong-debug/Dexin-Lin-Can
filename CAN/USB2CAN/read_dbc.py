#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取DBC文件中的CAN参数说明
"""

import os
import sys

def read_dbc_file():
    """读取DBC文件"""
    dbc_file_path = r'd:\老化CAN通讯\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc'
    
    if not os.path.exists(dbc_file_path):
        print(f"DBC文件不存在: {dbc_file_path}")
        return
    
    print(f"读取DBC文件: {dbc_file_path}")
    
    try:
        with open(dbc_file_path, 'r', encoding='gbk', errors='ignore') as f:
            content = f.read()
            
        print(f"\nDBC文件总行数: {len(content.split(chr(10)))}")
        
        # 查找与0x4E0、0x524、0x525相关的定义
        target_ids = ['0x4E0', '0x524', '0x525', '4E0', '524', '525']
        
        print(f"\n{'='*80}")
        print("查找与0x4E0、0x524、0x525相关的定义")
        print(f"{'='*80}")
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # 查找包含目标ID的行
            if any(target_id in line for target_id in target_ids):
                # 显示该行及其前后几行
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                print(f"\n找到相关内容（行 {i+1}）:")
                for j in range(start, end):
                    print(f"  {j+1}: {lines[j][:100]}")
            
            # 查找包含波特率、BRP、SEG等CAN配置参数的行
            if any(keyword in line.upper() for keyword in ['BAUD', 'BAUDRATE', 'BRP', 'SEG', 'SJW', 'BITTIMING', 'CAN_SPEED']):
                print(f"\n找到CAN配置参数（行 {i+1}）:")
                print(f"  {line[:150]}")
    
    except Exception as e:
        print(f"读取DBC文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    read_dbc_file()