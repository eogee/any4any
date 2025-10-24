import os
import torch
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8888))
    RELOAD = os.getenv("RELOAD", "False").lower() == "false"                        # 是否自动重启，多进程及生成环境下不建议启用
    DEV_MODE = os.getenv("DEV_MODE", "False").lower() == "false"                    # 是否启用开发模式，开发模式下，控制台可以显示更多日志内容
    PREVIEW_MODE = os.getenv("PREVIEW_MODE", "True").lower() == "true"              # 是否启用预览模式，预览模式下，大模型响应内容需要人为确认或等待超时自动响应
    PREVIEW_TIMEOUT = int(os.getenv("PREVIEW_TIMEOUT", "60"))                       # 预览超时时间（秒），默认1分钟
    DELAY_MODE = os.getenv("DELAY_MODE", "False").lower() == "true"                 # 是否启用延迟模式，延迟模式下，系统会累积用户消息并延迟处理
    DELAY_TIME = int(os.getenv("DELAY_TIME", "3"))                                  # 延迟处理时间（秒），默认3秒，用户停止发送消息超过此时间才处理
    KNOWLEDGE_BASE_ENABLED = os.getenv("KNOWLEDGE_BASE_ENABLED", "False").lower() == "true" # 是否启用知识库，启用后会根据用户问题从知识库中提取相关内容

    # MCP配置
    MCP_PORT = int(os.getenv("MCP_PORT", 9999))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")
    
    # 认证配置
    API_KEY = os.getenv("API_KEY", "EMPTY")
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "1800"))                     # 会话有效期，单位为秒，默认为30分钟
    MAX_CONVERSATION_MESSAGES = int(os.getenv("MAX_CONVERSATION_MESSAGES", "20"))          # 最大对话轮次（消息数量）
    MAX_CONVERSATION_TOKENS = int(os.getenv("MAX_CONVERSATION_TOKENS", "8000"))            # 最大对话token数估算
    ENABLE_CONVERSATION_TRUNCATION = os.getenv("ENABLE_CONVERSATION_TRUNCATION", "True").lower() == "true"  # 是否启用对话截断
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    EDGE_TTS_ENABLED = os.getenv("EDGE_TTS_ENABLED", "False").lower() == "true"  # 是否启用edge-tts
    EDGE_DEFAULT_VOICE = os.getenv("EDGE_DEFAULT_VOICE", "zh-CN-XiaoyiNeural")

    # 模型按需加载配置 (默认不加载，只在首次调用时加载)
    INDEX_TTS_MODEL_ENABLED = os.getenv("INDEX_TTS_MODEL_ENABLED", "False").lower() == "true"  # 是否启用IndexTTS-1.5模型
    ASR_MODEL_ENABLED = os.getenv("ASR_MODEL_ENABLED", "False").lower() == "true"           # 是否启用ASR模型
    RERANK_MODEL_ENABLED = os.getenv("RERANK_MODEL_ENABLED", "False").lower() == "true"     # 是否启用Rerank模型
    EMBEDDING_MODEL_ENABLED = os.getenv("EMBEDDING_MODEL_ENABLED", "False").lower() == "true" # 是否启用Embedding模型
    LLM_MODEL_ENABLED = os.getenv("LLM_MODEL_ENABLED", "False").lower() == "true"           # 是否启用LLM模型

    # 模型路径配置 (按需加载的模型路径)
    INDEX_TTS_MODEL_DIR = os.getenv("INDEX_TTS_MODEL_DIR", "/mnt/c/models/IndexTTS-1.5")
    ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", "/mnt/c/models/SenseVoiceSmall")
    RERANK_MODEL_DIR = os.getenv("RERANK_MODEL_DIR", "/mnt/c/models/bge-reranker-base")
    EMBEDDING_MODEL_DIR = os.getenv("EMBEDDING_MODEL_DIR", "/mnt/c/models/bge-small-zh-v1.5")
    LLM_MODEL_DIR = os.getenv("LLM_MODEL_DIR", "/mnt/c/models/Qwen3-1.7B")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-1.7B")
    NO_THINK = os.getenv("NO_THINK", "True").lower() == "true"
    ASR_PROMPT = os.getenv("ASR_PROMPT", "")
     
    # LLM模型加载配置
    TRUST_REMOTE_CODE = os.getenv("TRUST_REMOTE_CODE", "True").lower() == "true"    # 是否信任远程代码
    USE_HALF_PRECISION = os.getenv("USE_HALF_PRECISION", "True").lower() == "true"  # 是否使用半精度
    LOW_CPU_MEM_USAGE = os.getenv("LOW_CPU_MEM_USAGE", "True").lower() == "true"    # 是否使用低CPU内存
    TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "False").lower() == "true" # 是否启用多线程分词
    
    # LLM模型生成参数配置
    MAX_LENGTH = int(os.getenv("MAX_LENGTH", "4096"))                               # 最大生成长度
    NUM_RETURN_SEQUENCES = int(os.getenv("NUM_RETURN_SEQUENCES", "1"))              # 生成序列数量
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))                            # 温度参数，控制生成的随机性
    TOP_P = float(os.getenv("TOP_P", "0.9"))                                        # Top-p采样参数，控制生成的多样性
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.1"))              # 重复惩罚参数，控制生成的多样性
    LLM_PROMPT = os.getenv("LLM_PROMPT", "")                                        # LLM模型提示词
    
    # EMBEDDING模型配置
    TOP_K = int(os.getenv("TOP_K", "3"))                                            # 取前k个最相似的向量
    VECTOR_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/vector_db") # 向量数据库路径
    DOCS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/docs")           # 文档路径
    DOC_CHUNK_SIZE = int(os.getenv("DOC_CHUNK_SIZE", "500"))                        # 文档处理器文本分块大小
    DOC_CHUNK_OVERLAP = int(os.getenv("DOC_CHUNK_OVERLAP", "50"))                   # 文档处理器文本分块重叠大小
    SUPPORTED_FILE_TYPES = ['.pdf', '.docx', '.txt']                                # 支持的文件类型
    
    # RERANK模型配置
    RERANK_ENABLED = os.getenv("RERANK_ENABLED", "True").lower() == "true"          # 是否启用重排序
    RERANK_CANDIDATE_FACTOR = int(os.getenv("RERANK_CANDIDATE_FACTOR", "10"))       # 重排序候选文档倍数
    RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "16"))                   # 重排序批处理大小

    # IndexTTS-1.5引擎配置
    INDEX_TTS_ENABLED = os.getenv("INDEX_TTS_ENABLED", "False").lower() == "true"   # 是否启用IndexTTS-1.5引擎
    INDEX_TTS_DEVICE = os.getenv("INDEX_TTS_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    INDEX_TTS_MAX_WORKERS = int(os.getenv("INDEX_TTS_MAX_WORKERS", "2"))            # IndexTTS-1.5最大并发数
    INDEX_TTS_TIMEOUT = int(os.getenv("INDEX_TTS_TIMEOUT", "60"))                   # IndexTTS-1.5超时时间，单位为秒
    INDEX_TTS_SUPPORTED_VOICES = ["default"]                                        # IndexTTS-1.5支持的语音列表
    
    # MySQL数据库配置
    MYSQL_HOST = os.getenv("MYSQL_HOST", "172.21.48.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "any4any")

    # 数据库功能配置
    QUERY_CLEANING = os.getenv("QUERY_CLEANING", "True").lower() == "true"          # 是否启用数据库查询清理功能

    # 工具系统配置
    TOOLS_ENABLED = os.getenv("TOOLS_ENABLED", "True").lower() == "true"
    TOOLS_DEBUG = os.getenv("TOOLS_DEBUG", "False").lower() == "true"
    TOOLS_TIMEOUT = int(os.getenv("TOOLS_TIMEOUT", "30"))  # 工具执行超时时间（秒）

    # SQL数据库配置 (复用现有MySQL配置)
    SQL_DB_TYPE = os.getenv("SQL_DB_TYPE", "mysql")
    SQL_DB_HOST = MYSQL_HOST  # 复用现有MySQL配置
    SQL_DB_PORT = MYSQL_PORT  # 复用现有MySQL配置
    SQL_DB_USERNAME = MYSQL_USER  # 复用现有MySQL配置
    SQL_DB_PASSWORD = MYSQL_PASSWORD  # 复用现有MySQL配置
    SQL_DB_DATABASE = MYSQL_DATABASE  # 复用现有MySQL配置

    # 工具服务器配置
    TOOLS_ENABLED = os.getenv("TOOLS_ENABLED", "True").lower() == "true"
    TOOLS_DEBUG = os.getenv("TOOLS_DEBUG", "False").lower() == "true"
    TOOLS_TIMEOUT = int(os.getenv("TOOLS_TIMEOUT", "30"))  # 工具执行超时时间（秒）
    
    # 钉钉配置
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    ROBOT_CODE = os.getenv("ROBOT_CODE", "")
    DINGTALK_PORT = os.getenv("DINGTALK_PORT", "6666")

    # 确保目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)
    os.makedirs(LLM_MODEL_DIR, exist_ok=True)
    os.makedirs(EMBEDDING_MODEL_DIR, exist_ok=True)
    os.makedirs(VECTOR_DB_PATH, exist_ok=True)
    os.makedirs(DOCS_PATH, exist_ok=True)
    os.makedirs(INDEX_TTS_MODEL_DIR, exist_ok=True)