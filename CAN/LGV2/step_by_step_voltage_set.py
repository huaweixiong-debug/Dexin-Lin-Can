#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一步一步将电源电压调到13V的脚本
详细记录每一步操作和结果
"""

import serial
import time
import struct

class StepByStepVoltageSetter:
    def __init__(self, port='COM4', baudrate=9600, station_address=6):
        """
        初始化电压设置器
        
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
        self.voltage_factor = 100  # 1V = 100个原始单位，根据实际电源显示调整
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
        print("=" * 60)
        print(f"1. 尝试连接到电源: {self.port}")
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"✅ 成功连接到电源，端口: {self.port}")
            print(f"   站地址: {self.station_address}")
            print(f"   波特率: {self.baudrate}")
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
    
    def send_command(self, command, description=""):
        """
        发送命令并接收响应
        
        参数:
            command: 命令字节数组
            description: 命令描述
        
        返回:
            响应字节数组或None
        """
        if description:
            print(f"\n   📤 {description}:")
        
        if not self.serial or not self.serial.is_open:
            print("   ❌ 串口未连接")
            return None
        
        try:
            # 清空缓冲区
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # 发送命令
            print(f"   命令: {command.hex().upper()}")
            self.serial.write(command)
            
            # 等待响应
            time.sleep(0.5)  # 增加等待时间
            
            # 读取响应
            response = self.serial.read_all()
            
            if response:
                print(f"   📥 响应: {response.hex().upper()}")
                return response
            else:
                print("   ⚠️  未收到响应")
                return None
        except Exception as e:
            print(f"   ❌ 发送命令失败: {e}")
            return None
    
    def read_power_status(self):
        """
        读取电源状态
        
        返回:
            (电压, 电流, 状态) 或 (None, None, None)
        """
        print("\n2. 读取电源状态")
        
        # 使用功能码0x04读取输入寄存器
        command = bytes([
            self.station_address,
            0x04,  # 功能码：读输入寄存器
            0x00, 0x00,  # 起始地址
            0x00, 0x03   # 寄存器数量：3
        ])
        
        command += self.calculate_crc(command)
        response = self.send_command(command, "读取状态命令")
        
        if response and len(response) >= 9:
            try:
                # 解析响应
                status_raw = (response[3] << 8) | response[4]
                voltage_raw = (response[5] << 8) | response[6]
                current_raw = (response[7] << 8) | response[8]
                
                voltage = voltage_raw / self.voltage_factor
                current = current_raw / self.current_factor
                
                # 解析状态位
                status = {
                    'working': bool(status_raw & 0x0001),  # BIT0: 工作/待机
                    'remote_control': bool(status_raw & 0x0002),  # BIT1: 程控/近控
                    'constant_current': bool(status_raw & 0x0004),  # BIT2: 恒流/恒压
                    'overvoltage_fault': bool(status_raw & 0x0008),  # BIT3: 过压故障
                    'short_circuit_fault': bool(status_raw & 0x0010),  # BIT4: 短路故障
                    'reference_fault': bool(status_raw & 0x0020)  # BIT5: 基准源故障
                }
                
                print(f"   ✅ 状态读取成功")
                print(f"   📊 电压: {voltage:.2f}V")
                print(f"   📊 电流: {current:.2f}A")
                print(f"   📋 状态:")
                print(f"      - 工作模式: {'工作' if status['working'] else '待机'}")
                print(f"      - 控制模式: {'远程' if status['remote_control'] else '本地'}")
                print(f"      - 输出模式: {'恒流' if status['constant_current'] else '恒压'}")
                print(f"      - 过压故障: {'是' if status['overvoltage_fault'] else '否'}")
                print(f"      - 短路故障: {'是' if status['short_circuit_fault'] else '否'}")
                print(f"      - 基准源故障: {'是' if status['reference_fault'] else '否'}")
                
                return voltage, current, status
            except Exception as e:
                print(f"   ❌ 解析状态失败: {e}")
                return None, None, None
        else:
            print("   ❌ 状态读取失败")
            return None, None, None
    
    def power_off(self):
        """
        关闭电源输出
        
        返回:
            True/False
        """
        print("\n3. 关闭电源输出")
        
        # 构建设置命令
        command = bytes([
            self.station_address,
            0x06,  # 功能码：写单个寄存器
            0x00, 0x00,  # 寄存器地址：0000（控制）
            0x00, 0x00   # 关闭电源
        ])
        
        command += self.calculate_crc(command)
        response = self.send_command(command, "关闭电源命令")
        
        if response:
            print("   ✅ 电源已关闭")
            return True
        else:
            print("   ❌ 关闭电源失败")
            return False
    
    def power_on(self):
        """
        打开电源输出
        
        返回:
            True/False
        """
        print("\n5. 打开电源输出")
        
        # 构建设置命令
        command = bytes([
            self.station_address,
            0x06,  # 功能码：写单个寄存器
            0x00, 0x00,  # 寄存器地址：0000（控制）
            0x00, 0xFF   # 打开电源
        ])
        
        command += self.calculate_crc(command)
        response = self.send_command(command, "打开电源命令")
        
        if response:
            print("   ✅ 电源已打开")
            return True
        else:
            print("   ❌ 打开电源失败")
            return False
    
    def set_voltage(self, voltage):
        """
        设置电源电压
        
        参数:
            voltage: 目标电压（V）
        
        返回:
            True/False
        """
        print(f"\n4. 设置电压为 {voltage}V")
        
        # 将电压转换为原始值
        voltage_raw = int(voltage * self.voltage_factor)
        print(f"   📏 电压原始值: {voltage_raw} (0x{voltage_raw:04X})")
        
        # 构建设置命令
        command = bytes([
            self.station_address,
            0x06,  # 功能码：写单个寄存器
            0x00, 0x01,  # 寄存器地址：0001（电压设置）
            (voltage_raw >> 8) & 0xFF,  # 电压高字节
            voltage_raw & 0xFF         # 电压低字节
        ])
        
        command += self.calculate_crc(command)
        response = self.send_command(command, "设置电压命令")
        
        if response:
            print("   ✅ 电压设置命令发送成功")
            return True
        else:
            print("   ❌ 电压设置命令发送失败")
            return False
    
    def verify_voltage(self, target_voltage, tolerance=0.5):
        """
        验证电压是否设置成功
        
        参数:
            target_voltage: 目标电压（V）
            tolerance: 允许的误差范围（V）
        
        返回:
            True/False
        """
        print(f"\n6. 验证电压设置")
        print(f"   目标电压: {target_voltage}V")
        print(f"   允许误差: ±{tolerance}V")
        
        # 读取多次以确保准确性
        success = False
        for i in range(3):
            print(f"   🔄 验证尝试 {i+1}/3")
            voltage, current, status = self.read_power_status()
            
            if voltage is not None:
                voltage_diff = abs(voltage - target_voltage)
                print(f"   📊 测量电压: {voltage:.2f}V")
                print(f"   📊 误差: {voltage_diff:.2f}V")
                
                if voltage_diff <= tolerance:
                    print(f"   ✅ 电压设置成功！")
                    success = True
                    break
                else:
                    print(f"   ⚠️  电压误差超出范围，等待重试...")
                    time.sleep(1)
            else:
                print(f"   ⚠️  无法读取电压，等待重试...")
                time.sleep(1)
        
        if not success:
            print(f"   ❌ 电压设置失败！")
        
        return success
    
    def run_step_by_step(self, target_voltage=13.0):
        """
        一步一步执行电压设置流程
        
        参数:
            target_voltage: 目标电压，默认为13V
        """
        print("🚀 开始一步一步电压设置流程")
        print(f"📌 目标电压: {target_voltage}V")
        print("=" * 60)
        
        try:
            # 1. 连接电源
            if not self.connect():
                return False
            
            # 2. 读取初始状态
            initial_voltage, initial_current, initial_status = self.read_power_status()
            
            # 3. 关闭电源输出
            if not self.power_off():
                return False
            
            # 4. 等待1秒
            time.sleep(1)
            
            # 5. 设置电压
            if not self.set_voltage(target_voltage):
                return False
            
            # 6. 等待1秒
            time.sleep(1)
            
            # 7. 打开电源输出
            if not self.power_on():
                return False
            
            # 8. 等待电压稳定
            print(f"\n7. 等待电压稳定（5秒）")
            for i in range(5):
                print(f"   ⏳ 等待 {i+1}/5 秒")
                time.sleep(1)
            
            # 9. 验证电压
            if not self.verify_voltage(target_voltage):
                return False
            
            # 10. 最终状态检查
            print("\n8. 最终状态检查")
            final_voltage, final_current, final_status = self.read_power_status()
            
            print("\n" + "=" * 60)
            print("🎉 电压设置流程完成！")
            print(f"📋 初始电压: {initial_voltage:.2f}V")
            print(f"📋 最终电压: {final_voltage:.2f}V")
            print(f"📋 目标电压: {target_voltage}V")
            print(f"📋 误差: {abs(final_voltage - target_voltage):.2f}V")
            print("=" * 60)
            
            return True
            
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断程序")
            return False
        except Exception as e:
            print(f"\n❌ 程序错误: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 11. 断开连接
            print("\n9. 断开电源连接")
            self.disconnect()
            print("=" * 60)

if __name__ == "__main__":
    # 创建电压设置器实例
    voltage_setter = StepByStepVoltageSetter(
        port='COM4',
        baudrate=9600,
        station_address=6
    )
    
    # 运行一步一步电压设置流程
    success = voltage_setter.run_step_by_step(target_voltage=13.0)
    
    if success:
        print("✅ 电压设置成功！")
    else:
        print("❌ 电压设置失败！")
