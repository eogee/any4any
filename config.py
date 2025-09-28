import os
import torch
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Config:
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8888))
    RELOAD = os.getenv("RELOAD", "False").lower() == "false"                        # 是否自动重启，多进程及生成环境下不建议启用
    DEV_MODE = os.getenv("DEV_MODE", "False").lower() == "false"                    # 是否启用开发模式，开发模式下，控制台可以显示更多日志内容
    PREVIEW_MODE = os.getenv("PREVIEW_MODE", "True").lower() == "true"              # 是否启用预览模式，预览模式下，大模型响应内容需要人为确认或等待超时自动响应
    PREVIEW_TIMEOUT = int(os.getenv("PREVIEW_TIMEOUT", "60"))                       # 预览超时时间（秒），默认1分钟

    # MCP配置
    MCP_PORT = int(os.getenv("MCP_PORT", 9999))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")
    
    # 认证配置
    API_KEY = os.getenv("API_KEY", "EMPTY")
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "1800"))                     # 会话有效期，单位为秒，默认为30分钟
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", "/mnt/c/models/SenseVoiceSmall")
    RERANK_MODEL_DIR = os.getenv("RERANK_MODEL_DIR", "/mnt/c/models/bge-reranker-base")
    LLM_MODEL_DIR = os.getenv("LLM_MODEL_DIR", "/mnt/c/models/Qwen3-1.7B")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-1.7B")
    NO_THINK = os.getenv("NO_THINK", "True").lower() == "true"
    ASR_PROMPT = os.getenv("ASR_PROMPT", "")
    LLM_PROMPT = os.getenv("LLM_PROMPT", "")
     
    # LLM模型加载配置
    TRUST_REMOTE_CODE = os.getenv("TRUST_REMOTE_CODE", "True").lower() == "true"    # 是否信任远程代码
    USE_HALF_PRECISION = os.getenv("USE_HALF_PRECISION", "True").lower() == "true"  # 是否使用半精度
    LOW_CPU_MEM_USAGE = os.getenv("LOW_CPU_MEM_USAGE", "True").lower() == "true"    # 是否使用低CPU内存
    TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "False").lower() == "true"      # 是否启用多线程分词

    # LLM模型生成参数配置
    MAX_LENGTH = int(os.getenv("MAX_LENGTH", "4096"))                               # 最大生成长度
    NUM_RETURN_SEQUENCES = int(os.getenv("NUM_RETURN_SEQUENCES", "1"))              # 生成序列数量
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))                            # 温度参数，控制生成的随机性
    TOP_P = float(os.getenv("TOP_P", "0.9"))                                        # Top-p采样参数，控制生成的多样性
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.1"))              # 重复惩罚参数，控制生成的多样性    
    
    # MySQL数据库配置
    MYSQL_HOST = os.getenv("MYSQL_HOST", "172.21.48.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "any4any")

    # 数据库功能配置
    QUERY_CLEANING = os.getenv("QUERY_CLEANING", "True").lower() == "true"          # 是否启用数据库查询清理功能
    
    # 文本分块配置-知识库文本处理
    DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", 2000))
    DEFAULT_OVERLAP = int(os.getenv("DEFAULT_OVERLAP", 200))
    
    # 确保模型目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)
    os.makedirs(LLM_MODEL_DIR, exist_ok=True)
    
    # 钉钉配置
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    ROBOT_CODE = os.getenv("ROBOT_CODE", "")
    DINGTALK_PORT = os.getenv("DINGTALK_PORT", "6666")