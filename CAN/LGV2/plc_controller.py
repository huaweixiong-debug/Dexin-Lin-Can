import snap7
from snap7.util import get_bool, set_bool
import threading
import time
from logger import logger

class PLCController:
    def __init__(self):
        self.plc1_ip = '192.168.10.221'
        self.plc2_ip = '192.168.10.222'
        self.rack = 0
        self.slot = 1 
        
        # Determine PLC Memory Area
        try:
            self.plc_mem_area = snap7.Area.MK
        except AttributeError:
            try:
                self.plc_mem_area = snap7.types.Areas.MK
            except AttributeError:
                self.plc_mem_area = 0x83
        
        self.client1 = snap7.Client()
        self.client2 = snap7.Client()
        
        self.connected1 = False
        self.connected2 = False
        
        self.last_read_time = {1: 0, 2: 0} # PLC1, PLC2
        
        self.lock = threading.RLock()
        
        # Callbacks
        self.on_start_signal = None # func(station_idx)
        self.on_stop_signal = None  # func(station_idx)
        self.on_emergency_stop = None  # func(station_idx)
        self.on_reset = None  # func(station_idx)
        
        # State tracking for edge detection
        # {station_idx: {'start': bool, 'stop': bool, 'emergency_stop': bool, 'reset': bool}}
        self.last_states = {}
        for i in range(1, 11):
            self.last_states[i] = {
                'start': False, 
                'stop': False,
                'emergency_stop': False,
                'reset': False
            }
        
        # PLC状态日志回调
        self.log_callback = None

    def connect(self):
        logger.info(f"Attempting to connect to PLC1 ({self.plc1_ip})...")
        with self.lock:
            try:
                # 确保先断开现有连接
                try:
                    if self.client1.get_connected():
                        logger.info(f"Disconnecting from PLC1 ({self.plc1_ip}) before reconnecting...")
                        self.client1.disconnect()
                        time.sleep(0.1)  # 等待100ms确保连接完全释放
                except Exception as disconnect_e:
                    logger.debug(f"Error checking PLC1 connection status: {disconnect_e}")
                
                self.client1.connect(self.plc1_ip, 0, 1)
                self.connected1 = True
                logger.info(f"Connected to PLC 1 ({self.plc1_ip})")
                if self.log_callback:
                    self.log_callback(f"PLC1连接成功: {self.plc1_ip}")
            except Exception as e:
                logger.error(f"Failed to connect to PLC 1: {e}")
                self.connected1 = False
                if self.log_callback:
                    self.log_callback(f"PLC1连接失败: {str(e)}")

            logger.info(f"Attempting to connect to PLC2 ({self.plc2_ip})...")
            try:
                # 确保先断开现有连接
                try:
                    if self.client2.get_connected():
                        logger.info(f"Disconnecting from PLC2 ({self.plc2_ip}) before reconnecting...")
                        self.client2.disconnect()
                        time.sleep(0.1)  # 等待100ms确保连接完全释放
                except Exception as disconnect_e:
                    logger.debug(f"Error checking PLC2 connection status: {disconnect_e}")
                
                self.client2.connect(self.plc2_ip, 0, 1)
                self.connected2 = True
                logger.info(f"Connected to PLC 2 ({self.plc2_ip})")
                if self.log_callback:
                    self.log_callback(f"PLC2连接成功: {self.plc2_ip}")
            except Exception as e:
                logger.error(f"Failed to connect to PLC 2: {e}")
                self.connected2 = False
                if self.log_callback:
                    self.log_callback(f"PLC2连接失败: {str(e)}")

    def disconnect(self):
        with self.lock:
            if self.connected1:
                logger.info(f"Disconnecting from PLC 1 ({self.plc1_ip})...")
                try:
                    self.client1.disconnect()
                    self.connected1 = False
                    logger.info(f"Disconnected from PLC 1 ({self.plc1_ip})")
                    if self.log_callback:
                        self.log_callback(f"PLC1断开连接")
                except Exception as e:
                    logger.error(f"Error disconnecting from PLC 1: {e}")
                    if self.log_callback:
                        self.log_callback(f"PLC1断开连接错误: {str(e)}")
            else:
                logger.debug(f"PLC1 ({self.plc1_ip}) already disconnected")
                
            if self.connected2:
                logger.info(f"Disconnecting from PLC 2 ({self.plc2_ip})...")
                try:
                    self.client2.disconnect()
                    self.connected2 = False
                    logger.info(f"Disconnected from PLC 2 ({self.plc2_ip})")
                    if self.log_callback:
                        self.log_callback(f"PLC2断开连接")
                except Exception as e:
                    logger.error(f"Error disconnecting from PLC 2: {e}")
                    if self.log_callback:
                        self.log_callback(f"PLC2断开连接错误: {str(e)}")
            else:
                logger.debug(f"PLC2 ({self.plc2_ip}) already disconnected")

    def update_plc_ips(self, plc1_ip, plc2_ip):
        """更新PLC IP地址"""
        logger.info(f"Updating PLC IP addresses: PLC1={plc1_ip}, PLC2={plc2_ip}")
        with self.lock:
            # 断开现有连接
            if self.connected1:
                try:
                    self.client1.disconnect()
                    self.connected1 = False
                except Exception as e:
                    logger.error(f"Error disconnecting from PLC1: {e}")
            
            if self.connected2:
                try:
                    self.client2.disconnect()
                    self.connected2 = False
                except Exception as e:
                    logger.error(f"Error disconnecting from PLC2: {e}")
            
            # 更新IP地址
            self.plc1_ip = plc1_ip
            self.plc2_ip = plc2_ip
            
            # 重新连接
            self.connect()

    def check_connection(self):
        # 检查PLC1连接状态
        with self.lock:
            try:
                try:
                    is_connected1 = self.client1.get_connected()
                except Exception as get_conn_e:
                    logger.debug(f"Error checking PLC1 connection status: {get_conn_e}")
                    is_connected1 = False
                
                if not is_connected1:
                    logger.warning(f"PLC1 ({self.plc1_ip}) disconnected, attempting to reconnect...")
                    try:
                        self.client1.connect(self.plc1_ip, 0, 1)
                        self.connected1 = True
                        logger.info(f"Reconnected to PLC 1 ({self.plc1_ip})")
                        if self.log_callback:
                            self.log_callback(f"PLC1重新连接成功")
                    except Exception as e:
                        logger.error(f"Failed to reconnect to PLC 1: {e}")
                        self.connected1 = False
                        if self.log_callback:
                            self.log_callback(f"PLC1连接失败: {str(e)}")
                else:
                    # 记录连接状态
                    logger.debug(f"PLC1 ({self.plc1_ip}) connection status: Connected")
            except Exception as e:
                logger.error(f"Error checking PLC1 connection: {e}")
                self.connected1 = False
                    
            # 检查PLC2连接状态
            try:
                try:
                    is_connected2 = self.client2.get_connected()
                except Exception as get_conn_e:
                    logger.debug(f"Error checking PLC2 connection status: {get_conn_e}")
                    is_connected2 = False
                
                if not is_connected2:
                    logger.warning(f"PLC2 ({self.plc2_ip}) disconnected, attempting to reconnect...")
                    try:
                        self.client2.connect(self.plc2_ip, 0, 1)
                        self.connected2 = True
                        logger.info(f"Reconnected to PLC 2 ({self.plc2_ip})")
                        if self.log_callback:
                            self.log_callback(f"PLC2重新连接成功")
                    except Exception as e:
                        logger.error(f"Failed to reconnect to PLC 2: {e}")
                        self.connected2 = False
                        if self.log_callback:
                            self.log_callback(f"PLC2连接失败: {str(e)}")
                else:
                    # 记录连接状态
                    logger.debug(f"PLC2 ({self.plc2_ip}) connection status: Connected")
            except Exception as e:
                logger.error(f"Error checking PLC2 connection: {e}")
                self.connected2 = False

    def monitor_loop(self):
        while True:
            try:
                self.check_connection()
                
                if not self.connected1 and not self.connected2:
                    time.sleep(1)
                    continue
                
                # Read PLC inputs
                for station_idx in range(1, 11):
                    # Determine which PLC to read from
                    if station_idx <= 5:
                        client = self.client1 if self.connected1 else None
                        plc_name = "PLC1"
                    else:
                        client = self.client2 if self.connected2 else None
                        plc_name = "PLC2"
                    
                    if not client:
                        continue
                    
                    with self.lock:
                        try:
                                # 根据Excel文件，每个工位对应一个M寄存器组
                            # 工位1: M1.x, 工位2: M2.x, 工位3: M3.x, 工位4: M4.x, 工位5: M5.x
                            # 工位6: M1.x (PLC2), 工位7: M2.x (PLC2), 工位8: M3.x (PLC2), 工位9: M4.x (PLC2), 工位10: M5.x (PLC2)
                            
                            # 计算M寄存器地址
                            # 对于PLC1: 工位1-5 -> M1-M5
                            # 对于PLC2: 工位6-10 -> M1-M5
                            if station_idx <= 5:
                                m_register = station_idx  # M1-M5
                            else:
                                m_register = station_idx - 5  # M1-M5
                            
                            # 读取M寄存器字节
                            m_byte = m_register  # M1对应字节1, M2对应字节2, 以此类推
                            
                            # 记录读取操作
                            logger.debug(f"Reading PLC data from {plc_name} Station {station_idx} (Byte {m_byte})")
                            
                            # 增加读取重试机制
                            max_read_retries = 3
                            read_success = False
                            m_data = None
                            
                            for read_retry in range(max_read_retries):
                                try:
                                    m_data = client.read_area(self.plc_mem_area, 0, m_byte, 1)
                                    read_success = True
                                    break
                                except Exception as read_e:
                                    error_msg = str(read_e)
                                    logger.warning(f"PLC Read Error (attempt {read_retry+1}/{max_read_retries}) ({plc_name} Station {station_idx}): {error_msg}")
                                    
                                    # 根据错误类型调整重试间隔
                                    if "CLI : Job pending" in error_msg:
                                        # 对于CLI : Job pending错误，使用指数退避策略
                                        wait_time = 0.5 * (2 ** read_retry)
                                        # 限制最大等待时间为3秒
                                        wait_time = min(wait_time, 3.0)
                                        logger.info(f"Detected 'CLI : Job pending' error, waiting {wait_time:.1f}s before retry")
                                        time.sleep(wait_time)
                                    elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
                                        wait_time = 0.8
                                        time.sleep(wait_time)
                                    else:
                                        time.sleep(0.3)
                            
                            if not read_success:
                                logger.error(f"Failed to read PLC data after {max_read_retries} attempts ({plc_name} Station {station_idx})")
                                if self.log_callback:
                                    # Throttle error logs to avoid spamming UI
                                    current_time = time.time()
                                    if current_time - self.last_read_time.get(station_idx, 0) > 5.0:
                                        self.log_callback(f"PLC读取错误 ({plc_name} 工位{station_idx}): 读取失败")
                                        self.last_read_time[station_idx] = current_time
                                continue
                            
                            # 记录读取到的原始数据
                            logger.debug(f"PLC raw data for {plc_name} Station {station_idx}: {list(m_data)}")
                            
                            # 解析各个信号位
                            # Mx.0: 扫码OK (上位机发给PLC) - 我们写入
                            # Mx.1: 启动信号 (PLC发给上位机) - 我们读取
                            # Mx.2: 复位信号 (PLC发给上位机) - 我们读取
                            # Mx.3: 急停信号 (PLC发给上位机) - 我们读取
                            # Mx.4: 测试合格 (上位机发给PLC) - 我们写入
                            # Mx.5: 测试不合格 (上位机发给PLC) - 我们写入
                            
                            # 读取启动信号 (Mx.1)
                            start_signal = get_bool(m_data, 0, 1)
                            
                            # 读取复位信号 (Mx.2)
                            reset_signal = get_bool(m_data, 0, 2)
                            
                            # 读取急停信号 (Mx.3)
                            emergency_signal = get_bool(m_data, 0, 3)
                            
                            # 停止信号使用急停信号（根据用户要求，停止同急停）
                            stop_signal = emergency_signal
                            
                            # 记录当前信号状态
                            logger.debug(f"PLC signals for {plc_name} Station {station_idx}: Start={start_signal}, Reset={reset_signal}, Emergency={emergency_signal}, Stop={stop_signal}")
                            
                            # Edge detection for start signal (rising edge)
                            last_start = self.last_states[station_idx]['start']
                            if start_signal and not last_start:
                                logger.info(f"PLC Start signal detected for Station {station_idx}")
                                if self.log_callback:
                                    self.log_callback(f"PLC启动信号: 工位{station_idx}")
                                if self.on_start_signal:
                                    self.on_start_signal(station_idx)
                            
                            # Edge detection for stop signal (rising edge)
                            last_stop = self.last_states[station_idx]['stop']
                            if stop_signal and not last_stop:
                                logger.info(f"PLC Stop signal detected for Station {station_idx}")
                                if self.log_callback:
                                    self.log_callback(f"PLC停止信号: 工位{station_idx}")
                                if self.on_stop_signal:
                                    self.on_stop_signal(station_idx)
                            
                            # Edge detection for emergency stop signal (rising edge)
                            last_emergency = self.last_states[station_idx]['emergency_stop']
                            if emergency_signal and not last_emergency:
                                logger.info(f"PLC Emergency Stop signal detected for Station {station_idx}")
                                if self.log_callback:
                                    self.log_callback(f"PLC急停信号: 工位{station_idx}")
                                if self.on_emergency_stop:
                                    self.on_emergency_stop(station_idx)
                            
                            # Edge detection for reset signal (rising edge)
                            last_reset = self.last_states[station_idx]['reset']
                            if reset_signal and not last_reset:
                                logger.info(f"PLC Reset signal detected for Station {station_idx}")
                                if self.log_callback:
                                    self.log_callback(f"PLC复位信号: 工位{station_idx}")
                                if self.on_reset:
                                    self.on_reset(station_idx)
                            
                            # Update last states
                            self.last_states[station_idx]['start'] = start_signal
                            self.last_states[station_idx]['stop'] = stop_signal
                            self.last_states[station_idx]['emergency_stop'] = emergency_signal
                            self.last_states[station_idx]['reset'] = reset_signal
                            
                        except Exception as e:
                            error_msg = str(e)
                            logger.error(f"PLC Read Error ({plc_name} Station {station_idx}): {error_msg}")
                            if self.log_callback:
                                # Throttle error logs to avoid spamming UI
                                current_time = time.time()
                                if current_time - self.last_read_time.get(station_idx, 0) > 5.0:
                                    self.log_callback(f"PLC读取错误 ({plc_name} 工位{station_idx}): {error_msg}")
                                    self.last_read_time[station_idx] = current_time
                
                time.sleep(0.1)  # 100ms polling interval
                
            except Exception as e:
                logger.error(f"PLC Monitor Loop Error: {e}")
                if self.log_callback:
                     # Throttle loop error logs
                    current_time = time.time()
                    if current_time - self.last_read_time.get('loop', 0) > 5.0:
                        self.log_callback(f"PLC监控循环错误: {str(e)}")
                        self.last_read_time['loop'] = current_time
                time.sleep(1)

    def process_data(self, data, start_station):
        # data is bytearray of size 5
        # i goes from 0 to 4
        # station_idx = start_station + i
        for i in range(5):
            station_idx = start_station + i
            byte_val = data[i]
            
            # Bit 1: Start Signal
            start_signal = get_bool(data, i, 1)
            # Bit 2: Reset, Bit 3: E-Stop. If either is high -> Stop
            reset_signal = get_bool(data, i, 2)
            estop_signal = get_bool(data, i, 3)
            stop_signal = reset_signal or estop_signal
            
            logger.debug(f"Station {station_idx}: Start={start_signal}, Reset={reset_signal}, E-Stop={estop_signal}, Stop={stop_signal}")
            
            # Edge Detection
            # Start: Rising Edge
            if start_signal and not self.last_states[station_idx]['start']:
                if self.on_start_signal:
                    logger.info(f"PLC Start Signal for Station {station_idx}")
                    self.on_start_signal(station_idx)
            
            # Stop: Rising Edge
            if stop_signal and not self.last_states[station_idx]['stop']:
                if self.on_stop_signal:
                    logger.info(f"PLC Stop Signal for Station {station_idx}")
                    self.on_stop_signal(station_idx)
            
            self.last_states[station_idx]['start'] = start_signal
            self.last_states[station_idx]['stop'] = stop_signal

    def write_status(self, station_idx, status_type, value=True):
        """
        Write status to PLC
        station_idx: 1-10
        status_type: 'SCAN_OK', 'PASS', 'FAIL'
        value: True/False
        """
        # Determine which PLC to write to
        if station_idx <= 5:
            client = self.client1 if self.connected1 else None
            plc_name = "PLC1"
            plc_ip = self.plc1_ip
        else:
            client = self.client2 if self.connected2 else None
            plc_name = "PLC2"
            plc_ip = self.plc2_ip
        
        if not client:
            logger.error(f"Cannot write to PLC - not connected for station {station_idx}")
            return
        
        try:
            # 根据Excel文件，每个工位对应一个M寄存器组
            # 工位1: M1.x, 工位2: M2.x, 工位3: M3.x, 工位4: M4.x, 工位5: M5.x
            # 工位6: M1.x (PLC2), 工位7: M2.x (PLC2), 工位8: M3.x (PLC2), 工位9: M4.x (PLC2), 工位10: M5.x (PLC2)
            
            # 计算M寄存器地址
            if station_idx <= 5:
                m_register = station_idx  # M1-M5
            else:
                m_register = station_idx - 5  # M1-M5
            
            # 确定字节偏移
            byte_offset = m_register  # M1对应字节1, M2对应字节2, 以此类推
            
            # 确定位偏移
            if status_type == 'SCAN_OK':
                bit_offset = 0  # Mx.0: 扫码OK
            elif status_type == 'PASS':
                bit_offset = 4  # Mx.4: 测试合格
            elif status_type == 'FAIL':
                bit_offset = 5  # Mx.5: 测试不合格
            else:
                logger.error(f"Unknown status type: {status_type}")
                return
            
            # 记录写入前的数据
            logger.debug(f"Writing {status_type}={value} to {plc_name} Station {station_idx} (Byte {byte_offset}, Bit {bit_offset})")
            
            max_retries = 5  # 增加重试次数到5次
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    with self.lock:
                        # 确保连接
                        if not client.get_connected():
                            client.set_connection_params(plc_ip, self.rack, self.slot)
                            client.connect()
                            time.sleep(0.2)  # 连接后等待0.2秒
                        
                        # Read current byte
                        current_data = client.read_area(self.plc_mem_area, 0, byte_offset, 1)
                        logger.debug(f"Before write - Current data: {list(current_data)}")
                        
                        # Set the bit
                        set_bool(current_data, 0, bit_offset, value)
                        logger.debug(f"After setting bit - New data: {list(current_data)}")
                        
                        # Write back
                        client.write_area(self.plc_mem_area, 0, byte_offset, current_data)
                    
                    logger.info(f"Wrote {status_type}={value} to {plc_name} Station {station_idx} (Byte {byte_offset}, Bit {bit_offset})")
                    success = True
                    
                    # 记录日志到UI
                    if self.log_callback:
                        status_text = "成功" if value else "失败"
                        self.log_callback(f"PLC状态写入: 工位{station_idx} {status_type}={status_text}")
                    
                    # 验证写入结果
                    try:
                        # 增加验证前的等待时间
                        time.sleep(0.1)
                        with self.lock:
                            verify_data = client.read_area(self.plc_mem_area, 0, byte_offset, 1)
                        verify_value = get_bool(verify_data, 0, bit_offset)
                        if verify_value == value:
                            logger.debug(f"Write verified successfully for {plc_name} Station {station_idx}")
                        else:
                            logger.warning(f"Write verification failed for {plc_name} Station {station_idx}: expected {value}, got {verify_value}")
                            if self.log_callback:
                                self.log_callback(f"PLC写入验证失败 ({plc_name} 工位{station_idx}): 期望 {value}, 实际 {verify_value}")
                    except Exception as verify_e:
                        logger.warning(f"Write verification error for {plc_name} Station {station_idx}: {verify_e}")
                        if self.log_callback:
                            self.log_callback(f"PLC写入验证错误 ({plc_name} 工位{station_idx}): {str(verify_e)}")
                    
                except Exception as e:
                    retry_count += 1
                    error_msg = str(e)
                    logger.error(f"PLC Write Error (attempt {retry_count}/{max_retries}) ({plc_name} Station {station_idx}): {error_msg}")
                    
                    # 根据错误类型调整重试间隔
                    if "CLI : Job pending" in error_msg:
                        # 对于CLI : Job pending错误，使用指数退避策略
                        wait_time = 0.8 * (2 ** retry_count)
                        # 限制最大等待时间为5秒
                        wait_time = min(wait_time, 5.0)
                        logger.info(f"Detected 'CLI : Job pending' error, waiting {wait_time:.1f}s before retry")
                        time.sleep(wait_time)
                    elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
                        # 对于连接错误，等待更长时间
                        wait_time = 1.0
                        time.sleep(wait_time)
                    else:
                        # 其他错误，使用默认间隔
                        wait_time = 0.5 + (retry_count * 0.2)
                        time.sleep(wait_time)
                    
                    if retry_count >= max_retries:
                        if self.log_callback:
                            self.log_callback(f"PLC写入错误: 工位{station_idx} {status_type} - {error_msg}")
                        return
            
        except Exception as e:
            logger.error(f"PLC Write Error ({plc_name} Station {station_idx}): {e}")
            if self.log_callback:
                self.log_callback(f"PLC写入错误: 工位{station_idx} {status_type} - {str(e)}")
    
    def write_status_pulse(self, station_idx, status_type, duration=2.0):
        """
        Write status to PLC with a pulse (ON for duration, then OFF)
        """
        # Set to True immediately
        self.write_status(station_idx, status_type, True)
        
        # Schedule reset to False
        def reset_status():
            self.write_status(station_idx, status_type, False)
            
        timer = threading.Timer(duration, reset_status)
        timer.start()
        
    def write_test_result(self, station_idx, result):
        """
        写入测试结果到PLC (脉冲信号)
        station_idx: 工位索引
        result: 'PASS' 或 'FAIL'
        """
        if result == 'PASS':
            # Ensure FAIL is off
            self.write_status(station_idx, 'FAIL', False)
            # Send PASS pulse
            self.write_status_pulse(station_idx, 'PASS', 2.0)
            if self.log_callback:
                self.log_callback(f"测试结果: 工位{station_idx} 合格 (脉冲信号)")
        elif result == 'FAIL':
            # Ensure PASS is off
            self.write_status(station_idx, 'PASS', False)
            # Send FAIL pulse
            self.write_status_pulse(station_idx, 'FAIL', 2.0)
            if self.log_callback:
                self.log_callback(f"测试结果: 工位{station_idx} 不合格 (脉冲信号)")
        else:
            logger.error(f"Unknown test result: {result}")
    
    def write_wind_speed(self, plc_number, wind_speed):
        """
        写入风速值到PLC
        plc_number: 1或2，表示PLC1或PLC2
        wind_speed: 风速值，0-50浮点数
        """
        # 确定PLC客户端
        if plc_number == 1:
            client = self.client1 if self.connected1 else None
            plc_name = "PLC1"
            plc_ip = self.plc1_ip
        else:
            client = self.client2 if self.connected2 else None
            plc_name = "PLC2"
            plc_ip = self.plc2_ip
        
        if not client:
            logger.error(f"Cannot write wind speed to {plc_name} - not connected")
            if self.log_callback:
                self.log_callback(f"PLC风速写入错误: {plc_name} 未连接")
            return
        
        try:
            # 验证风速范围
            wind_speed = float(wind_speed)
            if wind_speed < 0 or wind_speed > 50:
                logger.error(f"Invalid wind speed value: {wind_speed}. Must be between 0 and 50.")
                if self.log_callback:
                    self.log_callback(f"PLC风速写入错误: 风速值 {wind_speed} 超出范围 (0-50)")
                return
            
            # 写入浮点数到VD0寄存器
            # VD0通常映射到DB1的偏移量0
            from struct import pack, unpack
            
            # 将浮点数转换为字节数组
            wind_speed_bytes = pack('>f', wind_speed)  # BIG_ENDIAN
            
            # 写入到PLC
            max_retries = 5  # 增加重试次数到5次
            retry_count = 0
            success = False
            
            # 确定内存区域常量
            try:
                db_area = snap7.types.Areas.DB
            except AttributeError:
                try:
                    db_area = snap7.Area.DB
                except AttributeError:
                    db_area = 0x84
            
            while retry_count < max_retries and not success:
                try:
                    # 使用DB内存区域 (S7-200 SMART V区通常映射为DB1)
                    # 写入到DB1的偏移量300 (VD300)
                    with self.lock:
                        # 确保连接
                        if not client.get_connected():
                            client.connect(plc_ip, self.rack, self.slot)
                            time.sleep(0.2)  # 连接后等待0.2秒
                        
                        # 1. 执行写入
                        # DB Number = 1, Start = 0
                        client.write_area(db_area, 1, 0, wind_speed_bytes)
                        
                        # 2. 立即回读验证 (Read-Back Verification)
                        # 这一步至关重要，确认数据确实写入了PLC内存
                        verify_bytes = client.read_area(db_area, 1, 0, 4)
                        verify_val = unpack('>f', verify_bytes)[0]
                        
                        # 浮点数比较，允许微小误差
                        if abs(verify_val - wind_speed) < 0.01:
                            logger.info(f"Wrote and Verified wind speed to {plc_name} VD0 (DB1.DBD0): {verify_val:.2f}")
                            success = True
                        else:
                            logger.warning(f"Write verification failed for {plc_name}: Wrote {wind_speed}, Read {verify_val}")
                            raise Exception(f"Verification failed: Wrote {wind_speed}, Read {verify_val}")

                except Exception as e:
                    retry_count += 1
                    error_msg = str(e)
                    logger.error(f"Error writing wind speed (attempt {retry_count}/{max_retries}): {error_msg}")
                    
                    # 根据错误类型调整重试间隔
                    if "CLI : Job pending" in error_msg:
                        wait_time = min(0.8 * (2 ** retry_count), 5.0)
                        logger.info(f"Detected 'CLI : Job pending' error, waiting {wait_time:.1f}s before retry")
                        time.sleep(wait_time)
                    elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
                        time.sleep(1.0)
                    else:
                        time.sleep(0.5 + (retry_count * 0.2))
                    
                    if retry_count >= max_retries:
                        if self.log_callback:
                            self.log_callback(f"PLC风速写入错误: {plc_name} - {str(error_msg)}")
                        return
            
            if success:
                # 写入成功后，等待M22.0反馈信号
                # M22.0为1秒反馈信号
                logger.info(f"Waiting for M22.0 feedback from {plc_name}...")
                feedback_received = False
                wait_start = time.time()
                last_m22_state = False
                
                # 等待最多5秒接收反馈
                while time.time() - wait_start < 5.0:
                    try:
                        # 确定M区常量
                        try:
                            mk_area = snap7.types.Areas.MK
                        except AttributeError:
                            try:
                                mk_area = snap7.Area.MK
                            except AttributeError:
                                mk_area = 0x83
                        
                        with self.lock:
                            # 确保连接
                            if not client.get_connected():
                                client.connect(plc_ip, self.rack, self.slot)
                                time.sleep(0.2)
                            
                            # 读取M区 Byte 22
                            m_data = client.read_area(mk_area, 0, 22, 1)
                            current_m22_state = get_bool(m_data, 0, 0)
                            
                            # 记录M22.0状态
                            # logger.debug(f"{plc_name} M22.0 state: {current_m22_state}")
                            
                            # 边缘检测：检测上升沿
                            if current_m22_state and not last_m22_state:
                                feedback_received = True
                                logger.info(f"Received M22.0 rising edge from {plc_name}")
                                break
                            
                            last_m22_state = current_m22_state
                        
                        # 增加读取频率，减少等待时间 (50ms)
                        time.sleep(0.05)
                    except Exception as e:
                        error_msg = str(e)
                        logger.warning(f"Error reading feedback M22.0: {error_msg}")
                        
                        # 根据错误类型调整等待时间
                        if "CLI : Job pending" in error_msg:
                            time.sleep(0.8)
                        else:
                            time.sleep(0.2)
                
                if feedback_received:
                    logger.info(f"Received M22.0 feedback from {plc_name}")
                    if self.log_callback:
                        self.log_callback(f"PLC风速写入成功: {plc_name} 风速设置为 {wind_speed} (反馈信号 M22.0 确认)")
                else:
                    logger.warning(f"Timeout waiting for M22.0 feedback from {plc_name}")
                    if self.log_callback:
                        self.log_callback(f"PLC风速写入警告: {plc_name} 写入成功但未接收到 M22.0 反馈信号")
                
        except ValueError as e:
            logger.error(f"Invalid wind speed value: {wind_speed} - {e}")
            if self.log_callback:
                self.log_callback(f"PLC风速写入错误: 无效的风速值 {wind_speed}")
        except Exception as e:
            logger.error(f"PLC Write Wind Speed Error ({plc_name}): {e}")
            if self.log_callback:
                self.log_callback(f"PLC风速写入错误: {plc_name} - {str(e)}")

    def set_callbacks(self, on_start, on_stop, on_emergency_stop=None, on_reset=None):
        self.on_start_signal = on_start
        self.on_stop_signal = on_stop
        self.on_emergency_stop = on_emergency_stop
        self.on_reset = on_reset
    
    def set_log_callback(self, log_callback):
        """设置日志回调函数"""
        self.log_callback = log_callback

    def get_calibration_start_signal(self, station_idx):
        """获取校准启动信号"""
        # 这里需要根据实际PLC信号定义实现
        # 暂时返回True，模拟PLC信号
        # 实际项目中需要读取PLC的相应寄存器或位
        return True

    def start(self):
        logger.info("Starting PLC controller...")
        self.connect()
        t = threading.Thread(target=self.monitor_loop, daemon=True)
        t.start()
        logger.info("PLC controller started")
