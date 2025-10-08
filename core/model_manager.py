import logging
import time
import multiprocessing 
import os
import gc
from typing import Optional
from config import Config
from fastapi import Header, HTTPException
from edge_tts import VoicesManager
from FlagEmbedding import FlagReranker
from core.auth.model_auth import verify_token
from core.chat.llm import get_llm_service
from core.tts.index_tts_engine import IndexTTSEngine
from utils.funasr.model import SenseVoiceSmall

try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

os.environ['TOKENIZERS_PARALLELISM'] = 'true' if Config.TOKENIZERS_PARALLELISM else 'false'

logger = logging.getLogger(__name__)

class ModelManager:
    """模型管理器-用于初始化所有模型和资源"""
    _instance = None
    m = None
    kwargs = None
    reranker = None
    available_voices = []
    llm_service = None
    embedding_model = None
    embedding_tokenizer = None
    index_tts_engine = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls, load_llm=True, load_asr=True, load_reranker=True, load_tts=True, load_embedding=True, load_index_tts=True):
        """初始化模型和声音列表
        
        Args:
            load_llm: 是否加载LLM模型
            load_asr: 是否加载ASR模型
            load_reranker: 是否加载重排序模型
            load_tts: 是否加载TTS声音列表
            load_embedding: 是否加载嵌入模型
            load_index_tts: 是否加载IndexTTS-1.5引擎
        """
        try:
            if not hasattr(cls, '_initialized'):
                cls._initialized = False
                
            if cls._initialized:
                logger.info("Models already initialized")
                return

            if load_asr and not cls.m:
                logger.info(f"Loading ASR model...")
                cls.m, cls.kwargs = SenseVoiceSmall.from_pretrained(
                    model_dir=Config.ASR_MODEL_DIR,
                    device=Config.DEVICE
                )
                cls.m.eval()
                logger.info("ASR model loaded")

            if load_tts and not cls.available_voices:
                logger.info("Loading voices...")
                voices_manager = await VoicesManager.create()
                cls.available_voices = voices_manager.voices
                logger.info(f"Loaded {len(cls.available_voices)} voices")

            if load_index_tts and Config.INDEX_TTS_ENABLED and not cls.index_tts_engine:
                try:
                    logger.info("Loading IndexTTS-1.5...")

                    cls.index_tts_engine = IndexTTSEngine.get_instance({
                        'model_path': Config.INDEX_TTS_MODEL_DIR,
                        'device': Config.INDEX_TTS_DEVICE
                    })
                    
                    # 验证初始化状态
                    if cls.index_tts_engine.is_initialized():
                        logger.info("IndexTTS-1.5 loaded")
                    else:
                        logger.warning("IndexTTS-1.5 loaded but not initialized properly")
                except Exception as e:
                    logger.error(f"Failed to load IndexTTS-1.5: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    cls.index_tts_engine = None

            if load_reranker and not cls.reranker:
                logger.info("Loading reranker model...")
                cls.reranker = FlagReranker(Config.RERANK_MODEL_DIR, use_fp16=False)
                logger.info("Reranker model loaded")

            if load_embedding and not cls.embedding_model:
                logger.info(f"Loading embedding model...")
                from transformers import AutoTokenizer, AutoModel
                try:
                    cls.embedding_tokenizer = AutoTokenizer.from_pretrained(Config.EMBEDDING_MODEL_DIR)
                    cls.embedding_model = AutoModel.from_pretrained(Config.EMBEDDING_MODEL_DIR)
                    logger.info("Embedding model loaded")
                except Exception as e:
                    logger.error(f"Failed to load embedding model: {str(e)}")

            if load_llm and not cls.llm_service:
                logger.info("Loading LLM model...")
                cls.llm_service = get_llm_service()
                init_success = await cls.llm_service.initialize_model()
                if init_success:
                    logger.info(f"LLM model loaded...")
                else:
                    logger.error(f"Failed to load LLM model from: {Config.LLM_MODEL_DIR}")
            elif not load_llm:
                logger.info("Skipping LLM model loading")
                
            cls._initialized = True
            logger.info("All models initialized")

        except Exception as e:
            logger.error(f"Model initialization failed: {str(e)}")
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
    def get_embedding_model(cls):
        return cls.embedding_model, cls.embedding_tokenizer
    
    @classmethod
    def get_index_tts_engine(cls):
        return cls.index_tts_engine

    @classmethod
    def cleanup(cls):
        """清理所有模型资源"""
        logger.info("Cleaning up model resources...")
        
        if cls.llm_service is not None:
            try:
                if hasattr(cls.llm_service, 'cleanup'):
                    cls.llm_service.cleanup()
                cls.llm_service = None
            except Exception as e:
                logger.error(f"Error cleaning LLM service: {str(e)}")

        if cls.m is not None:
            if hasattr(cls.m, 'to'):
                try:
                    cls.m.to('cpu')
                except Exception as e:
                    logger.error(f"Failed to move ASR model to CPU: {str(e)}")
            cls.m = None
        cls.kwargs = None

        cls.reranker = None
        cls.available_voices = []
        
        if cls.embedding_model is not None:
            if hasattr(cls.embedding_model, 'to'):
                try:
                    cls.embedding_model.to('cpu')
                except Exception as e:
                    logger.error(f"Failed to move embedding model to CPU: {str(e)}")
            cls.embedding_model = None
        cls.embedding_tokenizer = None

        if cls.index_tts_engine is not None:
            try:
                IndexTTSEngine.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning IndexTTS-1.5: {str(e)}")
            cls.index_tts_engine = None
        
        gc.collect()
        logger.info("Model cleanup completed")

async def list_models(authorization: Optional[str] = Header(None)):
    """列出可用模型"""
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
    
    llm_model_name = Config.LLM_MODEL_NAME
    models.append({
        "id": llm_model_name,
        "object": "model",
        "owned_by": "your-organization",
        "permissions": ["generate"]
    })
    
    return {"data": models}

async def health_check():
    """检查模型服务健康状态"""
    tts_status = "available" if ModelManager.get_voices() else "unavailable"
    index_tts_status = "loaded" if (ModelManager.get_index_tts_engine() and \
                                   ModelManager.get_index_tts_engine().is_initialized()) else "unloaded"
    
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": {
            "asr": "loaded" if ModelManager.m is not None else "unloaded",
            "reranker": "loaded" if ModelManager.reranker is not None else "unloaded",
            "tts": tts_status,
            "llm": "loaded" if ModelManager.llm_service is not None else "unloaded",
            "embedding": "loaded" if ModelManager.embedding_model is not None else "unloaded",
            "index_tts": index_tts_status
        }
    }