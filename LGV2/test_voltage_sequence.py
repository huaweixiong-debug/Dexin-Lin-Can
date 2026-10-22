import time
from Power_Com import ProgrammablePowerSupply


def main():
    """
    测试电压序列：8.5V 10秒 → 9.5V 10秒 → 16V 10秒 → 15V 10秒 → 13V 10秒
    """
    print("=" * 80)
    print("电压序列测试程序")
    print("=" * 80)
    print("测试序列：8.5V 10秒 → 9.5V 10秒 → 16V 10秒 → 15V 10秒 → 13V 10秒")
    print("=" * 80)
    
    # 创建电源对象
    pps = ProgrammablePowerSupply(port='COM4', station_address=1)
    
    try:
        # 连接电源
        print("\n🔌 连接电源...")
        if not pps.connect():
            print("❌ 电源连接失败，程序退出")
            return
        
        # 开机
        print("🔌 电源开机...")
        if not pps.power_on():
            print("❌ 电源开机失败，程序退出")
            return
        
        # 定义电压序列
        voltage_sequence = [
            (8.5, 10),   # 8.5V 10秒
            (9.5, 10),   # 9.5V 10秒
            (16.0, 10),  # 16V 10秒
            (15.0, 10),  # 15V 10秒
            (13.0, 10)   # 13V 10秒
        ]
        
        # 执行电压序列
        for i, (voltage, duration) in enumerate(voltage_sequence, 1):
            print(f"\n{'=' * 60}")
            print(f"阶段 {i}/{len(voltage_sequence)}: {voltage}V，持续 {duration} 秒")
            print(f"{'=' * 60}")
            
            # 设置电压
            print(f"⚡ 设置电压: {voltage}V")
            if not pps.set_voltage(voltage):
                print(f"❌ 设置电压失败: {voltage}V")
                continue
            
            # 等待电压稳定
            time.sleep(0.5)
            
            # 持续监测指定时间
            start_time = time.time()
            elapsed = 0
            
            while elapsed < duration:
                # 读取电源状态
                voltage_actual, current, status = pps.read_power_status()
                
                if voltage_actual is not None:
                    current_time = time.time() - start_time
                    print(f"  时间: {current_time:.1f}s, 电压: {voltage_actual:.2f}V, 电流: {current:.2f}A")
                
                # 等待1秒
                time.sleep(1)
                elapsed = time.time() - start_time
            
            print(f"✅ 阶段完成: {voltage}V {duration}秒")
        
        # 测试完成，电源待机
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)
        
        print("🔌 电源待机...")
        pps.power_off()
        
    except KeyboardInterrupt:
        print("\n\n🛑 用户中断，正在关闭电源...")
        pps.power_off()
    except Exception as e:
        print(f"\n❌ 程序运行错误: {e}")
        pps.power_off()
    finally:
        # 断开连接
        pps.disconnect()
        print("✅ 电源连接已断开")


if __name__ == "__main__":
    main()