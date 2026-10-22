#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取DBC文件中的详细信号定义
"""

import os
import sys

def read_dbc_detailed():
    """读取DBC文件中的详细信号定义"""
    dbc_file_path = r'd:\老化CAN通讯\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc'
    
    if not os.path.exists(dbc_file_path):
        print(f"DBC文件不存在: {dbc_file_path}")
        return
    
    print(f"读取DBC文件: {dbc_file_path}")
    
    try:
        with open(dbc_file_path, 'r', encoding='gbk', errors='ignore') as f:
            content = f.read()
            
        lines = content.split('\n')
        
        # 查找0x4E0、0x524、0x525的完整定义
        target_messages = ['ECC_0x4E0', 'PTC_0x524', 'PTC_0x525']
        
        for target_msg in target_messages:
            print(f"\n{'='*80}")
            print(f"查找报文: {target_msg}")
            print(f"{'='*80}")
            
            # 查找报文定义行（BO_）
            for i, line in enumerate(lines):
                if f'BO_ {target_msg}' in line or f'BO_ {target_msg.replace("_", "_")}' in line:
                    print(f"\n报文定义（行 {i+1}）:")
                    print(f"  {line}")
                    
                    # 显示该报文的所有信号定义（SG_）
                    j = i + 1
                    while j < len(lines) and (lines[j].strip().startswith('SG_') or lines[j].strip() == ''):
                        if lines[j].strip().startswith('SG_'):
                            print(f"  {lines[j][:120]}")
                        j += 1
                    break
    
    except Exception as e:
        print(f"读取DBC文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    read_dbc_detailed()