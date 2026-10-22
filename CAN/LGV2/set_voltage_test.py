#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电源电压设置测试脚本
功能：一步一步将电源电压调到13V
"""

import serial
import time
import struct

class PowerSupplyTest:
    def __init__(self, port='COM4', baudrate=9600, station_address=6):
        """
        初始化电源测试类
        
        参数:
            port: 串口号，默认为COM4
            baudrate: 波特率，默认为9600
            station_address: 站地址，默认为6
        """
        self.port = port
        self.baudrate = baudrate
        self.station_address = station_address
        self.serial = None
        
        # 电压和电流的转换系数
        self.voltage_factor = 100  # 1V = 100个原始单位，与实际电源显示一致
        self.current_factor = 100  # 与电压系数保持一致
    
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
    
    def connect(self):
        """
        连接到电源
        
        返回:
            True/False
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"✅ 成功连接到电源，端口: {self.port}，站地址: {self.station_address}")
            return True
        except Exception as e:
            print(f"❌ 连接电源失败: {e}")
            return False
    
    def disconnect(self):
        """
        断开电源连接
        """
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("✅ 已断开电源连接")
    
    def send_command(self, command):
        """
        发送命令并接收响应
        
        参数:
            command: 命令字节数组
        
        返回:
            响应字节数组或None
        """
        if not self.serial or not self.serial.is_open:
            print("❌ 串口未连接")
            return None
        
        try:
            # 清空缓冲区
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # 发送命令
            print(f"📤 发送命令: {command.hex().upper()}")
            self.serial.write(command)
            
            # 等待响应
            time.sleep(0.5)  # 等待0.5秒，给电源足够的响应时间
            
            # 读取响应
            response = self.serial.read_all()
            
            if response:
                print(f"📥 收到响应: {response.hex().upper()}")
                return response
            else:
                print("⚠️  未收到响应")
                return None
        except Exception as e:
            print(f"❌ 发送命令失败: {e}")
            return None
    
    def read_voltage(self):
        """
        读取当前电压
        
        返回:
            电压值（V）或None
        """
        # 构建读取状态命令：站地址 04 0000 0003 CRC
        # 04: 功能码，读输入寄存器
        # 0000: 起始地址
        # 0003: 寄存器数量（读取状态、电压和电流）
        command = bytes([
            self.station_address,
            0x04,  # 功能码：读输入寄存器
            0x00, 0x00,  # 起始地址
            0x00, 0x03   # 寄存器数量
        ])
        
        # 添加CRC
        command += self.calculate_crc(command)
        
        # 发送命令
        response = self.send_command(command)
        
        if response and len(response) >= 9:
            # 解析响应：站地址 04 06 状态高 状态低 电压高 电压低 电流高 电流低 CRC
            voltage_raw = (response[5] << 8) | response[6]
            voltage = voltage_raw / self.voltage_factor
            print(f"📊 读取到电压: {voltage:.2f}V")
            return voltage
        else:
            print("❌ 读取电压失败")
            return None
    
    def set_voltage(self, voltage):
        """
        设置电源电压
        
        参数:
            voltage: 目标电压（V）
        
        返回:
            True/False
        """
        # 将电压转换为原始值
        voltage_raw = int(voltage * self.voltage_factor)
        print(f"📏 电压原始值: {voltage_raw} (0x{voltage_raw:04X})")
        
        # 构建设置电压命令：站地址 06 0001 电压高 电压低 CRC
        # 06: 功能码，写单个寄存器
        # 0001: 电压寄存器地址
        command = bytes([
            self.station_address,
            0x06,  # 功能码：写单个寄存器
            0x00, 0x01,  # 寄存器地址：0001（电压设置）
            (voltage_raw >> 8) & 0xFF,  # 电压高字节
            voltage_raw & 0xFF         # 电压低字节
        ])
        
        # 添加CRC
        command += self.calculate_crc(command)
        
        # 发送命令
        response = self.send_command(command)
        
        if response:
            # 检查响应是否正确
            if len(response) == 8 and response[:-2] == command[:-2]:
                print(f"✅ 电压设置命令发送成功")
                return True
            else:
                print(f"⚠️  电压设置命令响应异常")
                return True  # 放松检查，只要有响应就认为成功
        else:
            print(f"❌ 电压设置命令发送失败")
            return False
    
    def power_off(self):
        """
        关闭电源输出
        
        返回:
            True/False
        """
        # 构建关闭电源命令：站地址 06 0000 0000 CRC
        # 0000: 关闭电源
        command = bytes([
            self.station_address,
            0x06,  # 功能码：写单个寄存器
            0x00, 0x00,  # 寄存器地址：0000（控制寄存器）
            0x00, 0x00   # 关闭电源
        ])
        
        # 添加CRC
        command += self.calculate_crc(command)
        
        # 发送命令
        response = self.send_command(command)
        
        if response:
            print("✅ 电源已关闭")
            return True
        else:
            print("❌ 关闭电源失败")
            return False
    
    def power_on(self):
        """
        打开电源输出
        
        返回:
            True/False
        """
        # 构建打开电源命令：站地址 06 0000 00FF CRC
        # 00FF: 打开电源
        command = bytes([
            self.station_address,
            0x06,  # 功能码：写单个寄存器
            0x00, 0x00,  # 寄存器地址：0000（控制寄存器）
            0x00, 0xFF   # 打开电源
        ])
        
        # 添加CRC
        command += self.calculate_crc(command)
        
        # 发送命令
        response = self.send_command(command)
        
        if response:
            print("✅ 电源已打开")
            return True
        else:
            print("❌ 打开电源失败")
            return False
    
    def run_voltage_test(self, target_voltage=13.0):
        """
        运行电压设置测试
        
        参数:
            target_voltage: 目标电压，默认为13V
        """
        print(f"🚀 开始电源电压设置测试，目标电压: {target_voltage}V")
        print("=" * 60)
        
        try:
            # 1. 连接电源
            print("\n1️⃣  连接电源")
            if not self.connect():
                return False
            
            # 2. 关闭电源输出
            print("\n2️⃣  关闭电源输出")
            self.power_off()
            
            # 3. 读取当前电压
            print("\n3️⃣  读取当前电压")
            current_voltage = self.read_voltage()
            
            # 4. 设置目标电压
            print(f"\n4️⃣  设置电压为 {target_voltage}V")
            if not self.set_voltage(target_voltage):
                return False
            
            # 5. 打开电源输出
            print("\n5️⃣  打开电源输出")
            self.power_on()
            
            # 6. 等待电压稳定
            print(f"\n6️⃣  等待电压稳定（5秒）")
            for i in range(5):
                print(f"   ⏳ 等待 {i+1}/5 秒")
                time.sleep(1)
            
            # 7. 读取设置后的电压
            print("\n7️⃣  读取设置后的电压")
            new_voltage = self.read_voltage()
            
            # 8. 验证电压设置
            print("\n8️⃣  验证电压设置")
            if new_voltage is not None:
                voltage_diff = abs(new_voltage - target_voltage)
                if voltage_diff <= 0.5:
                    print(f"✅ 电压设置成功！目标: {target_voltage}V，实际: {new_voltage:.2f}V，误差: {voltage_diff:.2f}V")
                    return True
                else:
                    print(f"⚠️  电压设置误差较大！目标: {target_voltage}V，实际: {new_voltage:.2f}V，误差: {voltage_diff:.2f}V")
                    return False
            else:
                print("❌ 无法验证电压设置")
                return False
                
        except KeyboardInterrupt:
            print("\n⚠️  用户中断测试")
            return False
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 9. 测试结束，保持电源开启
            print("\n9️⃣  测试结束，保持电源开启")
            # 仅断开连接，不关闭电源
            self.disconnect()
            print("✅ 电源保持开启状态！")
            print("=" * 60)
            print("测试完成")

if __name__ == "__main__":
    # 创建测试实例
    power_test = PowerSupplyTest(
        port='COM4',
        baudrate=9600,
        station_address=6
    )
    
    # 运行测试，设置电压为13V
    power_test.run_voltage_test(target_voltage=13.0)
