import os
import logging
import time
import asyncio
from fastapi.responses import FileResponse
import torchaudio

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

async def delayed_cleanup_file(filepath: str, delay_seconds: int = 100):
    """延迟清理临时文件，给前端足够的时间下载"""
    try:
        await asyncio.sleep(delay_seconds)
        cleanup_file(filepath)
    except Exception as e:
        logging.error(f"Error in delayed cleanup for {filepath}: {str(e)}")


def get_audio_duration(file_path: str) -> float:
    """获取音频文件时长"""
    try:
        info = torchaudio.info(file_path)
        return info.num_frames / info.sample_rate
    except Exception as e:
        logging.warning(f"Cannot get audio duration: {str(e)}")
        return 0.0

class file_response_with_cleanup(FileResponse):
    """带自动清理功能的文件响应，使用延迟清理避免前端下载中断"""
    def __init__(self, *args, cleanup_file: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleanup_file = cleanup_file
    
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            if self.cleanup_file:
                # 使用延迟清理，给前端足够的时间下载文件
                # 注意：这里使用asyncio.create_task创建一个后台任务，不阻塞响应
                # 延迟时间可以根据文件大小调整，默认100秒
                logging.info(f"Scheduling delayed cleanup for file: {self.cleanup_file}")
                asyncio.create_task(delayed_cleanup_file(self.cleanup_file, delay_seconds=100))