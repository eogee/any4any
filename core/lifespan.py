import logging
import os
from fastapi import FastAPI
from core.model_manager import ModelManager
from core.chat.conversation_manager import conversation_manager
from core.chat.delay_manager import delay_manager
from config import Config
from core.embedding.kb_server import initialize_kb_server_after_model

# 全局IndexTTS引擎实例
index_tts_engine_instance = None

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    global index_tts_engine_instance
    
    current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
    load_llm = current_port == str(Config.PORT) and current_port == '8888'
    
    # 初始化模型管理器（根据配置项决定加载哪些模型）
    await ModelManager.initialize(
        load_llm=load_llm and Config.LLM_MODEL_ENABLED,
        load_asr=Config.ASR_MODEL_ENABLED,
        load_reranker=Config.RERANK_MODEL_ENABLED,
        load_tts=Config.EDGE_TTS_ENABLED,
        load_embedding=Config.EMBEDDING_MODEL_ENABLED,
        load_index_tts=Config.INDEX_TTS_MODEL_ENABLED
    )
    
    # 初始化知识库服务
    if Config.KNOWLEDGE_BASE_ENABLED:
        initialize_kb_server_after_model()
        logger.info("KnowledgeBaseServer initialization triggered after ModelManager")
    
    # 初始化延迟管理器并设置到会话管理器
    if Config.DELAY_MODE:
        conversation_manager.set_delay_manager(delay_manager)
        logger.info("Delay manager initialized and set to conversation manager")
    
    # 预览模式下注册回调
    if Config.PREVIEW_MODE:
        from core.dingtalk import message_manager
        message_manager.register_preview_confirm_callback()
        logger.info("Preview confirm callback registered")

    # 初始化NL2SQL工具的示例数据
    try:
        if getattr(Config, 'TOOLS_ENABLED', False):
            from core.tools.nl2sql.table_info import get_table_manager
            table_manager = get_table_manager()
            # 创建示例表（如果需要）
            logger.info("NL2SQL table manager initialized")
    except ImportError as e:
        logger.warning(f"NL2SQL table manager initialization skipped, module not available: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize NL2SQL table manager: {e}")
    
    yield
    
    logger.info("Application shutting down...")
    
    # 清理IndexTTS-1.5引擎资源
    if Config.INDEX_TTS_ENABLED:
        try:
            from core.tts.index_tts_engine import IndexTTSEngine
            IndexTTSEngine.cleanup()
            index_tts_engine_instance = None
            logger.info("IndexTTS-1.5 engine cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up IndexTTS-1.5 engine: {str(e)}")
    
    # 清理LLM服务资源
    llm_service = ModelManager.get_llm_service()
    if llm_service and hasattr(llm_service, 'cleanup'):
        llm_service.cleanup()

    # 清理模型管理器资源
    ModelManager.cleanup()
    logger.info("Resource cleanup completed")