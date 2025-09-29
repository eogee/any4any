import logging
import os
from fastapi import FastAPI
from core.model_manager import ModelManager
from core.chat.conversation_manager import conversation_manager
from core.chat.delay_manager import delay_manager
from config import Config

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
    load_llm = current_port == str(Config.PORT) and current_port == '8888'
    
    logger.info(f"Initializing - PID: {os.getpid()}, Port: {current_port}, Load LLM: {load_llm}")
    
    # 初始化模型管理器
    await ModelManager.initialize(load_llm=load_llm)
    
    # 初始化延迟管理器并设置到会话管理器
    if Config.DELAY_MODE:
        conversation_manager.set_delay_manager(delay_manager)
        logger.info("Delay manager initialized and set to conversation manager")
    
    # 预览模式下注册回调
    if Config.PREVIEW_MODE:
        from core.dingtalk import message_manager
        message_manager.register_preview_confirm_callback()
        logger.info("Preview confirm callback registered")
    
    yield
    
    logger.info("Application shutting down...")
    
    # 清理LLM服务资源
    llm_service = ModelManager.get_llm_service()
    if llm_service and hasattr(llm_service, 'cleanup'):
        llm_service.cleanup()

    # 清理模型管理器资源
    ModelManager.cleanup()
    logger.info("Resource cleanup completed")