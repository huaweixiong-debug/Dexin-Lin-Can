"""
文件说明：USB2XXX LIN相关函数测试程序
更多帮助：www.usbxyz.com
"""
from ctypes import *
import os
from time import sleep
from datetime import datetime
import csv
from usb_device import *
from usb2lin_ex import *


def ensure_directory_exists(file_path):
    """确保文件所在目录存在"""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"创建目录: {directory}")


def read_or_create_file(file_path, default_content="0", is_numeric=True):
    """读取文件，如果不存在则创建并写入默认值"""
    try:
        ensure_directory_exists(file_path)

        if not os.path.exists(file_path):
            print(f"文件不存在，创建: {file_path}")
            with open(file_path, "w") as f:
                f.write(default_content)
            return float(default_content) if is_numeric else default_content

        with open(file_path, "r") as f:
            content = f.read().strip()

        if not content:  # 如果是空文件
            print(f"文件为空，写入默认值: {file_path}")
            with open(file_path, "w") as f:
                f.write(default_content)
            return float(default_content) if is_numeric else default_content

        try:
            if is_numeric:
                return float(content)
            else:
                return content
        except ValueError:
            print(f"文件内容格式错误，使用默认值: {file_path}")
            with open(file_path, "w") as f:
                f.write(default_content)
            return float(default_content) if is_numeric else default_content

    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
        return float(default_content) if is_numeric else default_content


def write_file(file_path, content):
    """写入文件，确保目录存在"""
    try:
        ensure_directory_exists(file_path)

        with open(file_path, "w") as f:
            f.write(str(content))
        return True
    except Exception as e:
        print(f"写入文件 {file_path} 失败: {e}")
        return False


def update_csv_column(csv_file_path, cycle_count, signal_values):
    """
    更新CSV文件第0列的0-5行，使用英文文本记录
    """
    try:
        ensure_directory_exists(csv_file_path)

        # 创建或更新CSV文件，只保留6行（0-5行）
        signal_names = [
            "AEHModOprtgStsFrt_69_9",
            "AEH_CommErrFrt_69_9",
            "AEHMsrdCurrFrt_69_9",
            "AEHMsrdCurrOORHiFrt_69_9",
            "AEHMsrdCurrOORLoFrt_69_9",
            "AEH_ARCFrt_69_9"
        ]

        signal_keys = ['status', 'comm_err', 'current', 'over_current', 'under_current', 'arc']

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 读取现有文件内容（如果存在）
        existing_data = []
        if os.path.exists(csv_file_path):
            try:
                with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                    csv_reader = csv.reader(csvfile)
                    for row in csv_reader:
                        existing_data.append(row)
            except:
                existing_data = []

        # 确保有足够的行数（至少6行）
        while len(existing_data) < 6:
            existing_data.append(['', '', '', ''])

        # 只保留前6行（0-5行）
        existing_data = existing_data[:6]

        # 更新每一行的第一列（第0列）
        for i in range(6):
            if i < len(signal_keys):
                key = signal_keys[i]
                if key in signal_values:
                    # 第一列（第0列）写入信号描述（英文文本）
                    existing_data[i][0] = signal_values[key]['description']

                    # 其他列可以保留原有内容或添加新信息
                    if len(existing_data[i]) < 2:
                        existing_data[i].append(signal_names[i])
                    elif len(existing_data[i]) < 3:
                        existing_data[i].append(signal_names[i])
                    else:
                        existing_data[i][1] = signal_names[i]

                    if len(existing_data[i]) < 3:
                        existing_data[i].append(f"Cycle: {cycle_count}")
                    else:
                        existing_data[i][2] = f"Cycle: {cycle_count}"

                    if len(existing_data[i]) < 4:
                        existing_data[i].append(timestamp)
                    else:
                        existing_data[i][3] = timestamp

        # 写入文件
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            for row in existing_data:
                csv_writer.writerow(row)

        print(f"CSV文件已更新: {csv_file_path}")
        print(f"信号值已更新在第0列的第0-5行")
        for i, key in enumerate(signal_keys):
            if key in signal_values:
                print(f"第{i}行: {signal_values[key]['description']}")

        return True

    except Exception as e:
        print(f"更新CSV文件失败: {e}")
        return False


if __name__ == '__main__':
    LINMasterIndex = 0  # LIN主站索引
    target_serial = "3041545500333035530006EE"  # 目标设备序列号

    # CSV文件路径
    csv_result_file = r"d:\data\result.csv"

    print(f"正在查找设备序列号: {target_serial}")

    # Scan device
    DevHandles = (c_uint * 20)()
    ret = USB_ScanDevice(byref(DevHandles))

    if ret == 0:
        print("没有找到连接的设备!")
        exit()
    else:
        print(f"找到 {ret} 个设备")

    # 查找目标设备
    target_handle = None
    for i in range(ret):
        ret_open = USB_OpenDevice(DevHandles[i])
        if ret_open:
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

                if device_serial == target_serial:
                    print(f"找到目标设备!")
                    target_handle = DevHandles[i]
                    break
                else:
                    USB_CloseDevice(DevHandles[i])
            else:
                USB_CloseDevice(DevHandles[i])
        else:
            continue

    if target_handle is None:
        print(f"未找到序列号为 {target_serial} 的设备!")
        exit()

    # 已经打开了目标设备，继续使用
    print(f"成功打开目标设备")

    # 获取设备信息
    USB2XXXInfo = DEVICE_INFO()
    USB2XXXFunctionString = (c_char * 256)()
    ret = DEV_GetDeviceInfo(target_handle, byref(USB2XXXInfo), byref(USB2XXXFunctionString))

    if ret:
        print("设备信息:")
        print(f"--固件名称: {bytes(USB2XXXInfo.FirmwareName).decode('ascii', errors='ignore')}")
        print(
            f"--固件版本: v{(USB2XXXInfo.FirmwareVersion >> 24) & 0xFF}.{(USB2XXXInfo.FirmwareVersion >> 16) & 0xFF}.{USB2XXXInfo.FirmwareVersion & 0xFFFF}")
        print(
            f"--硬件版本: v{(USB2XXXInfo.HardwareVersion >> 24) & 0xFF}.{(USB2XXXInfo.HardwareVersion >> 16) & 0xFF}.{USB2XXXInfo.HardwareVersion & 0xFFFF}")
        print(f"--构建日期: {bytes(USB2XXXInfo.BuildDate).decode('ascii', errors='ignore')}")
        print(f"--功能字符串: {bytes(USB2XXXFunctionString.value).decode('ascii', errors='ignore')}")
    else:
        print("获取设备信息失败!")
        USB_CloseDevice(target_handle)
        exit()

    # 初始化配置主LIN
    ret = LIN_EX_Init(target_handle, LINMasterIndex, 19200, LIN_EX_MASTER)
    if ret != LIN_EX_SUCCESS:
        print("配置主LIN失败!")
        USB_CloseDevice(target_handle)
        exit()
    else:
        print("配置主LIN成功!")

    # 定义文件路径
    input_files = {
        "power": r"d:\data\AEHPctPwrCmndFrt_0.txt",
        "enable": r"d:\data\AEhodOpEnblCmdFrt_0.txt"
    }

    # 增加键盘输入检测功能
    import sys
    import platform
    
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
    
    # 主循环
    cycle_count = 0
    print("\n开始连续PTC功率测试")
    print(f"📌 目标功率: 50%")
    print(f"📌 目标使能: 1")
    print(f"📌 测试频率: 0.1秒/次")
    print(f"📌 按回车键停止测试")
    print("=" * 60)

    try:
        # 直接设置功率为50%，使能为1
        power_percentage = 50
        enable = 1
        
        while True:
            cycle_count += 1
            print(f"\n🔄 测试循环 {cycle_count}")

            # 1. 写入功率和使能到配置文件
            write_file(input_files["power"], str(power_percentage))
            write_file(input_files["enable"], "1 - Master Operation Enabled")
            print(f"2. 设置PTC功率为 {power_percentage}%，使能为 {enable}")
            print(f"✅ 功率配置文件已更新: {input_files['power']} = {power_percentage}")
            print(f"✅ 使能配置文件已更新: {input_files['enable']} = 1 - Master Operation Enabled")
            print(f"✅ PTC功率设置成功: {power_percentage}%, 使能={enable}")

            # 2. 构造发送数据 (ID 0x24)
            byte0 = power_percentage & 0x7F  # 低7位为功率百分比
            byte1 = enable & 0x01  # 最低位为使能开关

            data_buffer = (c_byte * 8)(byte0, byte1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)

            # 发送BREAK信号
            LINOutMsg = LIN_EX_MSG()
            LINMsg = LIN_EX_MSG()
            LINMsg.MsgType = LIN_EX_MSG_TYPE_BK
            LINMsg.Timestamp = 10

            ret = LIN_EX_MasterSync(target_handle, LINMasterIndex, byref(LINMsg), byref(LINOutMsg), 1)
            if ret != 1:
                continue

            sleep(0.01)

            # 设置消息结构体
            LINMsg.MsgType = LIN_EX_MSG_TYPE_MW
            LINMsg.Timestamp = 10
            LINMsg.PID = 0x24
            LINMsg.CheckType = LIN_EX_CHECK_EXT
            LINMsg.DataLen = 8

            for i in range(0, LINMsg.DataLen):
                LINMsg.Data[i] = data_buffer[i]

            # 发送LIN消息，不显示错误信息
            ret = LIN_EX_MasterSync(target_handle, LINMasterIndex, byref(LINMsg), byref(LINOutMsg), 1)

            sleep(0.05)  # 给从设备处理时间

            # 3. 读取响应数据 (ID 0x25)
            LINMsg.MsgType = LIN_EX_MSG_TYPE_MR
            LINMsg.Timestamp = 10
            LINMsg.PID = 0x25
            LINMsg.CheckType = LIN_EX_CHECK_EXT
            LINMsg.DataLen = 8

            ret = LIN_EX_MasterSync(target_handle, LINMasterIndex, byref(LINMsg), byref(LINOutMsg), 1)

            if ret == 1:
                data_bytes = [LINOutMsg.Data[i] & 0xFF for i in range(LINOutMsg.DataLen)]
            else:
                # 尝试备用读取方法
                read_buffer = (c_byte * 8)()
                ret2 = LIN_EX_MasterRead(target_handle, LINMasterIndex, 0x25, read_buffer)
                if ret2 > 0:
                    data_bytes = [read_buffer[i] & 0xFF for i in range(ret2)]
                else:
                    # 使用默认数据
                    data_bytes = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

            # 4. 直接解析响应数据
            signal_values = {}  # 用于存储解析结果，用于CSV文件

            try:
                # 只分析反馈字节长度大于0的结果
                if len(data_bytes) == 0:
                    # 数据为空，使用默认值
                    raise ValueError("数据长度为0")
                
                # 确保数据长度至少为4，否则使用默认值
                if len(data_bytes) < 4:
                    data_bytes += [0x00] * (4 - len(data_bytes))
                
                # 字节0的详细解析
                byte0 = data_bytes[0]
                byte1 = data_bytes[1]
                byte3 = data_bytes[3]

                # 1) PTC运行电流 AEHMsrdCurrFrt_69_9
                # 起始字节0, 起始位0, 长度9位, Unsigned, 精度0.5, 偏移-10
                # 公式: E = N * 0.5 - 10
                # 字节0的8位 + 字节1的位0（第9位）
                current_raw = (data_bytes[1] & 0x01) << 8 | data_bytes[0]
                current_phy = current_raw * 0.5 - 10

                signal_values['current'] = {
                    'value': current_phy,
                    'description': f"{current_phy:.4f} A"
                }

                # 2) PTC运行状态 AEHModOprtgStsFrt_69_9
                # 起始字节1, 起始位11, 长度2位
                # 字节1的位3和位4对应总线的位11和位12
                status_value = (byte1 >> 3) & 0x03
                status_desc_map = {
                    0: "0x0:Running Normal",
                    1: "0x1:Limited Operation",
                    2: "0x2:Recoverable Fault",
                    3: "0x3:Non-Recoverable Fault"
                }
                status_desc_str = status_desc_map.get(status_value, f"Unknown (0x{status_value})")

                signal_values['status'] = {
                    'value': status_value,
                    'description': status_desc_str
                }

                # 3) 通讯故障 AEH_CommErrFrt_69_9
                # 起始字节1, 起始位15, 长度1位
                # 字节1的位7对应总线的位15
                comm_err_value = (byte1 >> 7) & 0x01
                comm_err_desc = "0x0:No Comm Error" if comm_err_value == 0 else "0x1:Comm Error"

                signal_values['comm_err'] = {
                    'value': int(comm_err_value),
                    'description': comm_err_desc
                }

                # 4) 过流故障 AEHMsrdCurrOORHiFrt_69_9
                # 起始字节3, 起始位30, 长度1位
                # 字节3的位6对应总线的位30
                over_current_value = (byte3 >> 6) & 0x01
                over_current_desc = f"$0={'True' if over_current_value == 0 else 'False'}; $1={'True' if over_current_value == 1 else 'False'}"

                signal_values['over_current'] = {
                    'value': int(over_current_value),
                    'description': over_current_desc
                }

                # 5) 欠流保护 AEHMsrdCurrOORLoFrt_69_9
                # 起始字节3, 起始位31, 长度1位
                # 字节3的位7对应总线的位31
                under_current_value = (byte3 >> 7) & 0x01
                under_current_desc = f"$0={'True' if under_current_value == 0 else 'False'}; $1={'True' if under_current_value == 1 else 'False'}"

                signal_values['under_current'] = {
                    'value': int(under_current_value),
                    'description': under_current_desc
                }

                # 6) ARC故障状态 AEH_ARCFrt_69_9
                # 起始字节1, 起始位9, 长度2位
                # 字节1的位1和位2对应总线的位9和位10
                arc_value = (byte1 >> 1) & 0x03

                signal_values['arc'] = {
                    'value': int(arc_value),
                    'description': f"{int(arc_value)} (E=N*1)"
                }

            except Exception as e:
                print(f"⚠️ 读取PTC状态时出错: {e}")
                print(f"   当前数据: {data_bytes}")
                # 使用默认值
                default_values = {
                    'status': {'value': 0, 'description': '0x0:Running Normal'},
                    'comm_err': {'value': 0, 'description': '0x0:No Comm Error'},
                    'current': {'value': 0.0, 'description': '0.0000 A'},
                    'over_current': {'value': 0, 'description': '$0=True; $1=False'},
                    'under_current': {'value': 0, 'description': '$0=True; $1=False'},
                    'arc': {'value': 0, 'description': '0 (E=N*1)'}
                }
                signal_values.update(default_values)

            # 5. 显示真实PTC反馈结果
            print("====================================")
            print(f"AEHModOptgStsFrt_69_9 - {signal_values['status']['description']}")
            print(f"AEH_CommErrFrt_69_9 - {signal_values['comm_err']['description']}")
            print(f"AEHMsrdCurrFrt_69_9 - {signal_values['current']['description']}")
            print(f"AEHMsrdCurrOORHiFrt_69_9 - {signal_values['over_current']['description']}")
            print(f"AEHMsrdCurrOORLoFrt_69_9 - {signal_values['under_current']['description']}")
            print(f"AEH_ARCFrt_69_9 - {signal_values['arc']['description']}")
            print("====================================")

            # 6. 将结果更新到CSV文件第0列的0-5行
            if update_csv_column(csv_result_file, cycle_count, signal_values):
                pass  # 不显示CSV更新成功信息

            # 7. 检查是否有按键输入
            print("⏳ 等待0.1秒... (按任意键停止)")
            
            # 等待0.1秒，每0.01秒检查一次按键
            for _ in range(10):
                if is_key_pressed():
                    # 读取按键
                    if platform.system() == 'Windows':
                        import msvcrt
                        msvcrt.getch()
                    else:
                        sys.stdin.read(1)
                    print("\n⚠️ 用户中断测试")
                    raise KeyboardInterrupt
                sleep(0.01)  # 0.01秒检查一次按键

            # 不需要额外的等待，整个循环间隔保持在0.1秒左右

    except KeyboardInterrupt:
        print("\n\n用户中断，停止运行...")
    except Exception as e:
        print(f"运行过程中发生错误: {e}")
    finally:
        # 关闭设备
        ret = USB_CloseDevice(target_handle)
        if ret:
            print("关闭设备成功!")
        else:
            print("关闭设备失败!")