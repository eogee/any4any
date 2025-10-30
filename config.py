import os
import torch
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8888))
    RELOAD = os.getenv("RELOAD", "False").lower() == "false"
    DEV_MODE = os.getenv("DEV_MODE", "False").lower() == "false"
    PREVIEW_MODE = os.getenv("PREVIEW_MODE", "True").lower() == "true"
    PREVIEW_TIMEOUT = int(os.getenv("PREVIEW_TIMEOUT", "60"))
    DELAY_MODE = os.getenv("DELAY_MODE", "False").lower() == "true"
    DELAY_TIME = int(os.getenv("DELAY_TIME", "3"))
    KNOWLEDGE_BASE_ENABLED = os.getenv("KNOWLEDGE_BASE_ENABLED", "False").lower() == "true"

    # MCP配置
    MCP_PORT = int(os.getenv("MCP_PORT", 9999))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")

    # 认证配置
    API_KEY = os.getenv("API_KEY", "EMPTY")
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "1800"))
    MAX_CONVERSATION_MESSAGES = int(os.getenv("MAX_CONVERSATION_MESSAGES", "20"))
    MAX_CONVERSATION_TOKENS = int(os.getenv("MAX_CONVERSATION_TOKENS", "8000"))
    ENABLE_CONVERSATION_TRUNCATION = os.getenv("ENABLE_CONVERSATION_TRUNCATION", "True").lower() == "true"

    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    EDGE_TTS_ENABLED = os.getenv("EDGE_TTS_ENABLED", "False").lower() == "true"
    EDGE_DEFAULT_VOICE = os.getenv("EDGE_DEFAULT_VOICE", "zh-CN-XiaoyiNeural")

    # 模型按需加载配置 (默认不加载，只在首次调用时加载)
    INDEX_TTS_MODEL_ENABLED = os.getenv("INDEX_TTS_MODEL_ENABLED", "False").lower() == "true"
    ASR_MODEL_ENABLED = os.getenv("ASR_MODEL_ENABLED", "False").lower() == "true"
    RERANK_MODEL_ENABLED = os.getenv("RERANK_MODEL_ENABLED", "False").lower() == "true"
    EMBEDDING_MODEL_ENABLED = os.getenv("EMBEDDING_MODEL_ENABLED", "False").lower() == "true"
    LLM_MODEL_ENABLED = os.getenv("LLM_MODEL_ENABLED", "False").lower() == "true"

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
    TRUST_REMOTE_CODE = os.getenv("TRUST_REMOTE_CODE", "True").lower() == "true"
    USE_HALF_PRECISION = os.getenv("USE_HALF_PRECISION", "True").lower() == "true"
    LOW_CPU_MEM_USAGE = os.getenv("LOW_CPU_MEM_USAGE", "True").lower() == "true"
    TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "False").lower() == "true"

    # LLM模型生成参数配置
    MAX_LENGTH = int(os.getenv("MAX_LENGTH", "4096"))
    NUM_RETURN_SEQUENCES = int(os.getenv("NUM_RETURN_SEQUENCES", "1"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    TOP_P = float(os.getenv("TOP_P", "0.9"))
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.1"))
    LLM_PROMPT = os.getenv("LLM_PROMPT", "")

    # EMBEDDING模型配置
    TOP_K = int(os.getenv("TOP_K", "3"))
    VECTOR_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/vector_db")
    DOCS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/docs")
    DOC_CHUNK_SIZE = int(os.getenv("DOC_CHUNK_SIZE", "500"))
    DOC_CHUNK_OVERLAP = int(os.getenv("DOC_CHUNK_OVERLAP", "50"))
    SUPPORTED_FILE_TYPES = ['.pdf', '.docx', '.txt']

    # RERANK模型配置
    RERANK_CANDIDATE_FACTOR = int(os.getenv("RERANK_CANDIDATE_FACTOR", "10"))
    RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "16"))

    # IndexTTS-1.5引擎配置
    INDEX_TTS_FAST_ENABLED = os.getenv("INDEX_TTS_FAST_ENABLED", "False").lower() == "true"
    INDEX_TTS_FAST_MAX_TOKENS = int(os.getenv("INDEX_TTS_FAST_MAX_TOKENS", "50"))
    INDEX_TTS_FAST_BATCH_SIZE = int(os.getenv("INDEX_TTS_FAST_BATCH_SIZE", "16"))
    INDEX_TTS_STREAMING_MIN_SENTENCE_CHARS = int(os.getenv("INDEX_TTS_STREAMING_MIN_SENTENCE_CHARS", "15"))
    INDEX_TTS_DEVICE = os.getenv("INDEX_TTS_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    INDEX_TTS_MAX_WORKERS = int(os.getenv("INDEX_TTS_MAX_WORKERS", "2"))
    INDEX_TTS_TIMEOUT = int(os.getenv("INDEX_TTS_TIMEOUT", "60"))
    INDEX_TTS_SUPPORTED_VOICES = ["default"]
    INDEX_TTS_REFERENCE_AUDIO = os.getenv("INDEX_TTS_REFERENCE_AUDIO", "default.wav")

    # MySQL数据库配置
    MYSQL_HOST = os.getenv("MYSQL_HOST", "172.21.48.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "any4any")

    # 数据库功能配置
    QUERY_CLEANING = os.getenv("QUERY_CLEANING", "True").lower() == "true"

    # 工具系统配置

    # SQL数据库配置 (复用现有MySQL配置)
    SQL_DB_TYPE = os.getenv("SQL_DB_TYPE", "mysql")
    SQL_DB_HOST = MYSQL_HOST
    SQL_DB_PORT = MYSQL_PORT
    SQL_DB_USERNAME = MYSQL_USER
    SQL_DB_PASSWORD = MYSQL_PASSWORD
    SQL_DB_DATABASE = MYSQL_DATABASE

    # 工具服务器配置
    TOOLS_ENABLED = os.getenv("TOOLS_ENABLED", "True").lower() == "true"
    TOOLS_DEBUG = os.getenv("TOOLS_DEBUG", "False").lower() == "true"
    TOOLS_TIMEOUT = int(os.getenv("TOOLS_TIMEOUT", "30"))

    # 钉钉配置
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    ROBOT_CODE = os.getenv("ROBOT_CODE", "")
    DINGTALK_PORT = os.getenv("DINGTALK_PORT", "6666")

    # any4dh 数字人配置
    ANY4DH_ENABLED = os.getenv("ANY4DH_ENABLED", "False").lower() == "true"
    ANY4DH_TRANSPORT = os.getenv("ANY4DH_TRANSPORT", "webrtc")
    ANY4DH_MODEL = os.getenv("ANY4DH_MODEL", "wav2lip")
    ANY4DH_AVATAR_ID = os.getenv("ANY4DH_AVATAR_ID", "001")
    ANY4DH_BATCH_SIZE = int(os.getenv("ANY4DH_BATCH_SIZE", "16"))
    ANY4DH_FPS = int(os.getenv("ANY4DH_FPS", "50"))
    ANY4DH_TTS = os.getenv("ANY4DH_TTS", "edgetts")
    ANY4DH_REF_FILE = os.getenv("ANY4DH_REF_FILE", "zh-CN-YunxiaNeural")
    ANY4DH_REF_TEXT = os.getenv("ANY4DH_REF_TEXT", "")
    ANY4DH_TTS_SERVER = os.getenv("ANY4DH_TTS_SERVER", "http://127.0.0.1:9880")
    ANY4DH_MAX_SESSION = int(os.getenv("ANY4DH_MAX_SESSION", "1"))
    ANY4DH_WAV2LIP_MODEL_DIR = os.getenv("ANY4DH_WAV2LIP_MODEL_DIR", "/mnt/c/models/wav2lip256/wav2lip.pth")
    ANY4DH_AVATARS_DIR = os.getenv("ANY4DH_AVATARS_DIR", "data/avatars")

    # 确保目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)
    os.makedirs(LLM_MODEL_DIR, exist_ok=True)
    os.makedirs(EMBEDDING_MODEL_DIR, exist_ok=True)
    os.makedirs(VECTOR_DB_PATH, exist_ok=True)
    os.makedirs(DOCS_PATH, exist_ok=True)
    os.makedirs(INDEX_TTS_MODEL_DIR, exist_ok=True)
    os.makedirs(ANY4DH_AVATARS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(ANY4DH_WAV2LIP_MODEL_DIR), exist_ok=True)

    # 外部LLM API配置
    LLM_SERVER_TYPE = os.getenv("LLM_SERVER_TYPE", "local")
    API_KEY = os.getenv("API_KEY", "")
    API_URL = os.getenv("API_URL", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "")
    API_BASE_URL = os.getenv("API_BASE_URL", "")
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))
    STREAM_ENABLED = os.getenv("STREAM_ENABLED", "true").lower() == "true"

    # 本地LLM模型名称配置
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen3-0.6b")