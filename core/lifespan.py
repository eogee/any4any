import logging
from fastapi import FastAPI
from core.model_manager import ModelManager

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """模型启动加载初始化和资源清理"""
    await ModelManager.initialize()
    yield
    # 在应用关闭时清理资源，避免信号量泄漏
    logger.info("应用关闭中，开始清理资源...")
    # 清理LLM服务资源
    llm_service = ModelManager.get_llm_service()
    if llm_service and hasattr(llm_service, 'cleanup'):
        llm_service.cleanup()
    # 清理所有模型资源
    ModelManager.cleanup()
    logger.info("资源清理完成")