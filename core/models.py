from fastapi import FastAPI, Header, HTTPException
from typing import Optional
from config import Config
from model import SenseVoiceSmall
from edge_tts import VoicesManager
from FlagEmbedding import FlagReranker
import logging
import time

logger = logging.getLogger(__name__)

class ModelManager:
    _instance = None
    m = None
    kwargs = None
    reranker = None
    available_voices = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls):
        """初始化所有模型和声音列表"""
        try:
            # Initialize ASR model
            logger.info(f"Loading model from: {Config.ASR_MODEL_DIR}")
            logger.info(f"Using device: {Config.DEVICE}")
            cls.m, cls.kwargs = SenseVoiceSmall.from_pretrained(
                model=Config.ASR_MODEL_DIR,
                device=Config.DEVICE
            )
            cls.m.eval()
            logger.info("ASR model loaded successfully")

            # Initialize voice list
            voices_manager = await VoicesManager.create()
            cls.available_voices = voices_manager.voices
            logger.info(f"Loaded {len(cls.available_voices)} available voices")

            # Initialize reranker model
            cls.reranker = FlagReranker(Config.RERANK_MODEL_DIR, use_fp16=False)
            logger.info("Reranker model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize models: {str(e)}")
            raise RuntimeError(f"Model initialization failed: {str(e)}")

    @classmethod
    def get_asr_model(cls):
        return cls.m, cls.kwargs

    @classmethod
    def get_reranker(cls):
        return cls.reranker

    @classmethod
    def get_voices(cls):
        return cls.available_voices

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
    tts_status = "available" if ModelManager.get_voices() else "unavailable"
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": {
            "asr": "loaded" if ModelManager.m is not None else "unloaded",
            "reranker": "loaded" if ModelManager.reranker is not None else "unloaded",
            "tts": tts_status
        }
    }
