#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细读取Excel文件中的CAN参数说明
"""

import pandas as pd
import sys
import os

def read_excel_file():
    """读取Excel文件"""
    file_path = r'd:\老化CAN通讯\BAIC_3.0平台_ECC-ThemalBUS_PTC_CAN_V1.10_20250927.xlsx'
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"读取文件: {file_path}")
    
    try:
        # 读取Excel文件的所有工作表
        excel_file = pd.ExcelFile(file_path)
        print(f"\n工作表列表: {excel_file.sheet_names}")
        
        # 读取每个工作表
        for sheet_name in excel_file.sheet_names:
            print(f"\n{'='*60}")
            print(f"工作表: {sheet_name}")
            print(f"{'='*60}")
            
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            print(f"数据形状: {df.shape}")
            print(f"列名: {list(df.columns)}")
            
            # 显示所有数据
            print(f"\n所有数据:")
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            pd.set_option('display.max_colwidth', 50)
            print(df.to_string())
    
    except Exception as e:
        print(f"读取Excel文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    read_excel_file()