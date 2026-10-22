#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查PTC当前状态
功能：读取PTC的实际状态和电流值
"""

import time
from pathlib import Path

# 添加项目根目录到Python路径
import sys
sys.path.append(str(Path(__file__).parent))

from Main import LINManager

class PTCStatusChecker:
    def __init__(self):
        """
        初始化PTC状态检查器
        """
        self.lin_manager = None
    
    def connect_lin(self):
        """
        初始化LIN管理器
        
        返回:
            True/False
        """
        print("=" * 60)
        print("1. 初始化LIN管理器")
        try:
            self.lin_manager = LINManager()
            print("✅ LIN管理器初始化成功")
            return True
        except Exception as e:
            print(f"❌ LIN管理器初始化失败: {e}")
            return False
    
    def check_ptc_status(self):
        """
        检查PTC当前状态
        
        返回:
            (ptc_status, ptc_current)
        """
        print("\n2. 检查PTC当前状态")
        try:
            ptc_status = self.lin_manager.get_ptc_status()
            ptc_current = self.lin_manager.get_ptc_current()
            
            print(f"📊 PTC状态: {ptc_status}")
            print(f"📊 PTC电流: {ptc_current:.2f}A")
            
            # 解析PTC状态
            status_map = {
                0: "Running Normal (0x0)",
                1: "Recoverable Fault (0x1)",
                2: "Non-recoverable Fault (0x2)",
                3: "Initialization (0x3)"
            }
            print(f"📋 PTC状态描述: {status_map.get(ptc_status, f'Unknown (0x{ptc_status})')}")
            
            return ptc_status, ptc_current
        except Exception as e:
            print(f"❌ 检查PTC状态时出错: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def check_power_files(self):
        """
        检查功率相关配置文件
        """
        print("\n3. 检查功率配置文件")
        try:
            power_file = Path(r'd:\data\AEHPctPwrCmndFrt_0.txt')
            enable_file = Path(r'd:\data\AEhodOpEnblCmdFrt_0.txt')
            
            if power_file.exists():
                with open(power_file, 'r') as f:
                    power_value = f.read().strip()
                print(f"📄 功率配置文件: {power_file}")
                print(f"   内容: {power_value}%")
            else:
                print(f"❌ 功率配置文件不存在: {power_file}")
            
            if enable_file.exists():
                with open(enable_file, 'r') as f:
                    enable_value = f.read().strip()
                print(f"📄 使能配置文件: {enable_file}")
                print(f"   内容: {enable_value}")
            else:
                print(f"❌ 使能配置文件不存在: {enable_file}")
            
        except Exception as e:
            print(f"❌ 检查配置文件时出错: {e}")
    
    def run_check(self):
        """
        运行PTC状态检查
        """
        print("🚀 开始PTC状态检查")
        print("=" * 60)
        
        try:
            # 1. 初始化LIN管理器
            if not self.connect_lin():
                return False
            
            # 2. 检查PTC状态
            ptc_status, ptc_current = self.check_ptc_status()
            
            # 3. 检查功率配置文件
            self.check_power_files()
            
            print("\n" + "=" * 60)
            print("🎉 PTC状态检查完成！")
            print("=" * 60)
            
            return True
            
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断程序")
            return False
        except Exception as e:
            print(f"\n❌ 检查失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 清理资源
            if hasattr(self, 'lin_manager') and self.lin_manager:
                print("\n4. 清理资源")
                self.lin_manager.running = False
                print("✅ 资源已清理")
            print("=" * 60)

if __name__ == "__main__":
    # 创建状态检查器实例
    status_checker = PTCStatusChecker()
    
    # 运行状态检查
    status_checker.run_check()
