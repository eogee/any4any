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


def get_audio_duration(file_path: str) -> float:
    """获取音频文件时长"""
    try:
        info = torchaudio.info(file_path)
        return info.num_frames / info.sample_rate
    except Exception as e:
        logging.warning(f"Cannot get audio duration: {str(e)}")
        return 0.0

def clean_img_text(text: str)  -> str:
    """过滤img标签及内容"""
    pattern_full_img = r'<img\b[^>]*>'                      # 匹配完整标签
    pattern_start_img = r'<img\b[^>]*$'                     # 匹配开头标签
    pattern_end_alt = r'[^<]*alt="image">'                  # 匹配结尾alt标签

    cleaned = re.sub(pattern_full_img, '', text)
    if cleaned != text:                                     # 如果完整标签被替换过，直接返回结果
        return cleaned.strip()

    cleaned = re.sub(pattern_start_img, '', cleaned)
    cleaned = re.sub(pattern_end_alt, '', cleaned)
    return cleaned.strip()

def clean_video_text(text: str)  -> str:
    """过滤video标签及内容"""
    pattern_full_video = r'<video\b[^>]*>[\s\S]*?</video>'  # 匹配完整标签
    pattern_start_video = r'<video\b[\s\S]*$'               # 匹配开头标签
    pattern_end_video = r'[\s\S]*?</video>'                 # 匹配结尾标签

    cleaned = re.sub(pattern_full_video, '', text, flags=re.DOTALL)
    if cleaned != text:  # 如果完整标签被替换过，直接返回结果
        return cleaned.strip()

    cleaned = re.sub(pattern_start_video, '', cleaned)
    cleaned = re.sub(pattern_end_video, '', cleaned)
    return cleaned.strip()

def filter_special_chars(text: str) -> str:
    """过滤文本转语音特殊字符"""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'[#*]', '', text)
    text = clean_img_text(text)
    text = clean_video_text(text)
    return text

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
