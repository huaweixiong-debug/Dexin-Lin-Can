import time
from Power_6 import ProgrammablePowerSupply
from logger import logger
from power_communication_manager import power_comm_manager


def test_communication_interval():
    """
    测试通信间隔是否至少为5ms
    """
    logger.info("===== 开始测试通信间隔 ======")
    
    try:
        # 创建电源对象
        psu = ProgrammablePowerSupply(port='COM4', station_address=6, station_idx=6)
        logger.info("成功连接电源")
        
        # 开机
        if psu.power_on():
            logger.info("电源开机成功")
        else:
            logger.error("电源开机失败")
            return
        
        # 测试多次通信，记录时间间隔
        communication_times = []
        test_count = 10
        
        logger.info(f"开始测试 {test_count} 次通信的时间间隔")
        
        for i in range(test_count):
            start_time = time.time() * 1000  # 转换为毫秒
            
            # 执行通信操作
            status = psu.read_status()
            
            end_time = time.time() * 1000  # 转换为毫秒
            communication_times.append(end_time)
            
            if status:
                voltage = status['voltage']
                current = status['current']
                logger.info(f"通信 {i+1}: 电压={voltage:.2f}V, 电流={current:.2f}A, 时间={end_time:.2f}ms")
            else:
                logger.error(f"通信 {i+1}: 读取失败")
            
            # 短暂等待，避免过快的连续操作
            time.sleep(0.1)
        
        # 计算时间间隔
        intervals = []
        for i in range(1, len(communication_times)):
            interval = communication_times[i] - communication_times[i-1]
            intervals.append(interval)
            logger.info(f"通信间隔 {i}: {interval:.2f}ms")
        
        # 统计结果
        if intervals:
            min_interval = min(intervals)
            avg_interval = sum(intervals) / len(intervals)
            max_interval = max(intervals)
            
            logger.info(f"===== 通信间隔统计 ======")
            logger.info(f"最小间隔: {min_interval:.2f}ms")
            logger.info(f"平均间隔: {avg_interval:.2f}ms")
            logger.info(f"最大间隔: {max_interval:.2f}ms")
            
            # 检查是否满足最小5ms间隔
            if min_interval >= 5:
                logger.info("✅ 所有通信间隔都大于等于5ms，符合要求")
            else:
                logger.warning(f"❌ 发现小于5ms的间隔: {min_interval:.2f}ms")
        
        # 关机
        if psu.power_off():
            logger.info("电源关机成功")
        else:
            logger.error("电源关机失败")
        
        # 关闭连接
        psu.close()
        
        # 获取通信管理器统计信息
        stats = power_comm_manager.get_stats()
        logger.info(f"通信管理器统计: 总通信次数={stats['total_communications']}, 最小间隔={stats['min_interval_ms']}ms")
        
    except Exception as e:
        logger.error(f"测试异常: {e}")
    
    logger.info("===== 测试完成 ======")


def main():
    """
    主测试函数
    """
    test_communication_interval()


if __name__ == "__main__":
    main()
