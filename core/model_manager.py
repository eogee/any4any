import logging
import time
import multiprocessing 
import os
import logging
import gc
from typing import Optional
from config import Config
from utils.funasr.model import SenseVoiceSmall
from fastapi import Header, HTTPException
from edge_tts import VoicesManager
from FlagEmbedding import FlagReranker
from core.auth import verify_token
from core.chat.llm import get_llm_service

try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

# 设置环境变量避免多进程问题
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

logger = logging.getLogger(__name__)

class ModelManager:
    _instance = None
    m = None
    kwargs = None
    reranker = None
    available_voices = []
    llm_service = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls):
        """初始化所有模型和声音列表"""
        try:

            logger.info(f"Loading model from: {Config.ASR_MODEL_DIR}")
            logger.info(f"Using device: {Config.DEVICE}")
            logger.info("Starting to load ASR model...")
            
            cls.m, cls.kwargs = SenseVoiceSmall.from_pretrained(
                model_dir=Config.ASR_MODEL_DIR,
                device=Config.DEVICE
            )
            cls.m.eval()
            logger.info("ASR model loaded successfully")

            logger.info("Starting to load voices...")
            voices_manager = await VoicesManager.create()
            cls.available_voices = voices_manager.voices
            logger.info(f"Loaded {len(cls.available_voices)} available voices")

            logger.info("Starting to load reranker model...")
            cls.reranker = FlagReranker(Config.RERANK_MODEL_DIR, use_fp16=False)
            logger.info("Reranker model loaded successfully")

            logger.info("Starting to load LLM model...")
            cls.llm_service = get_llm_service()
            logger.info(f"LLM model loaded successfully from: {Config.LLM_MODEL_DIR}")

            logger.info("All models initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize models: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
        
    @classmethod
    def get_llm_service(cls):
        return cls.llm_service

    @classmethod
    def cleanup(cls):
        """清理所有模型资源"""
        logger.info("Starting to clean up model resources...")

        if cls.m is not None:
            logger.info("Starting to clean up ASR model resources...")
            # 如果模型在 GPU 上，尝试将其移回 CPU 以释放 GPU 内存
            if hasattr(cls.m, 'to'):
                try:
                    cls.m.to('cpu')
                except Exception as e:
                    logger.error(f"Failed to move ASR model to CPU: {str(e)}")
            cls.m = None
            logger.info("ASR model reference deleted")
        cls.kwargs = None

        cls.reranker = None
        logger.info("Reranker model reference deleted")
        
        cls.available_voices = []
        logger.info("TTS voices list cleaned up")

        if hasattr(cls, 'llm_service') and cls.llm_service is not None:
            try:
                if hasattr(cls.llm_service, 'cleanup'):
                    cls.llm_service.cleanup()
                cls.llm_service = None
                logger.info("LLM service resources confirmed cleaned up")
            except Exception as e:
                logger.error(f"Error confirming cleanup of LLM service resources: {str(e)}")
        
        logger.info("Collecting garbage...")
        gc.collect()
        logger.info("Garbage collection completed")
        
        logger.info("All model resources cleaned up")

async def list_models(authorization: Optional[str] = Header(None)):
    try:
        await verify_token(authorization)
    except HTTPException as e:
        if e.status_code != 401:
            raise e
    
    models = [{
        "id": "sensevoice-small",
        "object": "model",
        "owned_by": "your-organization",
        "permissions": ["generate"]
    }]
    
    # 添加LLM模型信息    
    llm_model_name = Config.LLM_MODEL_NAME
    models.append({
        "id": llm_model_name,
        "object": "model",
        "owned_by": "your-organization",
        "permissions": ["generate"]
    })
    
    return {
        "data": models
    }

async def health_check():
    """检查模型服务健康状态"""
    tts_status = "available" if ModelManager.get_voices() else "unavailable"
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": {
            "asr": "loaded" if ModelManager.m is not None else "unloaded",
            "reranker": "loaded" if ModelManager.reranker is not None else "unloaded",
            "tts": tts_status,
            "llm": "loaded" if ModelManager.llm_service is not None else "unloaded"
        }
    }