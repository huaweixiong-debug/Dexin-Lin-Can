import serial
import threading
from logger import logger

class SerialManager:
    """
    串口管理器
    实现同一个COM口的共享，避免多次打开同一个串口
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """初始化串口管理器"""
        self.serial_ports = {}  # 串口号 -> (serial_instance, ref_count)
        self.port_locks = {}    # 串口号 -> threading.Lock
        self.log_prefix = "[SerialManager]"
        logger.info(f"{self.log_prefix} 串口管理器已初始化")
    
    def get_serial(self, port='COM4', **kwargs):
        """
        获取串口实例
        如果串口已打开，返回现有实例并增加引用计数
        如果未打开，创建新实例并设置引用计数为1
        
        参数:
            port: 串口号
            **kwargs: 串口参数
            
        返回:
            serial.Serial: 串口实例
        """
        with self._lock:
            # 确保端口锁存在
            if port not in self.port_locks:
                self.port_locks[port] = threading.Lock()
            
            # 获取端口锁
            port_lock = self.port_locks[port]
            
        with port_lock:
            with self._lock:
                if port in self.serial_ports:
                    # 串口已存在，增加引用计数
                    serial_instance, ref_count = self.serial_ports[port]
                    new_ref_count = ref_count + 1
                    self.serial_ports[port] = (serial_instance, new_ref_count)
                    logger.info(f"{self.log_prefix} 共享串口 {port}, 当前引用计数: {new_ref_count}")
                    return serial_instance
                else:
                    # 串口不存在，创建新实例
                    try:
                        serial_instance = serial.Serial(
                            port=port,
                            baudrate=kwargs.get('baudrate', 9600),
                            bytesize=kwargs.get('bytesize', serial.EIGHTBITS),
                            parity=kwargs.get('parity', serial.PARITY_NONE),
                            stopbits=kwargs.get('stopbits', serial.STOPBITS_ONE),
                            timeout=kwargs.get('timeout', 1)
                        )
                        self.serial_ports[port] = (serial_instance, 1)
                        logger.info(f"{self.log_prefix} 打开串口 {port}, 引用计数: 1")
                        return serial_instance
                    except Exception as e:
                        logger.error(f"{self.log_prefix} 打开串口 {port} 失败: {e}")
                        raise
    
    def release_serial(self, port='COM4'):
        """
        释放串口实例
        减少引用计数，当引用计数为0时关闭串口
        
        参数:
            port: 串口号
        """
        with self._lock:
            if port not in self.serial_ports:
                logger.warning(f"{self.log_prefix} 释放不存在的串口 {port}")
                return
            
            # 获取端口锁
            port_lock = self.port_locks.get(port, threading.Lock())
            
        with port_lock:
            with self._lock:
                serial_instance, ref_count = self.serial_ports[port]
                new_ref_count = ref_count - 1
                
                if new_ref_count > 0:
                    # 还有其他引用，更新引用计数
                    self.serial_ports[port] = (serial_instance, new_ref_count)
                    logger.info(f"{self.log_prefix} 释放串口 {port}, 当前引用计数: {new_ref_count}")
                else:
                    # 引用计数为0，关闭串口
                    try:
                        serial_instance.close()
                        logger.info(f"{self.log_prefix} 关闭串口 {port}")
                    except Exception as e:
                        logger.error(f"{self.log_prefix} 关闭串口 {port} 失败: {e}")
                    finally:
                        del self.serial_ports[port]
                        if port in self.port_locks:
                            del self.port_locks[port]
    
    def get_port_status(self, port='COM4'):
        """
        获取串口状态
        
        参数:
            port: 串口号
            
        返回:
            dict: 串口状态信息
        """
        with self._lock:
            if port in self.serial_ports:
                serial_instance, ref_count = self.serial_ports[port]
                return {
                    "port": port,
                    "open": serial_instance.is_open,
                    "ref_count": ref_count,
                    "baudrate": serial_instance.baudrate
                }
            else:
                return {
                    "port": port,
                    "open": False,
                    "ref_count": 0
                }
    
    def get_all_ports(self):
        """
        获取所有管理的串口
        
        返回:
            dict: 所有串口的状态信息
        """
        with self._lock:
            status = {}
            for port in self.serial_ports:
                status[port] = self.get_port_status(port)
            return status


# 全局串口管理器实例
serial_manager = SerialManager()