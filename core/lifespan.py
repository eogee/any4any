from fastapi import FastAPI
from core.models import ModelManager
import logging

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """模型启动加载初始化"""
    await ModelManager.initialize()
    yield
    # Cleanup on shutdown if needed
