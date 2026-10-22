import time
from scanner import scanner_manager, Scanner
from logger import logger

# 测试扫码枪连接和扫码功能
def test_scanner():
    logger.info("开始测试扫码枪功能...")
    
    # 测试工位6的扫码枪（IP: 192.168.10.228:8888）
    station_idx = 6
    scanner_ip = "192.168.10.228:8888"
    
    # 添加扫码枪
    scanner_manager.add_scanner(station_idx, scanner_ip)
    
    # 获取扫码枪
    scanner = scanner_manager.get_scanner(station_idx)
    if not scanner:
        logger.error(f"无法获取工位{station_idx}的扫码枪")
        return
    
    # 连接扫码枪
    logger.info(f"正在连接扫码枪 {scanner_ip}...")
    if scanner.connect():
        logger.info("扫码枪连接成功！")
        
        # 执行扫码
        logger.info("等待扫码...")
        scan_result = scanner.scan(timeout=60)
        if scan_result:
            logger.info(f"扫码成功！结果: {scan_result}")
        else:
            logger.error("扫码失败或超时")
        
        # 断开连接
        scanner.disconnect()
    else:
        logger.error("扫码枪连接失败")
    
    logger.info("扫码枪测试完成")

if __name__ == "__main__":
    test_scanner()
