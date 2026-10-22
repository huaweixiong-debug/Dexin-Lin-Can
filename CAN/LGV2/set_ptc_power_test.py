#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTC功率设置测试脚本
功能：将PTC功率调到50%，使能=0
"""

import time
from pathlib import Path

# 添加项目根目录到Python路径
import sys
sys.path.append(str(Path(__file__).parent))

from Main import LINManager

class PTCPowerSetter:
    def __init__(self):
        """
        初始化PTC功率设置器
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
    
    def set_ptc_power(self, power_percent=50, enable=0):
        """
        设置PTC功率和使能
        
        参数:
            power_percent: 功率百分比，默认为50%
            enable: 使能状态，默认为0（禁用）
        
        返回:
            True/False
        """
        print(f"\n2. 设置PTC功率为 {power_percent}%，使能为 {enable}")
        try:
            # 直接写入配置文件，不打印LIN重试信息
            # 确保数据目录存在
            import os
            data_dir = os.path.join('d:', 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            # 写入功率文件
            power_file = os.path.join(data_dir, 'AEHPctPwrCmndFrt_0.txt')
            with open(power_file, 'w') as f:
                f.write(str(power_percent))
            print(f"✅ 功率配置文件已更新: {power_file} = {power_percent}")
            
            # 写入使能文件
            enable_file = os.path.join(data_dir, 'AEhodOpEnblCmdFrt_0.txt')
            enable_text = f"{enable} - {'Master Operation Enabled' if enable == 1 else 'Master Operation Disabled'}"
            with open(enable_file, 'w') as f:
                f.write(enable_text)
            print(f"✅ 使能配置文件已更新: {enable_file} = {enable_text}")
            
            print(f"✅ PTC功率设置成功: {power_percent}%, 使能={enable}")
            return True
        except Exception as e:
            print(f"❌ 设置PTC功率时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_actual_status(self):
        """
        检查PTC实际状态
        """
        print("\n3. 检查PTC实际状态")
        try:
            # 读取实际配置文件
            import os
            data_dir = os.path.join('d:', 'data')
            
            # 读取功率文件
            power_file = os.path.join(data_dir, 'AEHPctPwrCmndFrt_0.txt')
            actual_power = "未知"
            if os.path.exists(power_file):
                with open(power_file, 'r') as f:
                    actual_power = f.read().strip()
            
            # 读取使能文件
            enable_file = os.path.join(data_dir, 'AEhodOpEnblCmdFrt_0.txt')
            actual_enable = "未知"
            if os.path.exists(enable_file):
                with open(enable_file, 'r') as f:
                    actual_enable = f.read().strip()
            
            # 显示实际状态
            print(f"📊 实际功率设置: {actual_power}%")
            print(f"📊 实际使能状态: {actual_enable}")
            
            return True
        except Exception as e:
            print(f"❌ 检查实际状态时出错: {e}")
            return False
    
    def get_arc_fault_cycle(self, cycle_count=0):
        """
        获取AEH_ARCFrt_69_9的循环状态（0.1.2.3循环）
        
        参数:
            cycle_count: 循环计数器，用于手动控制循环状态
        
        返回:
            当前ARC故障状态值
        """
        if cycle_count >= 0:
            # 使用传入的计数器计算状态
            return cycle_count % 4
        else:
            # 使用当前时间的秒数作为种子来生成循环状态
            import time
            current_second = int(time.time()) % 4
            return current_second
    
    def run_continuous_test(self, power_percent=50, enable=1):
        """
        运行连续PTC功率测试，按回车键停止
        
        参数:
            power_percent: 功率百分比，默认为50%
            enable: 使能状态，默认为1（启用）
        """
        print("🚀 开始连续PTC功率测试")
        print(f"📌 目标功率: {power_percent}%")
        print(f"📌 目标使能: {enable}")
        print("📌 测试频率: 1秒/次")
        print("📌 按回车键停止测试")
        print("=" * 60)
        
        import sys
        import time
        import platform
        
        cycle_count = 0
        
        # Windows兼容的键盘输入检测
        def is_key_pressed():
            """检测是否有按键按下"""
            if platform.system() == 'Windows':
                try:
                    import msvcrt
                    return msvcrt.kbhit()
                except ImportError:
                    return False
            else:
                import select
                return select.select([sys.stdin], [], [], 0)[0]
        
        try:
            while True:
                cycle_count += 1
                print(f"\n🔄 测试循环 {cycle_count}")
                
                # 1. 设置PTC功率和使能（直接写入配置文件）
                if not self.set_ptc_power(power_percent, enable):
                    print(f"❌ 循环 {cycle_count} 失败")
                    time.sleep(1)
                    continue
                
                # 2. 等待0.5秒，确保设置生效
                time.sleep(0.5)
                
                # 3. 检查实际状态
                if not self.check_actual_status():
                    print(f"❌ 循环 {cycle_count} 失败")
                    time.sleep(1)
                    continue
                
                # 4. 使用真实LIN管理器读取状态
                try:
                    from Main import LINManager
                    lin_manager = LINManager()
                    
                    # 获取完整的PTC状态信息
                    ptc_full_status = lin_manager.get_full_ptc_status()
                    
                    # 状态映射
                    status_map = {
                        0: "0x0:Running Normal",
                        1: "0x1:Limited Operation",
                        2: "0x2:Recoverable Fault",
                        3: "0x3:Non-Recoverable Fault"
                    }
                    
                    # 显示真实PTC状态
                    print("====================================")
                    print(f"AEHModOptgStsFrt_69_9 - {status_map.get(ptc_full_status['AEHModOptgStsFrt_69_9'], f'Unknown (0x{ptc_full_status["AEHModOptgStsFrt_69_9"]})')}")
                    print(f"AEH_CommErrFrt_69_9 - {'0x0:No Comm Error' if ptc_full_status['AEH_CommErrFrt_69_9'] == 0 else '0x1:Comm Error'}")
                    print(f"AEHMsrdCurrFrt_69_9 - {ptc_full_status['AEHMsrdCurrFrt_69_9']:.4f} A")
                    print(f"AEHMsrdCurrOORHiFrt_69_9 - $0={'True' if ptc_full_status['AEHMsrdCurrOORHiFrt_69_9'] == 0 else 'False'}; $1={'True' if ptc_full_status['AEHMsrdCurrOORHiFrt_69_9'] == 1 else 'False'}")
                    print(f"AEHMsrdCurrOORLoFrt_69_9 - $0={'True' if ptc_full_status['AEHMsrdCurrOORLoFrt_69_9'] == 0 else 'False'}; $1={'True' if ptc_full_status['AEHMsrdCurrOORLoFrt_69_9'] == 1 else 'False'}")
                    print(f"AEH_ARCFrt_69_9 - {ptc_full_status['AEH_ARCFrt_69_9']} (E=N*1)")  # 0.1.2.3循环，使用真实值
                    print("====================================")
                    
                    # 关闭LIN管理器
                    lin_manager.running = False
                except Exception as e:
                    print(f"⚠️ 读取PTC状态时出错: {e}")
                
                # 5. 检查是否有按键输入
                print("⏳ 等待1秒... (按任意键停止)")
                
                # 等待1秒，每0.1秒检查一次按键
                for _ in range(10):
                    if is_key_pressed():
                        # 读取按键
                        if platform.system() == 'Windows':
                            import msvcrt
                            msvcrt.getch()
                        else:
                            sys.stdin.read(1)
                        print("\n⚠️ 用户中断测试")
                        return True
                    time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断程序")
            return False
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            print("\n5. 测试完成")
            print(f"📊 共执行 {cycle_count} 个循环")
            print("=" * 60)

if __name__ == "__main__":
    # 创建PTC功率设置器实例
    ptc_setter = PTCPowerSetter()
    
    # 运行连续测试，设置PTC功率为50%，使能为1，1秒一次，按回车键停止
    ptc_setter.run_continuous_test(power_percent=50, enable=1)
    
    print("✅ PTC连续功率测试结束！")
