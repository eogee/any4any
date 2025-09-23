"""
Any4Any 应用的生命周期管理器
"""

import logging
from fastapi import FastAPI
from core.model_manager import ModelManager

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """模型启动加载初始化和资源清理"""
    await ModelManager.initialize()
    yield
    
    logger.info("Application shutting down...")
    
    """应用关闭时清理所有模型资源"""
    llm_service = ModelManager.get_llm_service()
    if llm_service and hasattr(llm_service, 'cleanup'):
        llm_service.cleanup()

    ModelManager.cleanup()
    logger.info("Source cleanup completed")