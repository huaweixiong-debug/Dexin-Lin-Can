#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取Excel文件中的信号定义
"""

import pandas as pd
import sys
import os

def read_excel_signals():
    """读取Excel文件中的信号定义"""
    file_path = r'd:\老化CAN通讯\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.xlsx'
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"读取文件: {file_path}")
    
    try:
        # 读取Matrix工作表
        df = pd.read_excel(file_path, sheet_name='Matrix')
        print(f"Matrix工作表数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        
        # 查找与0x4E0、0x524、0x525相关的信号
        target_ids = ['0x4E0', '0x524', '0x525', 'ECC_0x4E0', 'PTC_0x524', 'PTC_0x525']
        
        print(f"\n{'='*80}")
        print("查找与0x4E0、0x524、0x525相关的信号")
        print(f"{'='*80}")
        
        for col in df.columns:
            if df[col].dtype == 'object':  # 文本列
                for target_id in target_ids:
                    mask = df[col].astype(str).str.contains(target_id, case=False, na=False)
                    if mask.any():
                        print(f"\n在列 '{col}' 中找到包含 '{target_id}' 的行:")
                        relevant_rows = df[mask]
                        # 显示相关列
                        display_cols = [c for c in df.columns if any(keyword in str(c) for keyword in ['Msg', 'ID', 'Signal', 'Byte', 'Bit', 'Value', 'Type', 'Unit'])]
                        if display_cols:
                            print(relevant_rows[display_cols].to_string())
                        else:
                            print(relevant_rows.to_string())
        
        # 查找所有包含"波特率"或"Baud"的内容
        print(f"\n{'='*80}")
        print("查找包含波特率相关的内容")
        print(f"{'='*80}")
        
        for col in df.columns:
            if df[col].dtype == 'object':
                mask = df[col].astype(str).str.contains('波特率|Baud|baud|BRP|SEG|SJW|CAN.*配置|CAN.*参数', case=False, na=False)
                if mask.any():
                    print(f"\n在列 '{col}' 中找到相关内容:")
                    print(df[mask][col].to_string())
    
    except Exception as e:
        print(f"读取Excel文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    read_excel_signals()