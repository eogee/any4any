import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """配置双输出日志系统"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 清除现有handler
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 控制台Handler（显示标准格式）
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # 文件Handler（持久化存储）
    file_handler = RotatingFileHandler(
        'api.log',
        maxBytes=10*1024*1024,  # 单个日志文件最大10MB（字节数计算：10*1024*1024）
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
