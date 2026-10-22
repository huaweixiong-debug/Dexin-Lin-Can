import serial
import time
import struct
import threading
import csv
from datetime import datetime
from pathlib import Path


class ProgrammablePowerSupply:
    # 类级变量，用于跨实例共享资源
    _serial_ports = {}     # 存储物理串口对象: {'COM4': serial.Serial object}
    _port_locks = {}       # 存储端口锁: {'COM4': threading.Lock()}
    _last_com_time = {}    # 存储端口最后通信时间: {'COM4': timestamp}
    _instance_counts = {}  # 存储端口引用计数: {'COM4': count}
    _global_lock = threading.Lock() # 用于保护上述类级变量的修改

    def __init__(self, port='COM4', baudrate=9600, timeout=1, station_address=1):
        """
        初始化程控电源通信类

        参数:
            port: 串口号，如 'COM1' 或 '/dev/ttyUSB0'
            baudrate: 波特率，默认为9600
            timeout: 超时时间
            station_address: 站地址，默认为1
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.station_address = station_address
        self.broadcast_address = 255  # 广播地址
        self.serial = None

        # 电压和电流的转换系数（根据实际测试调整）
        self.voltage_factor = 100  # 1V = 100个原始单位，根据实际电源显示调整
        self.current_factor = 100  # 与电压系数保持一致
        
        # 电流最大值设置（单位：A）
        self.current_max = 200.0  # 将电流最大值设置为200A

        # 文件路径
        self.time_file = Path(r'd:\data\时间.txt')
        self.voltage_setting_file = Path(r'd:\data\设置电压.txt')
        self.actual_voltage_file = Path(r'd:\data\实际电压.txt')
        self.actual_current_file = Path(r'd:\data\实际电流.txt')
        self.test_log_file = Path(r'd:\data\测试日志.txt')

        # 测试参数
        self.under_voltage = 12.0  # 欠压电压：12V
        self.normal_voltage = 13.0  # 正常电压：13V
        self.over_voltage = 16.0  # 过压电压：16V

        # 确保目录存在
        for file_path in [self.time_file, self.voltage_setting_file,
                          self.actual_voltage_file, self.actual_current_file,
                          self.test_log_file]:
            file_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """连接到程控电源 (支持多线程共享同一端口)"""
        with ProgrammablePowerSupply._global_lock:
            # 1. 确保该端口的锁和时间记录存在
            if self.port not in ProgrammablePowerSupply._port_locks:
                ProgrammablePowerSupply._port_locks[self.port] = threading.Lock()
            
            if self.port not in ProgrammablePowerSupply._last_com_time:
                ProgrammablePowerSupply._last_com_time[self.port] = 0.0
                
            # 2. 检查是否已有实例打开了该端口
            if self.port in ProgrammablePowerSupply._serial_ports:
                # 复用现有连接
                self.serial = ProgrammablePowerSupply._serial_ports[self.port]
                # 增加引用计数 (如果尚未记录该端口的计数，初始化为1，因为现有连接至少有一个持有者)
                if self.port not in ProgrammablePowerSupply._instance_counts:
                    ProgrammablePowerSupply._instance_counts[self.port] = 1 # 假设之前的持有者计数为1
                
                ProgrammablePowerSupply._instance_counts[self.port] += 1
                print(f"[{self.station_address}] 复用端口 {self.port} 连接 (当前引用数: {ProgrammablePowerSupply._instance_counts[self.port]})")
                return True
            
            # 3. 如果没有，建立新连接
            try:
                # 如果已有连接（虽然不应该发生，因为上面检查了_serial_ports），先断开
                if self.serial and self.serial.is_open:
                    self.serial.close()
                
                ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout
                )
                
                self.serial = ser
                # 注册到共享资源
                ProgrammablePowerSupply._serial_ports[self.port] = ser
                ProgrammablePowerSupply._instance_counts[self.port] = 1
                
                print(f"[{self.station_address}] 成功新建连接到 {self.port}，波特率 {self.baudrate}")
                return True
            except PermissionError as e:
                print(f"❌ 连接失败: {e}")
                print("📋 解决方案:")
                print("   1. 检查该端口是否已被其他程序占用")
                print("   2. 尝试关闭其他可能占用该端口的程序")
                print("   3. 以管理员身份运行程序")
                print("   4. 检查设备管理器中端口的状态")
                print(f"   5. 尝试更换为其他可用的COM端口")
                return False
            except FileNotFoundError as e:
                print(f"❌ 连接失败: {e}")
                print("📋 解决方案:")
                print("   1. 检查端口名称是否正确")
                print("   2. 确认设备已正确连接到电脑")
                print("   3. 检查设备驱动是否已正确安装")
                return False
            except Exception as e:
                print(f"❌ 连接失败: {e}")
                print("📋 解决方案:")
                print("   1. 检查串口线连接是否正常")
                print("   2. 确认设备已开机并正常工作")
                print("   3. 检查波特率、数据位等参数是否正确")
                return False

    def disconnect(self):
        """断开连接 (减少引用计数，仅在无引用时关闭物理端口)"""
        with ProgrammablePowerSupply._global_lock:
            if self.port in ProgrammablePowerSupply._instance_counts:
                ProgrammablePowerSupply._instance_counts[self.port] -= 1
                print(f"[{self.station_address}] 断开端口 {self.port} 引用 (剩余: {ProgrammablePowerSupply._instance_counts[self.port]})")
                
                if ProgrammablePowerSupply._instance_counts[self.port] <= 0:
                    # 最后一个用户断开，关闭物理连接
                    if self.port in ProgrammablePowerSupply._serial_ports:
                        ser = ProgrammablePowerSupply._serial_ports[self.port]
                        if ser and ser.is_open:
                            try:
                                ser.close()
                                print(f"端口 {self.port} 物理连接已关闭")
                            except Exception as e:
                                print(f"关闭端口 {self.port} 时出错: {e}")
                        
                        del ProgrammablePowerSupply._serial_ports[self.port]
                        # 可选：清理锁和时间记录，或者保留以备后用
                        # del ProgrammablePowerSupply._port_locks[self.port]
                        # del ProgrammablePowerSupply._instance_counts[self.port]
            
            self.serial = None

    def calculate_crc(self, data):
        """
        计算MODBUS CRC16校验码

        参数:
            data: 字节数组

        返回:
            CRC16校验码（2字节）
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        # 返回低位在前，高位在后的格式
        return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    def send_command(self, command, verbose=True):
        """
        发送命令并接收响应，增加响应等待时间和严格的CRC校验
        此方法现在是线程安全的，并且强制执行最小通信间隔。

        参数:
            command: 命令字节数组
            verbose: 是否打印详细日志，默认为True

        返回:
            响应数据字节数组或None
        """
        if not self.serial or not self.serial.is_open:
            if verbose:
                print("未连接")
            return None

        # 获取当前端口的锁
        port_lock = ProgrammablePowerSupply._port_locks.get(self.port)
        if not port_lock:
             if verbose: print(f"错误: 找不到端口 {self.port} 的锁")
             return None

        with port_lock:
            # 强制执行5ms最小间隔
            current_time = time.time()
            last_time = ProgrammablePowerSupply._last_com_time.get(self.port, 0)
            elapsed = current_time - last_time
            min_interval = 0.005 # 5ms
            
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                # if verbose: print(f"等待通信间隔: {sleep_time*1000:.2f}ms")
                time.sleep(sleep_time)

            try:
                # 清空缓冲区
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()

                # 发送命令
                if verbose:
                    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [{getattr(self, 'station_idx', 'Main')}] 发送命令: {command.hex().upper()}")
                self.serial.write(command)

                # 增加等待时间，给电源更多响应时间
                # 优化: 从0.3秒减少到0.05秒，以避免阻塞主循环太久
                # 如果设备响应慢，可以适当增加，但不能太长
                time.sleep(0.05)  

                # 读取响应
                response = self.serial.read_all()
                
                # 更新最后通信时间
                ProgrammablePowerSupply._last_com_time[self.port] = time.time()

                if response:
                    if verbose:
                        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [{getattr(self, 'station_idx', 'Main')}] 收到响应: {response.hex().upper()}")
                    
                    # 检查响应是否符合基本格式
                    if len(response) < 5:  # 至少需要地址、功能码、数据长度和CRC
                        if verbose:
                            print("响应长度不足")
                        return None
                    
                    # 检查响应地址是否匹配
                    if response[0] != self.station_address:
                        if verbose:
                            print(f"响应地址不匹配: 收到{response[0]}, 期望{self.station_address}")
                        return None
                    
                    # 检查功能码是否匹配或为错误码
                    if response[1] == command[1]:
                        # 功能码匹配，正常响应
                        pass
                    elif response[1] == (command[1] | 0x80):
                        # 功能码最高位为1，表示错误响应
                        if verbose:
                            print(f"设备返回错误: 错误码{response[2]}")
                        return None
                    else:
                        # 功能码不匹配，可能是设备返回了不同的功能码，尝试接受此响应继续执行
                        # 有些设备可能会返回不同的功能码，这里放松检查，确保程序能够继续运行
                        if verbose:
                            print(f"功能码不匹配: 收到{response[1]}, 期望{command[1]}，尝试接受此响应继续执行")
                        # 继续处理响应，不直接返回None
                        pass
                    
                    # 严格验证CRC，只有CRC正确才返回响应
                    if len(response) >= 2:
                        received_crc = response[-2:]
                        calculated_crc = self.calculate_crc(response[:-2])

                        if received_crc == calculated_crc:
                            return response
                        else:
                            if verbose:
                                print(f"CRC校验失败: 收到{received_crc.hex()}，计算{calculated_crc.hex()}")
                            return None
                else:
                    if verbose:
                        print(f"[{getattr(self, 'station_idx', 'Main')}] 无响应")
                    return None
            except Exception as e:
                print(f"通信异常: {e}")
                return None

    def read_power_status(self, verbose=False):
        """
        读取电源状态（输出电压和电流），增加重试机制和等待时间

        参数:
            verbose: 是否打印详细日志，默认为False

        返回:
            (电压, 电流, 状态) 或 (None, None, None)
        """
        # 构建读取状态命令：使用功能码0x04(读输入寄存器)，因为测量值（电压、电流）存储在输入寄存器中
        # 保持寄存器(0x03)用于设置值，输入寄存器(0x04)用于测量值
        command = bytes([
            self.station_address,  # 站地址
            0x04,  # 功能码：读输入寄存器（改回0x04，之前错误地改为0x03）
            0x00, 0x00,  # 起始地址：0000
            0x00, 0x03,  # 寄存器数量：3
        ])

        # 添加CRC
        crc = self.calculate_crc(command)
        command += crc

        # 增加重试机制，最多重试3次
        for retry in range(3):
            if verbose:
                print(f"发送读取状态命令: {command.hex().upper()} (重试 {retry+1}/3)")
            response = self.send_command(command, verbose=verbose)

            if response:
                if verbose:
                    print(f"响应长度: {len(response)}")
                
                # 即使响应长度不足11字节，也要尝试解析
                if len(response) >= 9:
                    try:
                        # 解析状态
                        status_raw = (response[3] << 8) | response[4]

                        # 解析状态位
                        status_bits = {
                            'working': bool(status_raw & 0x0001),  # BIT0: 工作/待机
                            'remote_control': bool(status_raw & 0x0002),  # BIT1: 程控/近控
                            'constant_current': bool(status_raw & 0x0004),  # BIT2: 恒流/恒压
                            'overvoltage_fault': bool(status_raw & 0x0008),  # BIT3: 过压故障
                            'short_circuit_fault': bool(status_raw & 0x0010),  # BIT4: 短路故障
                            'reference_fault': bool(status_raw & 0x0020)  # BIT5: 基准源故障
                        }

                        # 解析电压 - 正确的寄存器地址
                        # 功能码0x03响应格式：站地址+功能码+数据长度+寄存器1+寄存器2+寄存器3+CRC
                        # 寄存器1: 状态
                        # 寄存器2: 电压
                        # 寄存器3: 电流
                        voltage_raw = (response[5] << 8) | response[6]
                        voltage = voltage_raw / self.voltage_factor

                        # 解析电流 - 正确的寄存器地址
                        current_raw = (response[7] << 8) | response[8]
                        current = current_raw / self.current_factor
                        
                        # 增加范围检查，防止异常值
                        if voltage > 200.0 or voltage < 0.0:  # 电压超过200V或小于0V视为异常
                            if verbose:
                                print(f"⚠️  电压异常: {voltage:.2f}V，超出合理范围，忽略此读数")
                            # 重试
                            time.sleep(0.2)
                            continue
                        
                        if current > 200.0 or current < 0.0:  # 电流超过200A或小于0A视为异常
                            if verbose:
                                print(f"⚠️  电流异常: {current:.2f}A，超出合理范围，忽略此读数")
                            # 重试
                            time.sleep(0.2)
                            continue
                        
                        if verbose:
                            print(f"解析结果 - 电压: {voltage:.2f}V, 电流: {current:.2f}A")

                        return voltage, current, status_bits
                    except Exception as e:
                        if verbose:
                            print(f"解析响应失败: {e}，重试")
                        time.sleep(0.2)
                        continue
                else:
                    if verbose:
                        print(f"响应长度不足，无法完整解析: {response.hex().upper()}，重试")
                    time.sleep(0.2)
                    continue
            else:
                if verbose:
                    print(f"读取状态失败，重试 {retry+1}/3")
                time.sleep(0.2)
                continue
        
        # 所有重试都失败
        if verbose:
            print("读取状态失败，所有重试都已完成")
        return None, None, None

    def set_voltage(self, voltage):
        """
        设置电压值

        参数:
            voltage: 电压值（单位：V）

        返回:
            True/False
        """
        print(f"🔧 设置电压: {voltage}V")
        
        # 增加重试机制，确保电压设置成功
        max_retries = 5  # 增加重试次数到5次
        success = False
        
        for retry in range(max_retries):
            print(f"   重试 {retry+1}/{max_retries}")
            
            # 1. 首先关闭电源输出，确保设置能正确应用
            print("   步骤1: 关闭电源输出")
            self.power_off()
            time.sleep(0.5)  # 等待电源关闭
            
            # 2. 检查是否处于远程控制模式
            print("   步骤2: 检查电源状态")
            power_status = self.read_power_status(verbose=True)  # 设置电压前检查状态，打印详细日志
            # 处理read_power_status可能返回None或包含None值的情况
            status_bits = None
            current_voltage = None
            
            if power_status is None:
                print("❌ 无法读取电源状态，跳过远程控制模式检查")
            else:
                voltage_actual, current, status_bits = power_status
                # 检查电压和电流是否为None
                if voltage_actual is not None and current is not None:
                    current_voltage = voltage_actual
                    print(f"   当前实际电压: {current_voltage:.2f}V, 当前实际电流: {current:.2f}A")
                else:
                    print("   当前实际电压: 未知, 当前实际电流: 未知")
                    status_bits = None  # 无法读取状态，跳过远程控制模式检查
            
            if status_bits and not status_bits['remote_control']:
                print("⚠️  电源未处于远程控制模式，但尝试继续设置电压")
                # 不直接返回False，继续尝试设置电压
                # 有些电源可能虽然报告未处于远程控制模式，但仍然可以接收命令
                pass
            
            # 3. 将电压值转换为协议格式
            print("   步骤3: 构建设置电压命令")
            voltage_raw = int(voltage * self.voltage_factor)
            print(f"   电压原始值: {voltage_raw} (0x{voltage_raw:04X})")

            # 构建设置电压命令：01 06 00 01 电压值 CRC
            command = bytes([
                self.station_address,  # 站地址
                0x06,  # 功能码：写单个寄存器
                0x00, 0x01,  # 寄存器地址：0001（电压设置）
                (voltage_raw >> 8) & 0xFF,  # 电压值高字节
                voltage_raw & 0xFF,  # 电压值低字节
            ])

            # 添加CRC
            crc = self.calculate_crc(command)
            command += crc

            print(f"发送设置电压命令: {command.hex().upper()}")
            response = self.send_command(command)

            if response:
                print(f"收到响应: {response.hex().upper()}")
                
                # 4. 打开电源输出
                print("   步骤4: 打开电源输出")
                self.power_on()
                time.sleep(0.5)  # 等待电源开启
                
                # 5. 设置后读取实际电压，验证设置是否生效
                print("   步骤5: 验证电压设置")
                time.sleep(1.0)  # 增加等待时间到1秒，确保电压稳定
                verify_status = self.read_power_status(verbose=True)
                if verify_status and verify_status[0] is not None:
                    verify_voltage, verify_current, _ = verify_status
                    print(f"✅ 电压设置验证: 期望 {voltage}V, 实际 {verify_voltage:.2f}V")
                    
                    # 验证电压是否在允许的误差范围内（±1V，增加容错范围）
                    if abs(verify_voltage - voltage) <= 1.0:
                        print(f"✅ 电压设置成功，误差在允许范围内 (±1.0V)")
                        success = True
                        break
                    else:
                        print(f"⚠️  电压设置误差较大，重试...")
                else:
                    print("⚠️  无法验证电压设置，重试...")
            else:
                print("⚠️  设置电压命令无响应，重试...")
            
            # 重试间隔
            time.sleep(1.0)  # 增加重试间隔到1秒
        
        if success:
            # 再次读取电压，确保最终状态正确
            final_status = self.read_power_status(verbose=True)
            if final_status and final_status[0] is not None:
                final_voltage, _, _ = final_status
                print(f"🎉 最终电压状态: {final_voltage:.2f}V")
            return True
        else:
            print("❌ 电压设置失败，所有重试都已完成")
            return False

    def set_current(self, current):
        """
        设置电流值

        参数:
            current: 电流值（单位：A）

        返回:
            True/False
        """
        # 检查电流是否超过最大值
        if current > self.current_max:
            print(f"⚠️ 电流 {current}A 超过最大值 {self.current_max}A，将被限制为最大值")
            current = self.current_max
        
        # 将电流值转换为协议格式
        current_raw = int(current * self.current_factor)

        # 构建设置电流命令：01 06 00 02 电流值 CRC
        command = bytes([
            self.station_address,  # 站地址
            0x06,  # 功能码：写单个寄存器
            0x00, 0x02,  # 寄存器地址：0002（电流设置）
            (current_raw >> 8) & 0xFF,  # 电流值高字节
            current_raw & 0xFF,  # 电流值低字节
        ])

        # 添加CRC
        crc = self.calculate_crc(command)
        command += crc

        print(f"发送设置电流命令: {command.hex().upper()}")
        response = self.send_command(command)

        if response:
            print(f"收到响应: {response.hex().upper()}")
            return True
        else:
            print("设置电流失败")
            return False

    def power_on(self):
        """开机"""
        command = bytes([
            self.station_address,  # 站地址
            0x06,  # 功能码：写单个寄存器
            0x00, 0x00,  # 寄存器地址：0000（控制）
            0x00, 0xFF,  # 开机值：00FF
        ])

        crc = self.calculate_crc(command)
        command += crc

        print(f"发送开机命令: {command.hex().upper()}")
        response = self.send_command(command)

        if response:
            print("开机成功")
            return True
        else:
            print("开机失败")
            return False

    def power_off(self):
        """待机"""
        command = bytes([
            self.station_address,  # 站地址
            0x06,  # 功能码：写单个寄存器
            0x00, 0x00,  # 寄存器地址：0000（控制）
            0x00, 0x00,  # 待机值：0000
        ])

        crc = self.calculate_crc(command)
        command += crc

        print(f"发送待机命令: {command.hex().upper()}")
        response = self.send_command(command)

        if response:
            print("待机成功")
            return True
        else:
            print("待机失败")
            return False

    def set_station_address(self, new_address):
        """
        设置站地址（通过广播地址）

        参数:
            new_address: 新站地址（1-127）

        返回:
            True/False
        """
        if not 1 <= new_address <= 127:
            print("站地址必须在1-127范围内")
            return False

        command = bytes([
            self.broadcast_address,  # 广播地址
            0x06,  # 功能码：写单个寄存器
            0x00, 0x04,  # 寄存器地址：0004（站地址设置）
            0x00, new_address,  # 新站地址
        ])

        crc = self.calculate_crc(command)
        command += crc

        print(f"发送设置站地址命令: {command.hex().upper()}")
        response = self.send_command(command)

        if response:
            print(f"站地址设置为: {new_address}")
            self.station_address = new_address
            return True
        else:
            print("设置站地址失败")
            return False

    def read_product_settings(self, csv_file_path, product_model="A061"):
        """
        从CSV文件读取产品设置

        参数:
            csv_file_path: CSV文件路径
            product_model: 产品型号，默认为"A061"

        返回:
            包含时间设置的字典 或 None
        """
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                for row in csv_reader:
                    if row['产品型号'] == product_model:
                        # 提取时间设置（转换为整数）
                        settings = {
                            'high_voltage_undervoltage_time': int(row['高压欠压时间']),
                            'high_voltage_undervoltage_recovery_time': int(row['高压欠压恢复时间']),
                            'high_voltage_overvoltage_time': int(row['高压过压时间']),
                            'high_voltage_overvoltage_recovery_time': int(row['高压过压恢复时间']),
                            '100%_power_time': int(row['100%功率时间']),
                            '0%_power_time_1': int(row['0%功率时间']),
                            '70%_power_time': int(row['70%功率时间']),
                            '0%_power_time_2': int(row['0%功率时间']),  # 注意：CSV中有两个0%功率时间列名相同
                            '50%_power_time': int(row['50%功率时间']),
                            '0%_power_time_3': int(row['0%功率时间']),  # 同上
                            '30%_power_time': int(row['30%功率时间']),
                            '0%_power_time_4': int(row['0%功率时间']),  # 同上
                            '10%_power_time': int(row['10%功率时间']),
                            '0%_power_time_5': int(row['0%功率时间'])  # 同上
                        }
                        return settings

            print(f"未找到产品型号: {product_model}")
            return None

        except Exception as e:
            print(f"读取产品设置CSV文件失败: {e}")
            return None

    def generate_test_sequence(self, product_settings):
        """
        根据产品设置生成测试序列

        参数:
            product_settings: 产品设置字典

        返回:
            测试序列列表，每个元素为(阶段名称, 电压, 时间)
        """
        sequence = []

        # 阶段1: 欠压(12V)
        sequence.append(("欠压", self.under_voltage, product_settings['high_voltage_undervoltage_time']))

        # 阶段2: 欠压恢复(13V)
        sequence.append(("欠压恢复", self.normal_voltage, product_settings['high_voltage_undervoltage_recovery_time']))

        # 阶段3: 过压(16V)
        sequence.append(("过压", self.over_voltage, product_settings['high_voltage_overvoltage_time']))

        # 阶段4: 过压恢复(13V)
        sequence.append(("过压恢复", self.normal_voltage, product_settings['high_voltage_overvoltage_recovery_time']))

        # 阶段5: 100%功率(13V)
        sequence.append(("100%功率测试", self.normal_voltage, product_settings['100%_power_time']))

        # 阶段6: 0%功率(13V)
        sequence.append(("0%功率测试1", self.normal_voltage, product_settings['0%_power_time_1']))

        # 阶段7: 70%功率(13V)
        sequence.append(("70%功率测试", self.normal_voltage, product_settings['70%_power_time']))

        # 阶段8: 0%功率(13V)
        sequence.append(("0%功率测试2", self.normal_voltage, product_settings['0%_power_time_2']))

        # 阶段9: 50%功率(13V)
        sequence.append(("50%功率测试", self.normal_voltage, product_settings['50%_power_time']))

        # 阶段10: 0%功率(13V)
        sequence.append(("0%功率测试3", self.normal_voltage, product_settings['0%_power_time_3']))

        # 阶段11: 30%功率(13V)
        sequence.append(("30%功率测试", self.normal_voltage, product_settings['30%_power_time']))

        # 阶段12: 0%功率(13V)
        sequence.append(("0%功率测试4", self.normal_voltage, product_settings['0%_power_time_4']))

        # 阶段13: 10%功率(13V)
        sequence.append(("10%功率测试", self.normal_voltage, product_settings['10%_power_time']))

        # 阶段14: 0%功率(13V)
        sequence.append(("0%功率测试5", self.normal_voltage, product_settings['0%_power_time_5']))

        return sequence

    def write_test_log(self, stage_name, set_voltage, duration, actual_voltage, actual_current):
        """
        写入测试日志

        参数:
            stage_name: 阶段名称
            set_voltage: 设置电压
            duration: 持续时间
            actual_voltage: 实际电压
            actual_current: 实际电流
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp},{stage_name},{set_voltage:.1f}V,{duration}s,{actual_voltage:.2f}V,{actual_current:.2f}A\n"

            with open(self.test_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)

        except Exception as e:
            print(f"写入测试日志失败: {e}")

    def write_actual_values(self, timestamp, voltage, current):
        """
        将实际电压和电流写入文件

        参数:
            timestamp: 时间戳
            voltage: 实际电压
            current: 实际电流
        """
        try:
            # 写入实际电压
            with open(self.actual_voltage_file, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp},{voltage:.2f}\n")

            # 写入实际电流
            with open(self.actual_current_file, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp},{current:.2f}\n")

        except Exception as e:
            print(f"写入实际值文件失败: {e}")

    def clear_data_files(self):
        """清空数据文件"""
        try:
            with open(self.actual_voltage_file, 'w', encoding='utf-8') as f:
                f.write("")
            with open(self.actual_current_file, 'w', encoding='utf-8') as f:
                f.write("")
            with open(self.test_log_file, 'w', encoding='utf-8') as f:
                f.write("")
            print("数据文件已清空")
        except Exception as e:
            print(f"清空数据文件失败: {e}")

    def run_test_sequence(self, product_model="A061"):
        """
        运行测试序列

        参数:
            product_model: 产品型号
        """
        # 读取产品设置
        csv_file_path = Path(r'd:\data\已选产品时间设置.csv')
        if not csv_file_path.exists():
            print(f"CSV文件不存在: {csv_file_path}")
            return

        product_settings = self.read_product_settings(csv_file_path, product_model)
        if not product_settings:
            print("无法读取产品设置，程序退出")
            return

        print(f"读取到产品 {product_model} 的设置")

        # 生成测试序列
        test_sequence = self.generate_test_sequence(product_settings)
        print(f"生成 {len(test_sequence)} 个测试阶段")

        # 清空数据文件
        self.clear_data_files()

        # 开机
        if not self.power_on():
            print("无法开机，程序退出")
            return

        # 开始测试
        start_time = time.time()
        total_duration = sum(stage[2] for stage in test_sequence)
        print(f"测试总时长: {total_duration} 秒 ({total_duration / 60:.1f} 分钟)")

        # 记录阶段信息
        for i, (stage_name, set_voltage, duration) in enumerate(test_sequence, 1):
            print(f"\n阶段 {i}/{len(test_sequence)}: {stage_name}")
            print(f"设置电压: {set_voltage}V, 持续时间: {duration}秒")

            # 设置电压
            if not self.set_voltage(set_voltage):
                print(f"设置电压失败，跳过阶段 {i}")
                continue

            # 等待电压稳定
            time.sleep(0.5)

            # 计算阶段开始时间
            stage_start_time = time.time()
            stage_elapsed = 0

            # 在阶段持续时间内定期读取电压和电流
            while stage_elapsed < duration:
                # 读取实际值
                actual_voltage, actual_current, status = self.read_power_status()

                if actual_voltage is not None:
                    current_time = time.time() - start_time

                    # 写入实际值文件
                    self.write_actual_values(current_time, actual_voltage, actual_current)

                    # 显示当前状态
                    print(f"  时间: {current_time:.1f}s, 电压: {actual_voltage:.2f}V, 电流: {actual_current:.2f}A")

                # 等待1秒再读取
                time.sleep(1)
                stage_elapsed = time.time() - stage_start_time

            # 阶段结束，写入日志
            if actual_voltage is not None:
                self.write_test_log(stage_name, set_voltage, duration, actual_voltage, actual_current)

        # 测试完成，待机
        print("\n测试完成")
        self.power_off()


def main():
    """主函数"""
    # 创建程控电源对象
    # 注意：根据实际连接调整串口号（如COM3、COM4等）
    pps = ProgrammablePowerSupply(port='COM3', station_address=1)

    # 连接电源
    if not pps.connect():
        print("无法连接电源，程序退出")
        return

    try:
        # 运行测试序列
        pps.run_test_sequence(product_model="A061")

    except KeyboardInterrupt:
        print("\n用户中断程序")
        # 中断时待机
        pps.power_off()
    except Exception as e:
        print(f"程序运行错误: {e}")
    finally:
        # 断开连接
        pps.disconnect()


if __name__ == "__main__":
    main()