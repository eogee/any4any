from fastapi import FastAPI
from core.models import ModelManager
import logging

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """Initialize models on startup"""
    await ModelManager.initialize()
    yield
    # Cleanup on shutdown if needed
