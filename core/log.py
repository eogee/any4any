import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """配置双输出日志系统"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 清除现有handler
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 控制台Handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # 文件Handler
    file_handler = RotatingFileHandler(
        'api.log',
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)