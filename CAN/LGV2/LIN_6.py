"""
文件说明：USB2XXX LIN通信测试程序 - LIN_6 修正版
功能：严格按照LIN矩阵定义发送和接收数据，修正存活计数器的解析逻辑
修正：修正存活计数器的解析逻辑，添加循环时间统计功能
"""
from ctypes import *
from time import sleep, perf_counter, time
import threading
from usb_device import *
from usb2lin_ex import *

# 设备配置
LINMasterIndex = 0  # LIN主站索引
TARGET_SERIAL = "3041545500333035530006EE"  # 目标设备序列号

# 全局变量
running = True  # 控制循环运行


def check_keyboard_input():
    """检查键盘输入，用于停止程序"""
    global running
    input("按回车键停止程序...\n")
    running = False


def create_command_message(power_percentage=50, enable=True):
    """
    创建命令报文 (AEHF_Cmd_MSG, ID 0x24)

    参数:
        power_percentage: 功率百分比 (0-127)
        enable: 使能开关 (True/False)

    返回:
        data_buffer: 2字节数据缓冲区
    """
    # 验证参数范围
    if power_percentage < 0 or power_percentage > 127:
        raise ValueError("功率百分比必须在0-127范围内")

    # 创建2字节数据缓冲区 (根据文档: 报文长度=2)
    data_buffer = (c_byte * 8)()

    # 第一个字节: AEHPctPwrCmndFrt_69_9 - 功率请求占比
    # 起始字节0, 起始位0, 信号长度7, 无符号
    # 范围: 0x00-0x7F (0-127)
    data_buffer[0] = power_percentage & 0x7F  # 确保在0-127范围内

    # 第二个字节: AEHModOpEnblCmdFrt_69_9 - 使能开关
    # 起始字节1, 起始位8, 信号长度1, 无符号
    # 范围: 0x00-0x01
    if enable:
        data_buffer[1] = 0x01  # Heater Operation Enabled
    else:
        data_buffer[1] = 0x00  # Heater Operation Disabled

    # 剩余字节填充0 (LIN通常使用8字节，但有效数据是2字节)
    for i in range(2, 8):
        data_buffer[i] = 0x00

    return data_buffer


def parse_response_message(data_bytes):
    """
    解析响应报文 (AEHF_Rsp_MSG, ID 0x25)

    参数:
        data_bytes: 接收到的数据字节列表

    返回:
        dict: 解析后的信号字典
    """
    if len(data_bytes) < 4:
        print(f"警告: 响应数据长度不足，期望4字节，实际收到{len(data_bytes)}字节")
        # 如果长度不够，用0填充
        padded_data = data_bytes + [0] * (4 - len(data_bytes))
        data_bytes = padded_data

    # 将字节列表转换为整数以便位操作
    byte0 = data_bytes[0] if len(data_bytes) > 0 else 0
    byte1 = data_bytes[1] if len(data_bytes) > 1 else 0
    byte2 = data_bytes[2] if len(data_bytes) > 2 else 0
    byte3 = data_bytes[3] if len(data_bytes) > 3 else 0

    # 解析各个信号
    signals = {}

    # 1. AEHModOprtgStsFrt_69_9 - PTC运行状态
    # 起始字节1, 起始位11, 信号长度2
    # 从byte1的位3-2 (Intel格式，小端)
    # 文档: 起始位11表示byte1的位3 (因为byte1的位0是8，位1是9，位2是10，位3是11)
    # 所以要右移3位，取低2位
    status_bits = (byte1 >> 3) & 0x03
    status_map = {
        0: "Running Normal",
        1: "Limited Operation",
        2: "Recoverable Fault",
        3: "Non-Recoverable Fault"
    }
    signals['operating_status'] = {
        'value': status_bits,
        'description': status_map.get(status_bits, f"Unknown ({status_bits})"),
        'raw_bits': status_bits
    }

    # 2. AEH_CommErrFrt_69_9 - 通讯故障
    # 起始字节1, 起始位15, 信号长度1
    # byte1的最高位 (bit7)
    comm_err = (byte1 >> 7) & 0x01
    signals['communication_error'] = {
        'value': comm_err,
        'description': "Comm Error" if comm_err == 1 else "No Comm Error",
        'raw_bits': comm_err
    }

    # 3. AEHMsrdCurrFrt_69_9 - PTC运行电流
    # 起始字节0, 起始位0, 信号长度9
    # 跨字节: byte0的全部8位 + byte1的bit0
    current_raw = (byte1 & 0x01) << 8 | byte0
    # 转换公式: 物理值 = 原始值 * 0.5 - 10
    current_physical = current_raw * 0.5 - 10
    signals['measured_current'] = {
        'raw_value': current_raw,
        'physical_value': current_physical,
        'unit': 'A',
        'formula': f"{current_raw} * 0.5 - 10 = {current_physical:.4f}A"
    }

    # 4. AEHMsrdCurrOORHiFrt_69_9 - 过流故障
    # 起始字节3, 起始位30, 信号长度1
    # byte3的位6 (从0开始计数)
    # 注意: byte3的位0是24，位1是25，...位6是30
    over_current = (byte3 >> 6) & 0x01
    signals['over_current_fault'] = {
        'value': over_current,
        'description': "True" if over_current == 1 else "False",
        'raw_bits': over_current
    }

    # 5. AEHMsrdCurrOORLoFrt_69_9 - 欠流保护
    # 起始字节3, 起始位31, 信号长度1
    # byte3的最高位 (bit7)
    under_current = (byte3 >> 7) & 0x01
    signals['under_current_fault'] = {
        'value': under_current,
        'description': "True" if under_current == 1 else "False",
        'raw_bits': under_current
    }

    # 6. AEH_ARCFrt_69_9 - 存活计数器
    # 起始字节1, 起始位9, 信号长度2
    # byte1的位1-2 (Intel格式)
    # 注意: byte1的位0是8，位1是9，位2是10
    # 所以要右移1位，取低2位
    arc_counter = (byte1 >> 1) & 0x03
    signals['arc_counter'] = {
        'value': arc_counter,
        'description': f"Counter value: {arc_counter}",
        'raw_bits': arc_counter,
        'expected_cycle': [0, 1, 2, 3, 0, 1, 2, 3]  # 应该在这个序列中循环
    }

    return signals


def print_response_signals(signals):
    """打印解析后的响应信号"""
    print("\n" + "=" * 50)
    print("响应数据解析结果")
    print("=" * 50)

    # PTC运行状态
    status = signals.get('operating_status', {})
    print(f"PTC运行状态: {status.get('description', 'Unknown')} (原始值: {status.get('value', 0):02b})")

    # 通讯故障
    comm_err = signals.get('communication_error', {})
    print(f"通讯故障: {comm_err.get('description', 'Unknown')} (原始值: {comm_err.get('value', 0):01b})")

    # PTC运行电流
    current = signals.get('measured_current', {})
    if current:
        raw_val = current.get('raw_value', 0)
        phys_val = current.get('physical_value', 0)
        if phys_val > 0:
            print(f"\033[92mPTC运行电流: {phys_val:.4f} A (原始值: {raw_val})\033[0m")
        else:
            print(f"PTC运行电流: {phys_val:.4f} A (原始值: {raw_val})")

    # 过流故障
    over_curr = signals.get('over_current_fault', {})
    print(f"过流故障: {over_curr.get('description', 'Unknown')} (原始值: {over_curr.get('value', 0):01b})")

    # 欠流保护
    under_curr = signals.get('under_current_fault', {})
    print(f"欠流保护: {under_curr.get('description', 'Unknown')} (原始值: {under_curr.get('value', 0):01b})")

    # 存活计数器
    arc = signals.get('arc_counter', {})
    arc_value = arc.get('value', 0)
    arc_desc = arc.get('description', 'Unknown')

    # 检查存活计数器是否在0-3范围内循环
    if 0 <= arc_value <= 3:
        print(f"存活计数器: {arc_desc} (原始值: {arc_value:02b})")
    else:
        print(f"\033[91m存活计数器错误: 值{arc_value}不在0-3范围内!\033[0m")

    print("=" * 50)


def find_target_device():
    """查找目标设备"""
    DevHandles = (c_uint * 20)()

    # 扫描设备
    ret = USB_ScanDevice(byref(DevHandles))
    if ret == 0:
        print("没有找到连接的设备!")
        return None

    print(f"找到 {ret} 个设备")

    # 查找目标设备
    for i in range(ret):
        ret_open = USB_OpenDevice(DevHandles[i])
        if ret_open:
            # 获取设备信息
            USB2XXXInfo = DEVICE_INFO()
            USB2XXXFunctionString = (c_char * 256)()
            ret_info = DEV_GetDeviceInfo(DevHandles[i], byref(USB2XXXInfo), byref(USB2XXXFunctionString))

            if ret_info:
                # 构建序列号字符串
                serial_parts = []
                for j in range(len(USB2XXXInfo.SerialNumber)):
                    serial_parts.append(f"{USB2XXXInfo.SerialNumber[j]:08X}")
                device_serial = ''.join(serial_parts)

                print(f"设备 {i} 序列号: {device_serial}")

                if device_serial == TARGET_SERIAL:
                    print(f"找到目标设备!")
                    return DevHandles[i]
                else:
                    USB_CloseDevice(DevHandles[i])
            else:
                USB_CloseDevice(DevHandles[i])
        else:
            continue

    print(f"未找到序列号为 {TARGET_SERIAL} 的设备!")
    return None


def send_lin_message(handle, pid, data_buffer, msg_type=LIN_EX_MSG_TYPE_MW, lin_index=0):
    """发送LIN消息"""
    LINOutMsg = LIN_EX_MSG()
    LINMsg = LIN_EX_MSG()

    # 设置消息参数
    LINMsg.MsgType = msg_type
    LINMsg.Timestamp = 20  # 超时时间20ms
    LINMsg.PID = pid
    LINMsg.CheckType = LIN_EX_CHECK_EXT  # 增强型校验
    LINMsg.DataLen = 8  # LIN标准数据长度

    # 填充数据
    for i in range(min(8, len(data_buffer))):
        LINMsg.Data[i] = data_buffer[i]

    # 发送消息
    ret = LIN_EX_MasterSync(handle, lin_index, byref(LINMsg), byref(LINOutMsg), 1)

    return ret, LINOutMsg


def send_lin_message_fast(handle, pid, data_buffer, msg_type=LIN_EX_MSG_TYPE_MW, timeout=50, lin_index=0):
    """
    快速发送LIN消息（优化版本）
    :param timeout: 超时时间，默认50ms（增加超时时间以减少卡顿）
    :param lin_index: LIN通道索引
    """
    LINOutMsg = LIN_EX_MSG()
    LINMsg = LIN_EX_MSG()

    # 设置消息参数
    LINMsg.MsgType = msg_type
    LINMsg.Timestamp = timeout  # 增加超时时间以减少卡顿
    LINMsg.PID = pid
    LINMsg.CheckType = LIN_EX_CHECK_EXT  # 增强型校验
    LINMsg.DataLen = 8  # LIN标准数据长度

    # 填充数据
    for i in range(min(8, len(data_buffer))):
        LINMsg.Data[i] = data_buffer[i]

    # 发送消息
    ret = LIN_EX_MasterSync(handle, lin_index, byref(LINMsg), byref(LINOutMsg), 1)

    return ret, LINOutMsg


def test_arc_counter_sequence():
    """测试存活计数器的解析逻辑"""
    print("\n" + "=" * 50)
    print("测试存活计数器解析逻辑")
    print("=" * 50)

    # 测试用例：模拟不同情况下的数据
    test_cases = [
        # (byte1值, 期望的计数器值)
        (0b00000000, 0),  # 位1-2 = 00
        (0b00000010, 1),  # 位1-2 = 01 (二进制01，右移1位后取低2位是01=1)
        (0b00000100, 2),  # 位1-2 = 10 (二进制10，右移1位后取低2位是10=2)
        (0b00000110, 3),  # 位1-2 = 11 (二进制11，右移1位后取低2位是11=3)
        (0b00100000, 0),  # 位1-2 = 00 (高位不影响)
        (0b00100010, 1),  # 位1-2 = 01
        (0b00100100, 2),  # 位1-2 = 10
        (0b00100110, 3),  # 位1-2 = 11
    ]

    for byte1_val, expected in test_cases:
        # 模拟数据
        data_bytes = [0x00, byte1_val, 0x00, 0x00]
        signals = parse_response_message(data_bytes)
        arc_counter = signals['arc_counter']['value']

        if arc_counter == expected:
            print(f"✓ byte1=0x{byte1_val:02X} ({byte1_val:08b}): 计数器={arc_counter} (正确)")
        else:
            print(f"✗ byte1=0x{byte1_val:02X} ({byte1_val:08b}): 计数器={arc_counter} (期望{expected})")

    print("=" * 50)


def main():
    """主函数"""
    global running

    # 运行解析逻辑测试
    test_arc_counter_sequence()

    # 1. 查找并打开目标设备
    target_handle = find_target_device()
    if target_handle is None:
        return

    try:
        # 2. 初始化LIN总线
        ret = LIN_EX_Init(target_handle, LINMasterIndex, 19200, LIN_EX_MASTER)
        if ret != LIN_EX_SUCCESS:
            print(f"配置主LIN失败，返回值: {ret}!")
            return
        else:
            print("配置主LIN成功!")

        # 3. 启动键盘监听线程
        keyboard_thread = threading.Thread(target=check_keyboard_input)
        keyboard_thread.daemon = True
        keyboard_thread.start()

        # 4. 初始测试通信
        print("\n" + "=" * 50)
        print("初始通信测试")
        print("=" * 50)

        # 测试发送命令
        test_command = create_command_message(power_percentage=50, enable=True)
        print(f"测试发送命令: 功率=50%, 使能=True")
        print(f"命令数据: {' '.join([f'0x{b:02X}' for b in test_command])}")

        ret, out_msg = send_lin_message(target_handle, 0x24, test_command, LIN_EX_MSG_TYPE_MW)
        if ret != 1:
            print("发送命令失败!")
        else:
            print(f"发送命令成功! 响应PID: 0x{out_msg.PID:02X}")

        sleep(0.1)

        # 测试读取响应
        print("\n测试读取响应...")
        ret, out_msg = send_lin_message(target_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR)

        if ret != 1:
            print("读取响应失败! 尝试备用方法...")
            # 尝试LIN_EX_MasterRead
            read_buffer = (c_byte * 8)()
            ret_read = LIN_EX_MasterRead(target_handle, LINMasterIndex, 0x25, read_buffer)
            if ret_read > 0:
                data_bytes = [read_buffer[i] & 0xFF for i in range(ret_read)]
                print(f"备用方法成功! 数据长度: {ret_read}")
                print(f"响应数据: {' '.join([f'0x{b:02X}' for b in data_bytes])}")

                # 检查是否为回显数据
                if len(data_bytes) >= 2 and data_bytes[:2] == [0x32, 0x01]:
                    print("注意: 收到命令回显数据，非响应数据")
                else:
                    # 解析响应数据
                    signals = parse_response_message(data_bytes)
                    print_response_signals(signals)
            else:
                print("备用方法也失败!")
        else:
            print(f"读取响应成功! 响应PID: 0x{out_msg.PID:02X}, 数据长度: {out_msg.DataLen}")
            if out_msg.DataLen > 0:
                data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                print(f"响应数据: {' '.join([f'0x{b:02X}' for b in data_bytes])}")

                # 解析响应数据
                signals = parse_response_message(data_bytes)
                print_response_signals(signals)
            else:
                print("警告: 数据长度为0!")

        # 5. 主循环 - 添加时间统计功能
        print("\n" + "=" * 50)
        print("开始主循环 - 发送50%功率，使能=1")
        print("=" * 50)

        cycle_count = 0
        arc_history = []  # 记录存活计数器的历史值

        # 【新增】循环时间统计相关变量
        cycle_times = []  # 存储每次循环的耗时
        total_cycle_time = 0  # 总循环时间
        max_cycle_time = 0  # 最大循环时间
        min_cycle_time = float('inf')  # 最小循环时间

        # 记录开始时间
        start_time = perf_counter()

        # 首次循环时间显示标题
        print("\n" + "=" * 60)
        print("循环时间统计")
        print("=" * 60)
        print(f"{'循环序号':<12} {'循环耗时(ms)':<15} {'累计时间(s)':<15} {'状态':<15}")
        print("-" * 60)

        while running:
            cycle_count += 1

            # 【新增】记录循环开始时间
            cycle_start_time = perf_counter()

            # 显示循环标题
            print(f"\n=== 循环 #{cycle_count} ===")

            # 发送BREAK信号
            print("发送BREAK信号...")
            break_msg = LIN_EX_MSG()
            break_msg.MsgType = LIN_EX_MSG_TYPE_BK
            break_msg.Timestamp = 20
            LIN_EX_MasterSync(target_handle, LINMasterIndex, byref(break_msg), byref(break_msg), 1)
            sleep(0.01)

            # 发送命令 (0x24)
            print("发送命令到ID 0x24...")
            command_data = create_command_message(power_percentage=50, enable=True)
            print(f"命令: 功率=50%, 使能=True")
            print(f"数据: {' '.join([f'0x{b:02X}' for b in command_data[:2]])} (有效数据: 2字节)")

            ret, out_msg = send_lin_message_fast(target_handle, 0x24, command_data, LIN_EX_MSG_TYPE_MW)
            if ret != 1:
                print(f"发送命令失败! 响应PID: 0x{out_msg.PID:02X}")
                status = "发送失败"
            else:
                print(f"发送命令成功! 响应PID: 0x{out_msg.PID:02X}")
                status = "成功"

                # 如果是回显数据 (PID 0x64 是增强校验值)
                if out_msg.PID == 0x64 and out_msg.DataLen > 0:
                    echo_data = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                    print(f"收到回显数据: {' '.join([f'0x{b:02X}' for b in echo_data])}")

            # 等待设备处理
            sleep(0.08)  # 稍微调整等待时间

            # 发送BREAK信号
            print("\n发送BREAK信号...")
            LIN_EX_MasterSync(target_handle, LINMasterIndex, byref(break_msg), byref(break_msg), 1)
            sleep(0.01)

            # 读取响应 (0x25)
            print("读取响应从ID 0x25...")
            ret, out_msg = send_lin_message_fast(target_handle, 0x25, (c_byte * 8)(), LIN_EX_MSG_TYPE_MR)

            if ret != 1:
                print("读取响应失败! 尝试备用方法...")
                # 尝试LIN_EX_MasterRead
                read_buffer = (c_byte * 8)()
                ret_read = LIN_EX_MasterRead(target_handle, LINMasterIndex, 0x25, read_buffer)
                if ret_read > 0:
                    data_bytes = [read_buffer[i] & 0xFF for i in range(ret_read)]
                    print(f"备用方法成功! 数据长度: {ret_read}")
                    print(f"响应数据: {' '.join([f'0x{b:02X}' for b in data_bytes])}")

                    # 检查是否为回显数据
                    if len(data_bytes) >= 2 and data_bytes[:2] == [0x32, 0x01]:
                        print("注意: 收到命令回显数据，非响应数据")
                    else:
                        # 解析响应数据
                        signals = parse_response_message(data_bytes)
                        print_response_signals(signals)

                        # 记录存活计数器
                        arc_counter = signals.get('arc_counter', {}).get('value')
                        if arc_counter is not None:
                            arc_history.append(arc_counter)
                else:
                    print("备用方法也失败!")
            else:
                print(f"读取响应成功! 响应PID: 0x{out_msg.PID:02X}, 数据长度: {out_msg.DataLen}")
                if out_msg.DataLen > 0:
                    data_bytes = [out_msg.Data[i] & 0xFF for i in range(out_msg.DataLen)]
                    print(f"响应数据: {' '.join([f'0x{b:02X}' for b in data_bytes])}")

                    # 解析响应数据
                    signals = parse_response_message(data_bytes)
                    print_response_signals(signals)

                    # 记录存活计数器
                    arc_counter = signals.get('arc_counter', {}).get('value')
                    if arc_counter is not None:
                        arc_history.append(arc_counter)

                        # 检查计数器是否在正确循环
                        if len(arc_history) > 1:
                            last_value = arc_history[-2]
                            current_value = arc_history[-1]
                            expected_next = (last_value + 1) % 4

                            if current_value != expected_next:
                                print(
                                    f"\033[93m警告: 存活计数器序列异常! 上一个值={last_value}, 当前值={current_value}, 期望值={expected_next}\033[0m")
                else:
                    print("警告: 数据长度为0!")

            # 显示存活计数器历史
            if arc_history:
                print(f"存活计数器历史 (最近10次): {arc_history[-10:]}")

                # 检查是否有不在0-3范围内的值
                invalid_values = [v for v in arc_history if v < 0 or v > 3]
                if invalid_values:
                    print(f"\033[91m错误: 发现无效的计数器值: {invalid_values}\033[0m")

            # 【新增】计算并显示循环时间统计
            cycle_end_time = perf_counter()
            cycle_duration = cycle_end_time - cycle_start_time  # 本次循环耗时（秒）
            cycle_duration_ms = cycle_duration * 1000  # 转换为毫秒

            # 记录循环时间
            cycle_times.append(cycle_duration_ms)
            total_cycle_time += cycle_duration
            max_cycle_time = max(max_cycle_time, cycle_duration_ms)
            min_cycle_time = min(min_cycle_time, cycle_duration_ms)

            # 计算平均循环时间
            avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else 0

            # 打印循环时间统计
            print(f"\n{'='*60}")
            print(f"循环时间统计 (循环 #{cycle_count})")
            print(f"{'='*60}")
            print(f"本次循环耗时: {cycle_duration_ms:.3f} ms")
            print(f"累计时间: {total_cycle_time:.3f} s")
            print(f"平均循环时间: {avg_cycle_time:.3f} ms")
            print(f"最小循环时间: {min_cycle_time:.3f} ms")
            print(f"最大循环时间: {max_cycle_time:.3f} ms")
            print(f"{'='*60}")

            # 每隔10次循环，显示统计摘要
            if cycle_count % 10 == 0:
                print(f"\n{'='*60}")
                print(f"循环统计摘要 (共 {cycle_count} 次循环)")
                print(f"{'='*60}")
                print(f"平均循环时间: {avg_cycle_time:.3f} ms")
                print(f"最小循环时间: {min_cycle_time:.3f} ms")
                print(f"最大循环时间: {max_cycle_time:.3f} ms")
                print(f"总循环时间: {total_cycle_time:.3f} s")
                print(f"{'='*60}")

            # 循环间隔 - 调整为动态间隔
            target_interval = 0.2  # 目标间隔200ms
            elapsed = perf_counter() - cycle_start_time
            remaining = target_interval - elapsed

            if remaining > 0:
                if remaining > 0.002:  # 大于2ms
                    sleep(remaining)
                else:
                    # 忙等待
                    while perf_counter() - cycle_start_time < target_interval:
                        pass
            else:
                print(f"\033[93m警告: 循环超时! 耗时{cycle_duration_ms:.1f}ms，超过目标间隔{target_interval*1000:.1f}ms\033[0m")

    except Exception as e:
        print(f"运行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭设备
        ret = USB_CloseDevice(target_handle)
        if ret:
            print("\n关闭设备成功!")
        else:
            print("\n关闭设备失败!")

        # 【新增】显示最终统计
        if cycle_count > 0:
            print(f"\n{'='*60}")
            print(f"最终统计 (共 {cycle_count} 次循环)")
            print(f"{'='*60}")
            print(f"总循环时间: {total_cycle_time:.3f} s")
            print(f"平均循环时间: {sum(cycle_times)/len(cycle_times):.3f} ms")
            print(f"最小循环时间: {min_cycle_time:.3f} ms")
            print(f"最大循环时间: {max_cycle_time:.3f} ms")
            print(f"循环成功率: {len([t for t in cycle_times if t < target_interval*1000])}/{cycle_count}")
            print(f"{'='*60}")


if __name__ == '__main__':
    main()
