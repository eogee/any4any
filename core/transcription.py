from fastapi import UploadFile, File, Form, Header, HTTPException
from typing import Optional
import re
import time
from io import BytesIO
import torchaudio
from config import Config
from core.auth import verify_token
from core.models import ModelManager
from funasr.utils.postprocess_utils import rich_transcription_postprocess
import logging

logger = logging.getLogger(__name__)

async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0),
    authorization: str = Header(None),
):
    """Transcribes audio into the input language."""
    await verify_token(authorization)
    
    start_time = time.time()
    try:
        audio_data = await file.read()
        data, fs = torchaudio.load(BytesIO(audio_data))
        data = data.mean(0)
        duration = len(data)/fs
        
        m, kwargs = ModelManager.get_asr_model()
        res = m.inference(
            data_in=[data],
            language=language.lower() if language else "auto",
            use_itn=False,
            ban_emo_unk=False,
            key=["openai_api_request"],
            fs=fs,
            **kwargs,
        )

        if not res or not res[0]:
            raise HTTPException(status_code=500, detail="Empty transcription result")

        raw_text = res[0][0]["text"]
        final_text = rich_transcription_postprocess(re.sub(r"<\|.*?\|>", "", raw_text))

        if Config.PROMPT is not None and Config.PROMPT != "":
            final_text = f"{final_text}<div style='display:none'>{Config.PROMPT}</div>"

        if Config.NO_THINK:
            final_text = f"{final_text}<div style='display:none'>/no_think</div>"
        
        logger.info(
            f"[ASR] Time: {time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Audio: {file.filename} | "
            f"Duration: {duration:.2f}s | "
            f"Processing Time: {time.time()-start_time:.2f}s | "
            f"Language: {language or 'auto'} | "
            f"Result: {final_text}"
        )

        if response_format == "text":
            return final_text
        return {"text": final_text}

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
