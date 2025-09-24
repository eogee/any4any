import os
import torch
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Config:
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8888))
    RELOAD = os.getenv("RELOAD", "False").lower() == "false"
    DEV_MODE = os.getenv("DEV_MODE", "False").lower() == "false"
    ENABLE_AUTH = os.getenv("ENABLE_AUTH", "False").lower() == "False"
    PREVIEW_MODE = os.getenv("PREVIEW_MODE", "True").lower() == "true" 

    # MCP配置
    MCP_PORT = int(os.getenv("MCP_PORT", 9999))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")
    
    # 认证配置
    API_KEY = os.getenv("API_KEY", "EMPTY")
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "1800"))  # 会话有效期，单位为秒，默认为30分钟
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", "/mnt/c/models/SenseVoiceSmall")
    RERANK_MODEL_DIR = os.getenv("RERANK_MODEL_DIR", "/mnt/c/models/bge-reranker-base")
    LLM_MODEL_DIR = os.getenv("LLM_MODEL_DIR", "/mnt/c/models/Qwen3-1.7B")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-1.7B")
    
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
    
    # 生成参数配置
    MAX_LENGTH = int(os.getenv("MAX_LENGTH", "4096")) 
    NUM_RETURN_SEQUENCES = int(os.getenv("NUM_RETURN_SEQUENCES", "1")) 
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7")) 
    TOP_P = float(os.getenv("TOP_P", "0.9"))
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.1"))

    # 模型加载配置
    TRUST_REMOTE_CODE = os.getenv("TRUST_REMOTE_CODE", "True").lower() == "true" 
    USE_HALF_PRECISION = os.getenv("USE_HALF_PRECISION", "True").lower() == "true"  # 是否使用半精度
    LOW_CPU_MEM_USAGE = os.getenv("LOW_CPU_MEM_USAGE", "True").lower() == "true"    # 是否使用低CPU内存

    # 预览服务配置
    PREVIEW_TIMEOUT = int(os.getenv("PREVIEW_TIMEOUT", "300"))                      # 预览超时时间（秒），默认5分钟
    CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "3600"))                   # 预览清理间隔（秒），默认1小时
    MAX_PREVIEW_COUNT = int(os.getenv("MAX_PREVIEW_COUNT", "100"))                  # 最大预览数量

    # 分词器配置
    TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "False").lower() == "true"      # 是否启用多线程分词
    
    # 钉钉配置
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    ROBOT_CODE = os.getenv("ROBOT_CODE", "")
    DINGTALK_PORT = os.getenv("DINGTALK_PORT", "6666")