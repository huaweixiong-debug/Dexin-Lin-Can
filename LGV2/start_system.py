#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统启动脚本
"""

import sys
import os
import time
from logger import logger

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

def check_plc_connection():
    """检查PLC连接状态"""
    print("检查PLC连接状态...")
    
    try:
        from plc_controller import PLCController
        
        plc = PLCController()
        plc.connect()
        
        if plc.connected1 or plc.connected2:
            print("✅ PLC连接成功")
            print(f"   PLC1 (192.168.10.221): {'已连接' if plc.connected1 else '未连接'}")
            print(f"   PLC2 (192.168.10.222): {'已连接' if plc.connected2 else '未连接'}")
            plc.disconnect()
            return True
        else:
            print("❌ PLC连接失败")
            return False
    except Exception as e:
        print(f"❌ PLC检查失败: {e}")
        return False

def check_scanner_config():
    """检查扫码枪配置"""
    print("\n检查扫码枪配置...")
    
    try:
        import json
        
        config_file = "config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            hardware_settings = config.get("hardware_settings", {})
            scanner_count = 0
            
            for station_key, settings in hardware_settings.items():
                scanner_ip = settings.get("scanner_ip", "")
                if scanner_ip:
                    scanner_count += 1
                    print(f"   {station_key}: {scanner_ip}")
            
            if scanner_count > 0:
                print(f"✅ 找到 {scanner_count} 个扫码枪配置")
                return True
            else:
                print("⚠️  未找到扫码枪配置")
                return True  # 扫码枪配置可选
        else:
            print("⚠️  未找到config.json文件")
            return True  # 配置文件可选
    except Exception as e:
        print(f"❌ 扫码枪配置检查失败: {e}")
        return False

def start_main_app():
    """启动主应用程序"""
    print("\n启动主应用程序...")
    
    try:
        import tkinter as tk
        from Main import MainApp
        
        root = tk.Tk()
        app = MainApp(root)
        root.mainloop()
    except Exception as e:
        print(f"❌ 主应用程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 80)
    print("LGV2 测试系统启动脚本")
    print("=" * 80)
    
    # 检查PLC连接
    plc_ok = check_plc_connection()
    
    # 检查扫码枪配置
    scanner_ok = check_scanner_config()
    
    # 如果PLC连接成功，启动主应用程序
    if plc_ok:
        print("\n" + "=" * 80)
        print("所有检查通过，启动主应用程序...")
        print("=" * 80)
        start_main_app()
    else:
        print("\n" + "=" * 80)
        print("PLC连接失败，无法启动系统")
        print("请检查PLC连接和网络设置")
        print("=" * 80)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
