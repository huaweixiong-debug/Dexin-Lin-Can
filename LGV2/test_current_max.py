"""
测试电源电流最大值设置
"""
from Power_Com import ProgrammablePowerSupply


def test_current_max():
    """测试电流最大值设置"""
    print("=" * 60)
    print("测试电源电流最大值设置")
    print("=" * 60)
    
    # 创建电源对象（不需要实际连接）
    power_supply = ProgrammablePowerSupply(port='COM4', station_address=1)
    
    # 测试电流最大值设置
    test_currents = [150, 200, 250, 300]
    
    print(f"\n电源电流最大值设置为: {power_supply.current_max}A")
    print("\n测试不同电流值:")
    
    for test_current in test_currents:
        print(f"\n测试设置电流: {test_current}A")
        
        # 模拟设置电流（不实际发送命令）
        # 检查电流是否超过最大值
        if test_current > power_supply.current_max:
            print(f"⚠️ 电流 {test_current}A 超过最大值 {power_supply.current_max}A，将被限制为最大值")
            limited_current = power_supply.current_max
        else:
            limited_current = test_current
        
        print(f"✅ 实际设置电流: {limited_current}A")
    
    print("\n" + "=" * 60)
    print("电流最大值测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_current_max()