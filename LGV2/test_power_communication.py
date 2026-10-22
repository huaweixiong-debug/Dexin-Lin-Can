import time
import threading
from Power_6 import ProgrammablePowerSupply
from logger import logger


def test_station(station_address, station_idx, test_duration=10):
    """
    测试单个工位的电源通信
    
    参数:
        station_address: 站地址
        station_idx: 工位索引
        test_duration: 测试持续时间（秒）
    """
    logger.info(f"开始测试工位 {station_idx}，站地址: {station_address}")
    
    try:
        # 创建电源对象
        psu = ProgrammablePowerSupply(port='COM4', station_address=station_address, station_idx=station_idx)
        logger.info(f"成功连接工位 {station_idx} 的电源")
        
        # 开机
        if psu.power_on():
            logger.info(f"工位 {station_idx} 电源开机成功")
        else:
            logger.error(f"工位 {station_idx} 电源开机失败")
            return False
        
        # 设置电压和电流
        if psu.set_voltage(13.0):
            logger.info(f"工位 {station_idx} 电压设置成功: 13.0V")
        else:
            logger.error(f"工位 {station_idx} 电压设置失败")
            return False
        
        if psu.set_current(100):
            logger.info(f"工位 {station_idx} 电流设置成功: 100A")
        else:
            logger.error(f"工位 {station_idx} 电流设置失败")
            return False
        
        # 测试读取状态
        start_time = time.time()
        read_count = 0
        error_count = 0
        
        while time.time() - start_time < test_duration:
            status = psu.read_status()
            if status:
                voltage = status['voltage']
                current = status['current']
                logger.info(f"工位 {station_idx} 读取成功: 电压={voltage:.2f}V, 电流={current:.2f}A")
                read_count += 1
            else:
                logger.error(f"工位 {station_idx} 读取失败")
                error_count += 1
            
            # 等待0.5秒
            time.sleep(0.5)
        
        # 关机
        if psu.power_off():
            logger.info(f"工位 {station_idx} 电源关机成功")
        else:
            logger.error(f"工位 {station_idx} 电源关机失败")
        
        # 关闭连接
        psu.close()
        
        logger.info(f"工位 {station_idx} 测试完成: 成功读取 {read_count} 次, 失败 {error_count} 次")
        return True
        
    except Exception as e:
        logger.error(f"工位 {station_idx} 测试异常: {e}")
        return False


def main():
    """
    主测试函数
    """
    logger.info("===== 开始测试COM4的站号6和7的电源通讯 =====")
    
    # 顺序测试两个站，确保通信间隔
    logger.info("测试站号6...")
    test_station(6, 6, 5)
    
    # 短暂等待，确保间隔
    time.sleep(0.1)
    
    logger.info("测试站号7...")
    test_station(7, 7, 5)
    
    logger.info("===== 测试完成 =====")


if __name__ == "__main__":
    main()
