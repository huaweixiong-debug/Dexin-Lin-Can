#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取DBC文件中的所有报文定义
"""

import os
import sys

def read_dbc_all():
    """读取DBC文件中的所有报文定义"""
    dbc_file_path = r'd:\老化CAN通讯\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927 .dbc'
    
    if not os.path.exists(dbc_file_path):
        print(f"DBC文件不存在: {dbc_file_path}")
        return
    
    print(f"读取DBC文件: {dbc_file_path}")
    
    try:
        with open(dbc_file_path, 'r', encoding='gbk', errors='ignore') as f:
            content = f.read()
            
        lines = content.split('\n')
        
        # 查找所有报文定义（BO_）
        print(f"\n{'='*80}")
        print("所有报文定义")
        print(f"{'='*80}")
        
        for i, line in enumerate(lines):
            if line.strip().startswith('BO_'):
                print(f"\n行 {i+1}: {line[:100]}")
                
                # 显示该报文的所有信号定义（SG_）
                j = i + 1
                while j < len(lines) and (lines[j].strip().startswith('SG_') or lines[j].strip() == ''):
                    if lines[j].strip().startswith('SG_'):
                        print(f"  {lines[j][:120]}")
                    j += 1
    
    except Exception as e:
        print(f"读取DBC文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    read_dbc_all()