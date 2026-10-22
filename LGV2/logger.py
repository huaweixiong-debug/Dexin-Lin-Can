import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

class Logger:
    def __init__(self, name='LGV2', log_dir='logs'):
        self.name = name
        self.log_dir = log_dir
        self.logger = None
        self._setup_logger()
    
    def _setup_logger(self):
        # 确保日志目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # 清除现有处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 创建文件处理器（按天轮转）
        log_file = os.path.join(self.log_dir, f'{self.name}_log.txt')
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.suffix = '%Y-%m-%d'
        self.logger.addHandler(file_handler)
    
    def get_logger(self):
        return self.logger
    
    def debug(self, message):
        self.logger.debug(message)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)

# 创建全局日志实例
logger = Logger().get_logger()

if __name__ == '__main__':
    # 测试日志功能
    test_logger = Logger('Test').get_logger()
    test_logger.debug('这是一条DEBUG日志')
    test_logger.info('这是一条INFO日志')
    test_logger.warning('这是一条WARNING日志')
    test_logger.error('这是一条ERROR日志')
    test_logger.critical('这是一条CRITICAL日志')
    print('日志测试完成，查看logs目录下的日志文件')
