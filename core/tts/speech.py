import os
import time
import uuid
from fastapi import Request, Header, HTTPException
from edge_tts import Communicate
from core.auth.model_auth import verify_token
from core.model_manager import ModelManager
from core.tts.file import file_response_with_cleanup
from utils.content_handle.filter import filter_special_chars
import logging

logger = logging.getLogger(__name__)

async def create_speech(
    request: Request,
    authorization: str = Header(None),
):
    """根据输入文本生成语音文件"""
    await verify_token(authorization)
    start_time = time.time()
    output_file = None
    
    try:
        data = await request.json()
        text = data.get("input", "")
        voice = data.get("voice", "zh-CN-XiaoyiNeural")
        
        text = filter_special_chars(text)
        
        if not any(v["ShortName"] == voice for v in ModelManager.get_voices()):
            raise HTTPException(status_code=400, detail=f"Voice {voice} not available")

        if not text:
            # 输入为空时生成一个静默的音频文件
            output_file = f"temp_{uuid.uuid4().hex}.mp3"
            with open(output_file, 'wb') as f:
                f.write(b'')  # 写入空内容
        else:
            output_file = f"temp_{uuid.uuid4().hex}.mp3"
            communicate = Communicate(text, voice)
            await communicate.save(output_file)

        if not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Audio file creation failed")
            
        return file_response_with_cleanup(
            output_file,
            media_type="audio/mpeg",
            filename="speech.mp3",
            cleanup_file=output_file
        )
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        raise HTTPException(status_code=500, detail=str(e))
