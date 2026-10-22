import socket
import time
import threading
import queue
from logger import logger

class Scanner:
    def __init__(self, scanner_ip, port=8888, timeout=5, mode='client'):
        """
        初始化扫码枪
        scanner_ip: 扫码枪IP地址，可以包含端口号（如"192.168.10.228:8888"）
        port: 扫码枪端口，默认为8888（TCP服务器模式），如果scanner_ip中包含端口号，则忽略此参数
        timeout: 超时时间，默认为5秒
        mode: 连接模式，'client'（作为客户端连接到扫码枪的TCP服务器）或'server'（作为服务器等待扫码枪连接）
        """
        # 解析scanner_ip，处理包含端口号的情况
        if ':' in scanner_ip:
            self.scanner_ip, port_str = scanner_ip.split(':', 1)
            try:
                self.port = int(port_str)
            except ValueError:
                self.port = 8888
                logger.warning(f"Invalid port in scanner_ip: {port_str}, using default port 8888")
        else:
            self.scanner_ip = scanner_ip
            self.port = port
        self.timeout = timeout
        self.mode = mode
        self.sock = None
        self.client_sock = None
        self.connected = False
        self.lock = threading.Lock()
        self.scan_result = ""
        self.scan_queue = queue.Queue()
        self.scan_thread = None
        self.running = False
        self.callback = None
    
    def connect(self):
        """
        连接扫码枪
        """
        with self.lock:
            try:
                if self.connected:
                    logger.info(f"Scanner {self.scanner_ip} is already connected")
                    return True
                
                if self.mode == 'client':
                    # 作为客户端连接到扫码枪的TCP服务器
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(self.timeout)
                    self.sock.connect((self.scanner_ip, self.port))
                    self.connected = True
                    logger.info(f"Connected to scanner TCP server at {self.scanner_ip}:{self.port}")
                    return True
                elif self.mode == 'server':
                    # 作为服务器等待扫码枪连接
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(self.timeout)
                    self.sock.bind(('0.0.0.0', self.port))
                    self.sock.listen(1)
                    logger.info(f"Scanner TCP server started on port {self.port}, waiting for connection...")
                    
                    # 等待客户端连接
                    self.client_sock, client_addr = self.sock.accept()
                    self.connected = True
                    logger.info(f"Scanner connected from {client_addr}")
                    return True
            except Exception as e:
                logger.error(f"Failed to connect to scanner {self.scanner_ip}: {e}")
                self.connected = False
                return False
    
    def disconnect(self):
        """
        断开扫码枪连接
        """
        with self.lock:
            try:
                if self.connected:
                    if self.client_sock:
                        self.client_sock.close()
                        self.client_sock = None
                    if self.sock:
                        self.sock.close()
                        self.sock = None
                    self.connected = False
                    logger.info(f"Disconnected from scanner {self.scanner_ip}")
            except Exception as e:
                logger.error(f"Error disconnecting from scanner {self.scanner_ip}: {e}")
            finally:
                self.connected = False
                self.sock = None
                self.client_sock = None
    
    def is_connected(self):
        """
        检查连接状态
        """
        return self.connected
    
    def start_auto_scan(self, callback=None):
        """
        启动自动扫码
        callback: 扫码结果回调函数，参数为(station_idx, scan_result)
        """
        self.callback = callback
        self.running = True
        self.scan_thread = threading.Thread(target=self._auto_scan_loop, daemon=True)
        self.scan_thread.start()
        logger.info(f"Auto scan started for scanner {self.scanner_ip}")
    
    def stop_auto_scan(self):
        """
        停止自动扫码
        """
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        logger.info(f"Auto scan stopped for scanner {self.scanner_ip}")
    
    def _auto_scan_loop(self):
        """
        自动扫码循环
        """
        while self.running:
            try:
                if not self.connected:
                    if not self.connect():
                        time.sleep(1)
                        continue
                
                # 选择使用的socket
                current_sock = self.client_sock if self.client_sock else self.sock
                
                # 清空缓冲区
                current_sock.setblocking(False)
                try:
                    while True:
                        data = current_sock.recv(1024)
                        if not data:
                            break
                        logger.debug(f"Cleared buffer: {data}")
                except BlockingIOError:
                    pass
                except Exception as e:
                    logger.warning(f"Error clearing buffer: {e}")
                
                # 设置为阻塞模式进行扫码
                current_sock.setblocking(True)
                current_sock.settimeout(1)  # 短超时，用于轮询
                
                # 接收扫码数据
                data = b""
                try:
                    chunk = current_sock.recv(1024)
                    if not chunk:
                        logger.warning(f"Connection closed by scanner {self.scanner_ip}")
                        self.connected = False
                        continue
                    data += chunk
                    
                    # 检查是否包含换行符或回车符（通常扫码枪会在数据末尾添加这些字符）
                    if b'\n' in data or b'\r' in data:
                        # 处理扫码结果
                        if data:
                            # 尝试多种编码方式解码
                            encodings = ['utf-8', 'gbk', 'ascii']
                            result = ""
                            for encoding in encodings:
                                try:
                                    result = data.decode(encoding).strip()
                                    if result:
                                        break
                                except:
                                    pass
                            
                            if not result:
                                # 如果所有编码方式都失败，使用原始数据
                                result = str(data).strip()
                            
                            self.scan_result = result
                            logger.info(f"Auto scanned from {self.scanner_ip}: {result}")
                            
                            # 将扫码结果放入队列
                            self.scan_queue.put(result)
                            
                            # 调用回调函数
                            if self.callback:
                                self.callback(result)
                except socket.timeout:
                    # 超时是正常的，继续循环
                    pass
                except Exception as e:
                    logger.error(f"Error during auto scan: {e}")
                    self.connected = False
                
            except Exception as e:
                logger.error(f"Auto scan loop error: {e}")
                time.sleep(1)
    
    def get_scan_result(self, timeout=0.1):
        """
        获取扫码结果
        timeout: 超时时间，默认为0.1秒
        返回: 扫码结果字符串，如果没有结果则返回空字符串
        """
        try:
            return self.scan_queue.get(timeout=timeout)
        except queue.Empty:
            return ""
    
    def scan(self, timeout=60):
        """
        执行扫码操作（兼容旧接口）
        timeout: 扫码超时时间，默认为60秒
        返回: 扫码结果字符串
        """
        with self.lock:
            try:
                if not self.connected:
                    if not self.connect():
                        logger.error(f"Cannot scan - scanner {self.scanner_ip} not connected")
                        return ""
                
                # 选择使用的socket
                current_sock = self.client_sock if self.client_sock else self.sock
                
                # 清空缓冲区
                current_sock.setblocking(False)
                try:
                    while True:
                        data = current_sock.recv(1024)
                        if not data:
                            break
                        logger.debug(f"Cleared buffer: {data}")
                except BlockingIOError:
                    pass
                except Exception as e:
                    logger.warning(f"Error clearing buffer: {e}")
                
                # 设置为阻塞模式进行扫码
                current_sock.setblocking(True)
                current_sock.settimeout(timeout)
                
                logger.info(f"Waiting for scan from {self.scanner_ip}:{self.port}...")
                
                # 接收扫码数据
                data = b""
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    try:
                        chunk = current_sock.recv(1024)
                        if not chunk:
                            logger.warning(f"Connection closed by scanner {self.scanner_ip}")
                            self.connected = False
                            return ""
                        data += chunk
                        logger.debug(f"Received chunk: {chunk}")
                        
                        # 检查是否包含换行符或回车符（通常扫码枪会在数据末尾添加这些字符）
                        if b'\n' in data or b'\r' in data:
                            break
                    except socket.timeout:
                        logger.warning(f"Scan timeout for {self.scanner_ip}")
                        return ""
                    except Exception as e:
                        logger.error(f"Error during scan: {e}")
                        self.connected = False
                        return ""
                
                # 处理扫码结果
                if data:
                    # 尝试多种编码方式解码
                    encodings = ['utf-8', 'gbk', 'ascii']
                    result = ""
                    for encoding in encodings:
                        try:
                            result = data.decode(encoding).strip()
                            if result:
                                break
                        except:
                            pass
                    
                    if not result:
                        # 如果所有编码方式都失败，使用原始数据
                        result = str(data).strip()
                    
                    self.scan_result = result
                    logger.info(f"Scanned from {self.scanner_ip}: {result}")
                    return result
                else:
                    logger.warning(f"No data received from scanner {self.scanner_ip}")
                    return ""
                    
            except Exception as e:
                logger.error(f"Scan failed for {self.scanner_ip}: {e}")
                import traceback
                traceback.print_exc()
                self.connected = False
                return ""
            finally:
                if self.sock and not self.client_sock:
                    try:
                        self.sock.setblocking(False)
                    except:
                        pass
                elif self.client_sock:
                    try:
                        self.client_sock.setblocking(False)
                    except:
                        pass
    
    def get_last_scan_result(self):
        """
        获取上次扫码结果
        """
        return self.scan_result
    
    def reset_scan_result(self):
        """
        重置扫码结果
        """
        self.scan_result = ""

class ScannerManager:
    def __init__(self):
        """
        扫码枪管理器
        """
        self.scanners = {}
        self.lock = threading.Lock()
        self.callbacks = {}  # station_idx -> callback
    
    def add_scanner(self, station_idx, scanner_ip, port=8888, mode='client'):
        """
        添加扫码枪
        station_idx: 工位索引
        scanner_ip: 扫码枪IP地址
        port: 扫码枪端口
        mode: 连接模式，'client'或'server'
        """
        with self.lock:
            if station_idx not in self.scanners:
                self.scanners[station_idx] = Scanner(scanner_ip, port, mode=mode)
                logger.info(f"Added scanner {scanner_ip}:{port} (mode: {mode}) for station {station_idx}")
            else:
                logger.warning(f"Scanner already exists for station {station_idx}")
    
    def get_scanner(self, station_idx):
        """
        获取指定工位的扫码枪
        station_idx: 工位索引
        """
        with self.lock:
            return self.scanners.get(station_idx)
    
    def start_auto_scan_all(self, callback=None):
        """
        启动所有扫码枪的自动扫码
        callback: 扫码结果回调函数，参数为(station_idx, scan_result)
        """
        with self.lock:
            for station_idx, scanner in self.scanners.items():
                def make_callback(idx):
                    def cb(result):
                        if callback:
                            callback(idx, result)
                    return cb
                
                scanner.start_auto_scan(make_callback(station_idx))
            logger.info("Started auto scan for all scanners")
    
    def stop_auto_scan_all(self):
        """
        停止所有扫码枪的自动扫码
        """
        with self.lock:
            for scanner in self.scanners.values():
                scanner.stop_auto_scan()
            logger.info("Stopped auto scan for all scanners")
    
    def scan_station(self, station_idx, timeout=60):
        """
        扫描指定工位（兼容旧接口）
        station_idx: 工位索引
        timeout: 超时时间
        """
        scanner = self.get_scanner(station_idx)
        if scanner:
            return scanner.scan(timeout)
        else:
            logger.error(f"No scanner found for station {station_idx}")
            return ""
    
    def get_scan_result(self, station_idx, timeout=0.1):
        """
        获取指定工位的扫码结果
        station_idx: 工位索引
        timeout: 超时时间
        """
        scanner = self.get_scanner(station_idx)
        if scanner:
            return scanner.get_scan_result(timeout)
        else:
            logger.error(f"No scanner found for station {station_idx}")
            return ""
    
    def disconnect_all(self):
        """
        断开所有扫码枪连接
        """
        with self.lock:
            for station_idx, scanner in self.scanners.items():
                scanner.disconnect()
            logger.info("Disconnected all scanners")

# 创建全局扫码枪管理器实例
scanner_manager = ScannerManager()

if __name__ == '__main__':
    # 测试扫码枪功能
    test_scanner = Scanner('192.168.10.228', port=8888, mode='client')
    print('Testing scanner connection...')
    if test_scanner.connect():
        print('Scanner connected successfully')
        print('Waiting for scan...')
        result = test_scanner.scan(timeout=60)
        print(f'Scan result: {result}')
        test_scanner.disconnect()
    else:
        print('Failed to connect to scanner')