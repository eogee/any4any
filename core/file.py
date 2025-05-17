import os
import logging
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


def get_audio_duration(file_path: str) -> float:
    """获取音频文件时长"""
    try:
        info = torchaudio.info(file_path)
        return info.num_frames / info.sample_rate
    except Exception as e:
        logging.warning(f"Cannot get audio duration: {str(e)}")
        return 0.0

class file_response_with_cleanup(FileResponse):
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