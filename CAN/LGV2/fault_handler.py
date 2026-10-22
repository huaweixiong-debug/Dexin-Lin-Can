#coding:utf-8
import threading
import time
from datetime import datetime

# 故障代码定义
FAULT_CODES = {
    0x01: {"name": "过压", "level": 2},
    0x02: {"name": "欠压", "level": 1},
    0x03: {"name": "IGBT短路", "level": 3},
    0x04: {"name": "芯体短路", "level": 3},
    0x05: {"name": "IGBT开路", "level": 2},
    0x06: {"name": "PTC过温", "level": 1},
    0x07: {"name": "IGBT过温", "level": 1},
    0x08: {"name": "PTC温度传感器故障", "level": 2},
    0x09: {"name": "IGBT温度传感器故障", "level": 2},
    0x0A: {"name": "PTC CAN通讯故障", "level": 1},
    0x0B: {"name": "PTC过流故障", "level": 3}
}

# 故障级别定义
FAULT_LEVELS = {
    1: "一般故障",
    2: "中度故障",
    3: "严重故障"
}

class FaultHandler:
    def __init__(self):
        """初始化故障处理器"""
        self.faults = {}
        self.station_status = {}
        self.callbacks = {}
        self.lock = threading.Lock()
    
    def register_callback(self, event_type, callback):
        """注册故障处理回调函数"""
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
    
    def notify_callbacks(self, event_type, *args, **kwargs):
        """通知回调函数"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Error in callback: {e}")
    
    def detect_fault(self, station_id, ptc_data):
        """检测故障"""
        if not ptc_data:
            return None
        
        error_code = ptc_data.get("error_code", 0)
        error_level = ptc_data.get("error_level", 0)
        
        if error_code > 0:
            fault_info = FAULT_CODES.get(error_code, {"name": f"未知故障 {error_code}", "level": error_level})
            fault = {
                "station_id": station_id,
                "code": error_code,
                "level": error_level,
                "name": fault_info["name"],
                "timestamp": datetime.now(),
                "ptc_data": ptc_data
            }
            
            with self.lock:
                if station_id not in self.faults:
                    self.faults[station_id] = []
                self.faults[station_id].append(fault)
            
            # 通知故障检测
            self.notify_callbacks("fault_detected", station_id, fault)
            
            # 检查是否需要停止测试
            if error_level in [1, 3]:  # 一般故障(0x2)和严重故障(0x3)
                self.handle_serious_fault(station_id, fault)
            
            return fault
        
        return None
    
    def handle_serious_fault(self, station_id, fault):
        """处理严重故障"""
        print(f"处理严重故障 - 工位{station_id}: {fault['name']} (代码: {fault['code']}, 级别: {fault['level']})")
        
        # 标记工位状态为故障
        with self.lock:
            self.station_status[station_id] = "fault"
        
        # 通知需要停止测试
        self.notify_callbacks("stop_test", station_id, fault)
    
    def clear_faults(self, station_id):
        """清除工位的所有故障"""
        with self.lock:
            if station_id in self.faults:
                del self.faults[station_id]
            if station_id in self.station_status:
                del self.station_status[station_id]
        
        print(f"已清除工位{station_id}的所有故障")
    
    def get_station_faults(self, station_id):
        """获取工位的所有故障"""
        with self.lock:
            return self.faults.get(station_id, [])
    
    def get_station_status(self, station_id):
        """获取工位状态"""
        with self.lock:
            return self.station_status.get(station_id, "normal")
    
    def is_station_in_fault(self, station_id):
        """检查工位是否处于故障状态"""
        with self.lock:
            return self.station_status.get(station_id) == "fault"
    
    def get_fault_summary(self, station_id):
        """获取故障摘要"""
        faults = self.get_station_faults(station_id)
        if not faults:
            return "无故障"
        
        latest_fault = faults[-1]
        return f"{latest_fault['name']} (代码: {latest_fault['code']}, 级别: {FAULT_LEVELS.get(latest_fault['level'], '未知')})"

# 全局故障处理器实例
fault_handler = None

# 初始化故障处理器
def init_fault_handler():
    global fault_handler
    fault_handler = FaultHandler()
    return fault_handler

# 获取故障处理器实例
def get_fault_handler():
    global fault_handler
    if fault_handler is None:
        fault_handler = FaultHandler()
    return fault_handler
