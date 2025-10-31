import os
import uuid
import tempfile
import logging
import threading
import time
from typing import Optional, Set, Dict, Any, Union
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class TempFileManager:
    """临时文件管理器"""

    _instance = None
    _initialized = False

    def __new__(cls, temp_dir: Optional[str] = None, max_file_age: int = 3600, cleanup_interval: int = 300):
        if cls._instance is None:
            cls._instance = super(TempFileManager, cls).__new__(cls)
        return cls._instance

    def __init__(self,
                 temp_dir: Optional[str] = None,
                 max_file_age: int = 3600,  # 1小时
                 cleanup_interval: int = 300):  # 5分钟

        # 防止重复初始化
        if self._initialized:
            return

        self._initialized = True
        """
        初始化临时文件管理器

        Args:
            temp_dir: 临时文件目录，None则使用当前工作目录
            max_file_age: 最大文件保存时间（秒）
            cleanup_interval: 清理间隔（秒）
        """
        # 如果没有指定目录，使用当前工作目录
        if temp_dir is None:
            self.temp_dir = "."
        else:
            self.temp_dir = temp_dir

        self.max_file_age = max_file_age
        self.cleanup_interval = cleanup_interval
        self._registered_files: Set[str] = set()  # 注册的临时文件
        self._lock = threading.Lock()

        # 启动后台清理线程
        if temp_dir is not None:
            self._cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
            self._cleanup_thread.start()
            Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

    def create_temp_file(self, suffix: str = ".mp3", prefix: str = "temp_") -> str:
        """
        创建临时文件路径

        Args:
            suffix: 文件后缀
            prefix: 文件前缀

        Returns:
            临时文件路径
        """
        filename = f"{prefix}{uuid.uuid4().hex}{suffix}"

        if self.temp_dir == ".":
            filepath = os.path.abspath(filename)
        else:
            # 使用专用临时目录
            filepath = os.path.join(self.temp_dir, filename)

        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # 注册文件以便管理
        with self._lock:
            self._registered_files.add(filepath)

        return filepath

    def register_temp_file(self, filepath: str):
        """
        注册已创建的临时文件

        Args:
            filepath: 文件路径
        """
        with self._lock:
            self._registered_files.add(filepath)

    def mark_file_completed(self, filepath: str):
        """
        标记文件已完成，从活跃管理中移除

        Args:
            filepath: 文件路径
        """
        # 这个方法主要供后台清理使用，暂时不移除注册
        # 文件仍然会被定时清理机制处理
        pass

    def cleanup_file(self, filepath: str) -> bool:
        """
        清理指定文件

        Args:
            filepath: 文件路径

        Returns:
            是否成功清理
        """
        if not filepath:
            return False

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"Error cleaning up file {filepath}: {str(e)}")
        finally:
            with self._lock:
                self._registered_files.discard(filepath)

        return os.path.exists(filepath) == False

    def _background_cleanup(self):
        """后台清理任务（仅在专用临时目录模式下运行）"""
        if self.temp_dir == ".":
            return  # 当前工作目录模式下不运行后台清理

        while True:
            try:
                time.sleep(self.cleanup_interval)
                self._cleanup_old_files()
            except Exception as e:
                logger.error(f"Background cleanup error: {str(e)}")

    def _cleanup_old_files(self):
        """清理过期文件"""
        if self.temp_dir == ".":
            return  # 当前工作目录模式下不运行后台清理

        current_time = time.time()
        cleanup_count = 0

        try:
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)

                # 跳过目录
                if not os.path.isfile(filepath):
                    continue

                # 检查文件年龄
                file_age = current_time - os.path.getmtime(filepath)

                # 清理过期文件
                if file_age > self.max_file_age:
                    if self.cleanup_file(filepath):
                        cleanup_count += 1

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态信息"""
        registered_count = len(self._registered_files)

        # 如果使用专用临时目录，统计文件信息
        total_files = 0
        total_size = 0
        if self.temp_dir != ".":
            try:
                for filename in os.listdir(self.temp_dir):
                    filepath = os.path.join(self.temp_dir, filename)
                    if os.path.isfile(filepath):
                        total_files += 1
                        total_size += os.path.getsize(filepath)
            except Exception:
                pass

        return {
            "temp_directory": self.temp_dir,
            "registered_files": registered_count,
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2) if total_size > 0 else 0,
            "max_file_age_hours": self.max_file_age / 3600,
            "cleanup_interval_minutes": self.cleanup_interval / 60,
            "background_cleanup_enabled": self.temp_dir != "."
        }

    def cleanup_all(self):
        """清理所有注册的临时文件"""
        cleanup_count = 0
        files_to_cleanup = list(self._registered_files)  # 复制列表避免并发修改

        for filepath in files_to_cleanup:
            if self.cleanup_file(filepath):
                cleanup_count += 1

# 全局临时文件管理器实例（延迟初始化）
temp_file_manager = None

def get_temp_file_manager() -> TempFileManager:
    """获取全局临时文件管理器实例（单例）"""
    global temp_file_manager
    if temp_file_manager is None:
        temp_file_manager = TempFileManager()
    return temp_file_manager

# 便捷函数
def create_temp_audio_file() -> str:
    """创建临时音频文件"""
    return get_temp_file_manager().create_temp_file(suffix=".mp3", prefix="temp_")

def create_temp_stream_file() -> str:
    """创建临时流式音频文件（数字人TTS用）"""
    return get_temp_file_manager().create_temp_file(suffix=".mp3", prefix="stream_")

def create_temp_voice_output_file() -> str:
    """创建临时语音输出文件（数字人TTS用）"""
    return get_temp_file_manager().create_temp_file(suffix=".mp3", prefix="voice_output_")

def register_existing_temp_file(filepath: str):
    """
    注册现有的临时文件

    Args:
        filepath: 现有临时文件路径
    """
    get_temp_file_manager().register_temp_file(filepath)