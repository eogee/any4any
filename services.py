from fastapi import FastAPI
import os
import re
import asyncio
import uuid
import time
import json
import logging
from typing import Optional, List
from fastapi import HTTPException, Request, Header, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
import torch
import torchaudio
from io import BytesIO
from edge_tts import Communicate, VoicesManager
from model import SenseVoiceSmall
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from FlagEmbedding import FlagReranker
from models import Config, Message, ChatCompletionRequest, SpeechRequest, QADocs

logger = logging.getLogger(__name__)

# --- 全局变量 ---
available_voices = []
reranker = None
m = None
kwargs = None

# --- 认证验证 ---
async def verify_token(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authentication required",
                "message": "Please include your API key in the Authorization header",
                "format": "Bearer YOUR_API_KEY",
                "documentation": "https://example.com/api-docs"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid authorization format",
                "message": "Authorization header must start with 'Bearer '",
                "example": "Bearer abc123def456"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    token = authorization[7:]
    if token != Config.API_KEY:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Invalid API key",
                "message": "The provided API key is not valid",
                "solution": "Check your API key or contact support"
            }
        )

# --- 模型初始化 ---
async def initialize_models():
    """Initialize all models and voice list"""
    global m, kwargs, reranker, available_voices
    
    try:
        # 初始化语音转录模型
        logger.info(f"Loading model from: {Config.MODEL_DIR}")
        logger.info(f"Using device: {Config.DEVICE}")
        m, kwargs = SenseVoiceSmall.from_pretrained(
            model=Config.MODEL_DIR,
            device=Config.DEVICE
        )
        m.eval()
        logger.info("ASR model loaded successfully")

        # 初始化语音列表
        voices_manager = await VoicesManager.create()
        available_voices = voices_manager.voices
        logger.info(f"Loaded {len(available_voices)} available voices")

        # 初始化reranker模型
        reranker = FlagReranker(Config.RERANK_MODEL_PATH, use_fp16=False)
        logger.info("Reranker model loaded successfully")

    except Exception as e:
        logger.error(f"Failed to initialize models: {str(e)}")
        raise RuntimeError(f"Model initialization failed: {str(e)}")

# --- API端点处理函数 ---
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

async def create_speech(
    request: Request,
    authorization: str = Header(None),
):
    """Generates audio from the input text."""
    await verify_token(authorization)
    start_time = time.time()
    output_file = None
    
    try:
        data = await request.json()
        text = data.get("input", "")
        voice = data.get("voice", "zh-CN-XiaoyiNeural")
        
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'<video\b[^>]*>.*?</video>', '', text, flags=re.DOTALL)
        text = re.sub(r'[#*]', '', text)
        
        if not text:
            raise HTTPException(status_code=400, detail="No input text provided")
            
        if not any(v["ShortName"] == voice for v in available_voices):
            raise HTTPException(status_code=400, detail=f"Voice {voice} not available")

        output_file = f"temp_{uuid.uuid4().hex}.mp3"
        communicate = Communicate(text, voice)
        await communicate.save(output_file)

        if not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Audio file creation failed")
            
        return FileResponse(
            output_file,
            media_type="audio/mpeg",
            filename="speech.mp3"
        )

    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        raise HTTPException(status_code=500, detail=str(e))

async def rerank_documents(
    docs: QADocs,
    authorization: str = Header(None)
):
    """Rerank documents based on query"""
    await verify_token(authorization)
    
    try:
        if docs is None or len(docs.documents) == 0:
            return {"results": []}

        pairs = [[docs.query, doc] for doc in docs.documents]
        scores = reranker.compute_score(pairs, normalize=True)
        
        if isinstance(scores, float):
            scores = [scores]
            
        results = []
        for index, score in enumerate(scores):
            results.append({
                "index": index,
                "relevance_score": score,
                "text": docs.documents[index]
            })
        
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Reranking failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Reranking failed")

# --- 辅助端点 ---
async def list_models(authorization: Optional[str] = Header(None)):
    try:
        await verify_token(authorization)
    except HTTPException as e:
        if e.status_code != 401:
            raise e
    
    return {
        "data": [{
            "id": "sensevoice-small",
            "object": "model",
            "owned_by": "your-organization",
            "permissions": ["generate"]
        }]
    }

async def health_check():
    """Check service health status"""
    tts_status = "available" if available_voices else "unavailable"
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": {
            "asr": "loaded" if m is not None else "unloaded",
            "reranker": "loaded" if reranker is not None else "unloaded",
            "tts": tts_status
        }
    }

async def tts_test():
    """Test TTS functionality with a simple phrase"""
    test_text = "这是一个测试语音"
    test_voice = "zh-CN-XiaoyiNeural"
    output_file = f"test_{uuid.uuid4().hex}.mp3"
    
    try:
        if not any(v["ShortName"] == test_voice for v in available_voices):
            return JSONResponse(
                status_code=500,
                content={"error": f"Voice {test_voice} not available"}
            )
        
        communicate = Communicate(test_text, test_voice)
        await communicate.save(output_file)
        
        if not os.path.exists(output_file):
            return JSONResponse(
                status_code=500,
                content={"error": "Audio file not created"}
            )
            
        return FileResponse(
            output_file,
            media_type="audio/mpeg",
            filename="test.mp3"
        )
        
    except Exception as e:
        logger.error(f"TTS test failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

async def public_test():
    """Public test endpoint that doesn't require authentication"""
    return {
        "status": "success",
        "message": "Public endpoint is working",
        "next_steps": {
            "authenticated_endpoints": "Use /api-docs to learn how to authenticate",
            "tts_test": "Try /tts-test after setting up authentication"
        }
    }

async def get_api_docs():
    """Return API documentation"""
    return {
        "authentication": {
            "description": "Most API endpoints require authentication",
            "method": "Bearer token in Authorization header",
            "example": "Authorization: Bearer YOUR_API_KEY",
            "sample_requests": {
                "curl": "curl -X POST http://localhost:8888/v1/audio/speech \\\n-H 'Authorization: Bearer YOUR_API_KEY' \\\n-H 'Content-Type: application/json' \\\n-d '{\"input\":\"Hello world\",\"voice\":\"zh-CN-XiaoyiNeural\"}'",
                "python": """import requests

url = "http://localhost:8888/v1/audio/speech"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "input": "Hello world",
    "voice": "zh-CN-XiaoyiNeural"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())"""
            }
        },
        "endpoints": {
            "/v1/audio/speech": {
                "method": "POST",
                "description": "Convert text to speech",
                "parameters": {
                    "input": "Text to convert to speech",
                    "voice": "Voice to use (default: zh-CN-XiaoyiNeural)"
                },
                "example_request": {
                    "input": "Hello world",
                    "voice": "zh-CN-XiaoyiNeural"
                }
            },
            "/tts-test": {
                "method": "GET",
                "description": "Test TTS functionality (requires auth)"
            },
            "/public-test": {
                "method": "GET",
                "description": "Public test endpoint (no auth required)"
            }
        }
    }

async def lifespan(app: FastAPI):
    """Initialize models on startup"""
    await initialize_models()
    yield
    # Cleanup on shutdown if needed
