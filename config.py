import os
import torch
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Config:
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8888))

    # MCP配置
    MCP_PORT = int(os.getenv("MCP_PORT", 9999))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")
    
    # 认证配置
    API_KEY = os.getenv("API_KEY", "EMPTY")
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", "/mnt/c/models/SenseVoiceSmall")
    RERANK_MODEL_DIR = os.getenv("RERANK_MODEL_DIR", "/mnt/c/models/bge-reranker-base")
    
    # MySQL数据库配置
    MYSQL_HOST = os.getenv("MYSQL_HOST", "172.21.48.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "any4any")

    # 功能开关配置
    NO_THINK = os.getenv("NO_THINK", "True").lower() == "true"
    QUERY_CLEANING = os.getenv("QUERY_CLEANING", "True").lower() == "true"
    PROMPT = os.getenv("PROMPT", "")
    
    # 文本分块配置
    DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", 2000))
    DEFAULT_OVERLAP = int(os.getenv("DEFAULT_OVERLAP", 200))
    
    # 确保模型目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)