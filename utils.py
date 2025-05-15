import os
import re
import logging
from logging.handlers import RotatingFileHandler
from fastapi.responses import FileResponse
import torchaudio

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
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

def cleanup_file(filepath: str):
    """清理临时文件"""
    if not filepath:
        return
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Cleaned up temporary file: {filepath}")
    except Exception as e:
        logging.error(f"Error cleaning up file {filepath}: {str(e)}")

def filter_special_chars(text: str) -> str:
    """过滤特殊字符"""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<video\b[^>]*>.*?</video>', '', text, flags=re.DOTALL)
    text = re.sub(r'[#*]', '', text)
    return text

def get_audio_duration(file_path: str) -> float:
    """获取音频文件时长"""
    try:
        info = torchaudio.info(file_path)
        return info.num_frames / info.sample_rate
    except Exception as e:
        logging.warning(f"Cannot get audio duration: {str(e)}")
        return 0.0

class FileResponseWithCleanup(FileResponse):
    """带自动清理功能的文件响应"""
    def __init__(self, *args, cleanup_file: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleanup_file = cleanup_file
    
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            if self.cleanup_file:
                cleanup_file(self.cleanup_file)
