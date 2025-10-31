from fastapi import HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class VoiceFileService:
    """语音文件服务"""

    @staticmethod
    def serve_voice_file(audio_file: str):
        """提供语音文件访问"""
        try:
            from config import Config
            audio_dir = Path(Config.VOICE_KB_AUDIO_DIR)
            audio_path = audio_dir / audio_file

            if not audio_path.exists():
                logger.error(f"Voice file not found: {audio_path}")
                raise HTTPException(status_code=404, detail="Voice file not found")

            return FileResponse(
                path=audio_path,
                media_type="audio/mpeg",
                filename=audio_file
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to serve voice file: {e}")
            raise HTTPException(status_code=500, detail="Failed to serve voice file")

    @staticmethod
    def get_voice_file_info(audio_file: str):
        """获取语音文件信息"""
        try:
            from config import Config
            import os

            audio_dir = Path(Config.VOICE_KB_AUDIO_DIR)
            audio_path = audio_dir / audio_file

            if not audio_path.exists():
                return {
                    "success": False,
                    "error": "Voice file not found"
                }

            file_stat = os.stat(audio_path)
            return {
                "success": True,
                "file_name": audio_file,
                "file_path": str(audio_path),
                "file_size": file_stat.st_size,
                "exists": True
            }

        except Exception as e:
            logger.error(f"Failed to get voice file info: {e}")
            return {
                "success": False,
                "error": str(e)
            }