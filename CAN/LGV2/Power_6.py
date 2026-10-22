import serial
import time
import struct
import sys
from logger import logger
from power_communication_manager import power_comm_manager
from serial_manager import serial_manager


class ProgrammablePowerSupply:
    def __init__(self, port='COM4', baudrate=9600, station_address=6, station_idx=0):
        """
        初始化程控电源连接
        
        参数:
            port: 串口号
            baudrate: 波特率
            station_address: 站地址
            station_idx: 工位索引（1-10），用于通信间隔控制
        """
        self.station_address = station_address
        self.station_idx = station_idx
        self.port = port

        # 使用串口管理器获取串口实例
        self.ser = serial_manager.get_serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1  # 读取超时时间
        )

        # 电压电流转换系数（根据额定范围）
        # 假设额定电压100V以下，额定电流1000A以下-10A以上
        self.voltage_factor = 100.0  # 电压值需要除以100
        self.current_factor = 10.0  # 电流值需要除以10

    def calculate_crc16(self, data):
        """
        计算Modbus CRC16校验码
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
        return crc

    def build_command(self, function_code, start_address, data=None, write_data=None):
        """
        构建Modbus RTU命令
        """
        # 构建基础帧：站地址 + 功能码
        frame = bytearray([self.station_address, function_code])

        # 添加起始地址（大端序）
        frame.extend(struct.pack('>H', start_address))

        # 根据功能码添加不同内容
        if function_code == 0x04:  # 读输入寄存器
            # 数据长度（要读取的寄存器数量）
            frame.extend(struct.pack('>H', data))
        elif function_code == 0x06:  # 写单个寄存器
            # 写入的数据值
            frame.extend(struct.pack('>H', write_data))
        elif function_code == 0x10:  # 写多个寄存器
            # 寄存器数量
            frame.extend(struct.pack('>H', data['reg_count']))
            # 字节数
            frame.append(data['byte_count'])
            # 数据
            for value in data['values']:
                frame.extend(struct.pack('>H', value))

        # 计算CRC16
        crc = self.calculate_crc16(frame)
        frame.extend(struct.pack('<H', crc))  # CRC小端序

        return bytes(frame)

    def parse_response(self, response, function_code):
        """
        解析设备响应
        """
        if not response or len(response) < 5:
            return None

        # 验证CRC
        crc_received = struct.unpack('<H', response[-2:])[0]
        crc_calculated = self.calculate_crc16(response[:-2])

        if crc_received != crc_calculated:
            print(f"CRC校验失败! Received: {response.hex().upper()} | Calc: {crc_calculated:04X} | Recv: {crc_received:04X}")
            return None

        if function_code == 0x04:  # 读取响应
            # 响应格式：站地址 功能码 字节数 数据... CRC
            byte_count = response[2]
            data_bytes = response[3:3 + byte_count]

            # 每2个字节是一个寄存器值
            registers = []
            for i in range(0, byte_count, 2):
                if i + 1 < byte_count:
                    value = struct.unpack('>H', data_bytes[i:i + 2])[0]
                    registers.append(value)

            return registers

        elif function_code in [0x06, 0x10]:  # 写入响应
            # 回应应该是原命令的echo
            return True

        return None

    def set_voltage(self, voltage):
        """
        设置电压
        假设额定电压100V以下，设置值 = 电压 * 100
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            set_value = int(voltage * 100)  # 15V -> 1500
            command = self.build_command(0x06, 0x0001, write_data=set_value)

            self.ser.write(command)
            response = self.ser.read(8)  # 写入响应固定8字节

            return self.parse_response(response, 0x06)

    def set_current(self, current):
        """
        设置电流
        假设额定电流1000A以下-10A以上，设置值 = 电流 * 10
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            set_value = int(current * 10)  # 200A -> 2000
            command = self.build_command(0x06, 0x0002, write_data=set_value)

            self.ser.write(command)
            response = self.ser.read(8)  # 写入响应固定8字节

            return self.parse_response(response, 0x06)

    def set_overvoltage(self, ovp_voltage):
        """
        设置过压保护
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            set_value = int(ovp_voltage * 100)  # 假设额定电压100V以下
            command = self.build_command(0x06, 0x0003, write_data=set_value)

            self.ser.write(command)
            response = self.ser.read(8)

            return self.parse_response(response, 0x06)

    def power_on(self):
        """
        开机
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            command = self.build_command(0x06, 0x0000, write_data=0x00FF)

            self.ser.write(command)
            response = self.ser.read(8)

            return self.parse_response(response, 0x06)

    def power_off(self):
        """
        待机
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            command = self.build_command(0x06, 0x0000, write_data=0x0000)

            self.ser.write(command)
            response = self.ser.read(8)

            return self.parse_response(response, 0x06)

    def read_status(self):
        """
        读取电源状态（包括电压、电流）
        读取3个寄存器：状态、输出电压、输出电流
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            command = self.build_command(0x04, 0x0000, 3)

            self.ser.write(command)
            response = self.ser.read(11)  # 读取响应: 地址(1)+功能(1)+字节数(1)+数据(6)+CRC(2)=11字节

            registers = self.parse_response(response, 0x04)

            if registers and len(registers) >= 3:
                status = registers[0]
                voltage_raw = registers[1]
                current_raw = registers[2]

                # 解析状态位（根据协议第2页）
                status_bits = {
                    'working': bool(status & 0x01),  # BIT0: 1工作，0待机
                    'program_control': bool(status & 0x02),  # BIT1: 1程控，0近控
                    'constant_current': bool(status & 0x04),  # BIT2: 1恒流，0恒压
                    'overvoltage_fault': bool(status & 0x08),  # BIT3: 过压故障
                    'short_circuit_fault': bool(status & 0x10),  # BIT4: 短路故障
                    'reference_fault': bool(status & 0x20)  # BIT5: 基准源故障
                }

                # 转换实际值（根据假设的额定范围）
                actual_voltage = voltage_raw / self.voltage_factor
                actual_current = current_raw / self.current_factor

                return {
                    'status': status_bits,
                    'voltage_raw': voltage_raw,
                    'current_raw': current_raw,
                    'voltage': actual_voltage,
                    'current': actual_current
                }

            return None

    def set_multiple_parameters(self, voltage, current, ovp_voltage, power_on=True):
        """
        同时设置多个参数（功能码0x10）
        """
        # 使用通信管理器确保原子操作
        with power_comm_manager:
            power_comm_manager.acquire_communication_slot(self.station_idx)
            
            # 计算设置值
            voltage_set = int(voltage * 100)  # 15V -> 1500
            current_set = int(current * 10)  # 200A -> 2000
            ovp_set = int(ovp_voltage * 100)  # 假设设置过压16V -> 1600
            power_set = 0x00FF if power_on else 0x0000

            data = {
                'reg_count': 4,  # 4个寄存器：工作状态、电压、电流、过压
                'byte_count': 8,  # 4个寄存器 * 2字节 = 8字节
                'values': [power_set, voltage_set, current_set, ovp_set]
            }

            command = self.build_command(0x10, 0x0000, data)

            self.ser.write(command)
            response = self.ser.read(8)  # 0x10响应固定8字节

            return self.parse_response(response, 0x10)

    def close(self):
        """关闭串口连接"""
        try:
            serial_manager.release_serial(self.port)
            logger.info(f"电源 {self.station_address} 串口 {self.port} 已释放")
        except Exception as e:
            logger.error(f"释放串口失败: {e}")


def main():
    """主程序"""
    print("程控电源控制程序")
    print("=" * 40)

    # 创建电源对象
    try:
        psu = ProgrammablePowerSupply(port='COM4', station_address=6)
        print(f"已连接程控电源 (COM4, 站地址: 6)")
    except Exception as e:
        print(f"连接失败: {e}")
        sys.exit(1)

    try:
        # 方法1：使用单次写指令分别设置参数
        print("\n1. 设置电源参数...")

        # 设置电压19V
        if psu.set_voltage(15.8):
            print("  ✓ 电压设置为19V")
        else:
            print("  ✗ 电压设置失败")

        # 设置电流200A
        if psu.set_current(200):
            print("  ✓ 电流设置为200A")
        else:
            print("  ✗ 电流设置失败")



        # 开机
        if psu.power_on():
            print("  ✓ 电源已开机")
        else:
            print("  ✗ 开机失败")

        print("\n2. 开始读取实际电压电流...")
        print("=" * 40)
        print("时间戳            | 电压(V) | 电流(A) | 状态")
        print("-" * 40)

        # 循环读取状态
        read_count = 0
        while True:
            status = psu.read_status()

            if status:
                # 获取当前时间
                timestamp = time.strftime("%H:%M:%S")

                # 提取状态信息
                voltage = status['voltage']
                current = status['current']
                status_bits = status['status']

                # 构建状态字符串
                status_str = "工作" if status_bits['working'] else "待机"
                if status_bits['constant_current']:
                    status_str += ",恒流"
                else:
                    status_str += ",恒压"

                if status_bits['overvoltage_fault']:
                    status_str += ",过压故障"
                if status_bits['short_circuit_fault']:
                    status_str += ",短路故障"

                # 打印结果
                print(f"{timestamp} | {voltage:7.2f} | {current:7.2f} | {status_str}")

                read_count += 1
            else:
                print("读取失败，请检查连接")

            # 等待1秒
            time.sleep(1)

            # 可选：设置读取次数限制（例如只读取10次）
            # if read_count >= 10:
            #     print("\n读取完成，共读取10次")
            #     break

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
    finally:
        # 关闭连接
        psu.close()
        print("串口连接已关闭")


if __name__ == "__main__":
    main()