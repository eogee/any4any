import logging
import os
from fastapi import FastAPI
from core.model_manager import ModelManager
from config import Config

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """模型启动加载初始化和资源清理"""
    # 获取当前进程端口
    current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
    
    # 设置明确的加载LLM条件：只有主FastAPI进程(端口8888)才加载
    # 避免其他进程重复加载模型
    load_llm = current_port == str(Config.PORT) and current_port == '8888'  # 硬编码确认
    
    # 添加额外日志信息便于调试
    logger.info(f"Lifespan init - Process: {os.getpid()}, Port: {current_port}, Load LLM: {load_llm}")
    
    # 调用初始化方法
    await ModelManager.initialize(load_llm=load_llm)
    
    # 添加预览确认回调注册
    if Config.PREVIEW_MODE:
        from core.dingtalk import message_manager
        message_manager.register_preview_confirm_callback()
        logger.info("Preview confirm callback registered during startup")
    
    yield
    
    logger.info("Application shutting down...")
    
    """应用关闭时清理所有模型资源"""
    llm_service = ModelManager.get_llm_service()
    if llm_service and hasattr(llm_service, 'cleanup'):
        llm_service.cleanup()

    ModelManager.cleanup()
    logger.info("Source cleanup completed")