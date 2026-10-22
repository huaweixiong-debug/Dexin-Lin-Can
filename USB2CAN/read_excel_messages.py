#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取Excel文件中的报文定义
"""

import pandas as pd
import sys
import os

def read_excel_messages():
    """读取Excel文件中的报文定义"""
    file_path = r'd:\老化CAN通讯\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.xlsx'
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"读取文件: {file_path}")
    
    try:
        # 读取Matrix工作表
        df = pd.read_excel(file_path, sheet_name='Matrix')
        print(f"Matrix工作表数据形状: {df.shape}")
        
        # 查找0x4E0、0x524、0x525的信号定义
        target_msg_ids = ['0x4E0', '0x524', '0x525']
        
        for msg_id in target_msg_ids:
            print(f"\n{'='*80}")
            print(f"报文ID: {msg_id}")
            print(f"{'='*80}")
            
            # 查找包含该报文ID的行
            mask = df['Msg ID\n报文标识符'].astype(str).str.contains(msg_id, case=False, na=False)
            
            if mask.any():
                msg_rows = df[mask]
                print(f"找到 {len(msg_rows)} 个信号:")
                
                # 显示关键列
                key_cols = ['Msg Name\n报文名称', 'Msg ID\n报文标识符', 'Msg Cycle Time(ms)\n报文周期时间',
                          'Signal Name\n信号名称', 'Chinese Signal Description\n中文信号描述',
                          'Start Byte\n起始字节', 'Start Bit\n起始位', 'Bit Length(Bit)\n信号长度',
                          'Resolution\n精度', 'Offset\n偏移量', 'Unit\n单位']
                
                for col in key_cols:
                    if col in msg_rows.columns:
                        print(f"\n{col}:")
                        print(msg_rows[col].dropna().to_string())
            else:
                print(f"未找到报文 {msg_id} 的信号定义")
    
    except Exception as e:
        print(f"读取Excel文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    read_excel_messages()