"""
文件说明：高压欠压及恢复测试脚本
功能：
1. 控制程控电源设置电压 (8.0V -> 10.5V -> 18.0V -> 15.0V)
2. 通过LIN总线发送控制命令
3. 监控PTC状态并判定测试结果
"""
import sys
import time
import threading
from ctypes import *

# 导入现有模块
try:
    from Power_6 import ProgrammablePowerSupply
    import LIN_6
    from LIN_6 import (
        find_target_device, 
        create_command_message, 
        parse_response_message,
        LINMasterIndex,
        LIN_EX_Init,
        LIN_EX_MASTER,
        LIN_EX_SUCCESS,
        send_lin_message_fast,
        LIN_EX_MSG_TYPE_MW,
        LIN_EX_MSG_TYPE_MR,
        LIN_EX_MasterRead,
        USB_CloseDevice,
        c_byte
    )
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 Power_6.py, LIN_6.py, usb_device.py, usb2lin_ex.py 在同一目录下")
    sys.exit(1)

def run_test_cycle(psu, lin_handle, step_name, target_voltage, expect_status, duration=10, voltage_tol=0.5, power_pct=50, enable=True):
    """
    执行单个测试循环
    :param psu: 电源对象
    :param lin_handle: LIN设备句柄
    :param step_name: 步骤名称
    :param target_voltage: 目标电压
    :param expect_status: 期望的PTC状态
    :param duration: 持续时间(秒)
    :param voltage_tol: 电压容差
    :param power_pct: 功率百分比
    :param enable: 使能状态
    """
    print("\n" + "=" * 60)
    print(f"{step_name} (目标电压: {target_voltage}V)")
    print("=" * 60)

    # 1. 设置电压
    print(f"设置电源: {target_voltage}V")
    psu.set_voltage(target_voltage)
    time.sleep(1)

    # 2. 验证电压
    voltage_ok = False
    actual_voltage = 0.0
    for _ in range(5):
        status = psu.read_status()
        if status:
            actual_voltage = status['voltage']
            print(f"当前电源电压: {actual_voltage:.2f}V")
            if target_voltage - voltage_tol <= actual_voltage <= target_voltage + voltage_tol:
                voltage_ok = True
                break
        time.sleep(0.5)
    
    if not voltage_ok:
        print(f"错误: 电源电压 {actual_voltage:.2f}V 未达到目标范围 ({target_voltage}V±{voltage_tol}V)，步骤终止")
        return False

    # 3. 准备LIN命令
    print(f"发送LIN命令: 功率{power_pct}%, 使能{'ON' if enable else 'OFF'}")
    cmd_data = create_command_message(power_pct, enable)
    
    # 4. 循环监控
    print(f"\n开始{duration}秒监控...")
    print(f"{'时间':<10} | {'电源电压(V)':<10} | {'LIN电流(A)':<10} | {'功率(W)':<10} | {'PTC状态':<20} | {'周期(ms)':<10} | {'ARC':<5}")
    print("-" * 110)

    start_time = time.perf_counter()
    last_loop_start = start_time
    final_ptc_status = None
    loop_count = 0
    cycle_intervals = []
    
    # ARC 验证变量
    last_arc = None
    arc_errors = 0
    
    while time.perf_counter() - start_time < duration:
        loop_start = time.perf_counter()
        
        # 计算循环周期 (从第二次循环开始)
        if loop_count > 0:
            cycle_ms = (loop_start - last_loop_start) * 1000
            cycle_intervals.append(cycle_ms)
        else:
            cycle_ms = 0.0
            
        last_loop_start = loop_start
        
        # A. 发送命令
        send_lin_message_fast(lin_handle, 0x24, cmd_data, LIN_EX_MSG_TYPE_MW)
        time.sleep(0.005) # 短暂等待

        # B. 读取LIN响应
        ret, out_msg = send_lin_message_fast(lin_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR)
        lin_current = 0.0
        ptc_status_code = -1
        ptc_status_desc = "Unknown"
        current_arc = None

        if ret == 1 and out_msg.DataLen > 0:
            data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
            signals = parse_response_message(data_bytes)
            
            if 'measured_current' in signals:
                lin_current = signals['measured_current'].get('physical_value', 0.0)
            
            if 'operating_status' in signals:
                ptc_status_code = signals['operating_status'].get('value', -1)
                ptc_status_desc = signals['operating_status'].get('description', 'Unknown')
                final_ptc_status = ptc_status_code
            
            if 'arc_counter' in signals:
                current_arc = signals['arc_counter'].get('value')
                
                # ARC 序列验证
                if current_arc is not None:
                    if last_arc is not None:
                        expected_arc = (last_arc + 1) % 4
                        if current_arc != expected_arc:
                            arc_errors += 1
                            # 仅在发生错误时打印，避免刷屏，或者在下方状态栏用颜色标记
                    last_arc = current_arc

        # C. 读取电源电压
        psu_status = psu.read_status()
        psu_voltage = 0.0
        if psu_status:
            psu_voltage = psu_status['voltage']

        # D. 计算功率
        power = psu_voltage * lin_current

        # E. 打印状态 (每次循环都打印，以展示连续的ARC)
        # if loop_count % 10 == 0:
        elapsed = time.perf_counter() - start_time
        arc_str = str(current_arc) if current_arc is not None else "-"
        print(f"{elapsed:5.1f}s     | {psu_voltage:10.2f} | {lin_current:10.2f} | {power:10.2f} | {ptc_status_desc:<20} | {cycle_ms:5.2f}      | {arc_str:<5}")
        
        loop_count += 1
        
        # F. 控制50ms循环周期
        elapsed_loop = time.perf_counter() - loop_start
        sleep_time = 0.05 - elapsed_loop
        if sleep_time > 0:
            time.sleep(sleep_time)

    # 5. 结果判定
    print("-" * 110)
    
    # 打印循环时间统计
    if cycle_intervals:
        avg_cycle = sum(cycle_intervals) / len(cycle_intervals)
        max_cycle = max(cycle_intervals)
        min_cycle = min(cycle_intervals)
        print(f"循环统计: 平均={avg_cycle:.2f}ms, 最大={max_cycle:.2f}ms, 最小={min_cycle:.2f}ms")
        
    # 打印 ARC 统计
    if arc_errors > 0:
        print(f"\033[91mARC序列错误: {arc_errors} 次\033[0m")
    else:
        print(f"\033[92mARC序列验证: 通过 (错误数: 0)\033[0m")
        
    print("-" * 110)

    if final_ptc_status == expect_status:
        print(f"{step_name}结果: \033[92m通过 (状态 0x{expect_status:X} {ptc_status_desc})\033[0m")
        return True
    else:
        actual_hex = f"0x{final_ptc_status:X}" if final_ptc_status is not None else "None"
        print(f"{step_name}结果: \033[91m失败 (期望 0x{expect_status:X}, 实际 {actual_hex})\033[0m")
        return False

def run_test():
    print("开始高压测试套件 (欠压/过压/恢复)")
    print("=" * 60)

    # 1. 初始化设备
    psu = None
    lin_handle = None

    try:
        # 初始化电源
        print("正在连接程控电源...")
        psu = ProgrammablePowerSupply(port='COM4', station_address=6)
        print("程控电源连接成功")

        # 初始化LIN设备
        print("正在查找LIN设备...")
        lin_handle = find_target_device()
        if lin_handle is None:
            print("未找到LIN设备，测试终止")
            return

        ret = LIN_EX_Init(lin_handle, LINMasterIndex, 19200, LIN_EX_MASTER)
        if ret != LIN_EX_SUCCESS:
            print(f"LIN初始化失败，返回值: {ret}")
            return
        print("LIN设备初始化成功")
        
        # 设置电源保护参数
        print("设置电源过压保护: 24.0V")
        psu.set_overvoltage(24.0)
        print("设置电源电流限制: 200A")
        psu.set_current(200)
        
        # 开机
        print("电源开机...")
        psu.power_on()
        time.sleep(1)

        # ---------------------------------------------------------
        # 执行测试步骤
        # ---------------------------------------------------------
        
        # 步骤1：高压欠压测试 (8.0V) -> 期望 0x2
        run_test_cycle(psu, lin_handle, "步骤1: 高压欠压测试", 8.0, 0x2)
        
        # 步骤2：高压欠压恢复测试 (10.5V) -> 期望 0x0
        run_test_cycle(psu, lin_handle, "步骤2: 高压欠压恢复测试", 10.5, 0x0)
        
        # 步骤3：高压过压测试 (18.0V) -> 期望 0x2
        run_test_cycle(psu, lin_handle, "步骤3: 高压过压测试", 18.0, 0x2)
        
        # 步骤4：高压过压恢复测试 (15.0V) -> 期望 0x0
        run_test_cycle(psu, lin_handle, "步骤4: 高压过压恢复测试", 15.0, 0x0)
        
        # 步骤5：待机功率测试 (13.0V) -> 期望 0x0
        run_test_cycle(psu, lin_handle, "步骤5: 待机功率测试", 13.0, 0x0, duration=10, power_pct=0, enable=True)

        # 步骤6：功率阶梯测试 (13.0V)
        print("\n" + "=" * 60)
        print("步骤6: 功率阶梯测试 (13.0V)")
        print("=" * 60)
        
        power_cycle_steps = [
            (100, 30),
            (0, 5),
            (70, 30),
            (0, 5),
            (50, 30),
            (0, 5),
            (30, 30),
            (0, 5),
            (10, 30),
            (0, 5)
        ]

        step_idx = 1
        for pct, duration in power_cycle_steps:
            step_name = f"步骤6-{step_idx}: 功率{pct}%持续{duration}s"
            # 每次都会先检查电压，OK后再发送LIN命令
            run_test_cycle(psu, lin_handle, step_name, 13.0, 0x0, 
                           duration=duration, power_pct=pct, enable=True)
            step_idx += 1

    except Exception as e:
        print(f"\n测试过程中发生异常: {e}")
        # 如果是串口权限错误，提示用户
        if "PermissionError" in str(e) or "Access is denied" in str(e):
            print("\n\033[93m提示: 串口(COM4)被占用。请检查是否有其他终端窗口正在运行测试脚本，并将其关闭。\033[0m")
        import traceback
        traceback.print_exc()

    finally:
        print("\n正在清理资源...")
        # 清理工作
        if psu:
            try:
                print("关闭电源输出...")
                psu.power_off()
                psu.close()
            except Exception as e:
                print(f"关闭电源失败: {e}")
        
        if lin_handle:
            try:
                print("关闭LIN设备...")
                USB_CloseDevice(lin_handle)
            except Exception as e:
                print(f"关闭LIN设备失败: {e}")
        
        print("测试结束")

if __name__ == "__main__":
    run_test()
