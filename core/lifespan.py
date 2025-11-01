import logging
import os
from fastapi import FastAPI
from core.model_manager import ModelManager
from core.chat.conversation_manager import conversation_manager
from core.chat.delay_manager import delay_manager
from config import Config
from core.embedding.kb_server import initialize_kb_server_after_model

# 全局服务器实例
_global_servers = {}

# 全局IndexTTS引擎实例
index_tts_engine_instance = None

logger = logging.getLogger(__name__)

def get_server_instance(server_class, server_name):
    """获取服务器实例的单例"""
    if server_name not in _global_servers:
        _global_servers[server_name] = server_class()
    return _global_servers[server_name]

async def lifespan(app: FastAPI):
    """应用生命周期管理"""
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
    if Config.PREVIEW_MODE and Config.DINGTALK_ENABLED:
        from core.dingtalk import message_manager
        message_manager.register_preview_confirm_callback()
        logger.info("Preview confirm callback registered")

    # 初始化NL2SQL工具的示例数据
    try:
        if getattr(Config, 'TOOLS_ENABLED', False):
            from core.tools.nl2sql.table_info import get_table_manager
            table_manager = get_table_manager()            
            logger.info("NL2SQL tool initialized")
    except ImportError as e:
        logger.warning(f"NL2SQL tool initialization skipped, module not available: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize NL2SQL tool: {e}")

    if current_port != str(Config.MCP_PORT):

        from servers.IndexServer import IndexServer
        from servers.AuthServer import AuthServer
        from servers.ChatServer import ChatServer

        index_server = get_server_instance(IndexServer, "IndexServer")
        index_server.register_routes(app)

        auth_server = get_server_instance(AuthServer, "AuthServer")
        auth_server.register_routes(app)

        chat_server = get_server_instance(ChatServer, "ChatServer")
        chat_server.register_routes(app)

        if Config.ANY4DH_ENABLED:
            try:
                from core.any4dh.any4dh_server import initialize_any4dh, register_any4dh_routes
                from servers.DHServer import DHServer

                opt, model, avatar = initialize_any4dh(Config())

                register_any4dh_routes(app)

                dh_server = get_server_instance(DHServer, "DHServer")
                dh_server.register_routes(app)

            except Exception as e:
                logger.error(f"any4dh server start failed: {e}")

    yield
    
    logger.info("Application shutting down...")
    
    # 清理IndexTTS-1.5引擎资源
    if Config.INDEX_TTS_MODEL_ENABLED:
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