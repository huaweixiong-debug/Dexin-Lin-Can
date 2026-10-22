import threading
import time
from typing import Optional
from logger import logger

class PowerCommunicationManager:
    """
    电源通信管理器
    确保10个电源的数据发送和读取至少有5ms的间隔
    """
    _instance: Optional['PowerCommunicationManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """初始化通信管理器"""
        self.communication_lock = threading.Lock()
        self.last_communication_end_time = 0  # 上次通信结束时间
        self.min_interval_ms = 5  # 最小间隔5ms
        self.communication_count = 0
        self.log_prefix = "[PowerCommManager]"
        
        logger.info(f"{self.log_prefix} 电源通信管理器已初始化，最小间隔: {self.min_interval_ms}ms")
    
    def acquire_communication_slot(self, station_idx: int = 0) -> bool:
        """
        获取通信时隙，确保同一时间只有一个通信操作在进行，且至少有5ms的间隔
        
        参数:
            station_idx: 工位索引（1-10），0表示未知工位
            
        返回:
            bool: 是否成功获取通信时隙
        """
        current_time = time.time() * 1000  # 转换为毫秒
        time_since_last = current_time - self.last_communication_end_time
        
        # 如果距离上次通信结束不足5ms，等待
        if time_since_last < self.min_interval_ms:
            wait_time = (self.min_interval_ms - time_since_last) / 1000.0  # 转换为秒
            if wait_time > 0:
                time.sleep(wait_time)
        
        self.communication_count += 1
        
        station_info = f"工位{station_idx}" if station_idx > 0 else "未知工位"
        # logger.debug(f"{self.log_prefix} 通信时隙获取成功: {station_info}, 通信计数: {self.communication_count}")
        
        return True
    
    def __enter__(self):
        """
        上下文管理器进入方法
        获取通信锁并获取通信时隙
        """
        self.communication_lock.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器退出方法
        释放通信锁
        """
        # 更新最后通信结束时间
        self.last_communication_end_time = time.time() * 1000
        self.communication_lock.release()
    
    def wrap_communication(self, station_idx: int = 0):
        """
        装饰器函数，用于包装通信操作
        
        参数:
            station_idx: 工位索引（1-10），0表示未知工位
            
        返回:
            装饰器函数
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # 使用上下文管理器确保原子操作
                with self:
                    # 获取通信时隙
                    self.acquire_communication_slot(station_idx)
                    
                    # 执行通信操作
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        logger.error(f"{self.log_prefix} 通信操作失败: {e}")
                        raise
            return wrapper
        return decorator
    
    def get_stats(self) -> dict:
        """
        获取通信统计信息
        
        返回:
            dict: 统计信息字典
        """
        with self.communication_lock:
            return {
                "total_communications": self.communication_count,
                "min_interval_ms": self.min_interval_ms,
                "last_communication_time": self.last_communication_end_time
            }


# 全局通信管理器实例
power_comm_manager = PowerCommunicationManager()