import os
import torch
from dotenv import load_dotenv

load_dotenv()

def get_bool_env(key: str, default: bool = False) -> bool:
    """从环境变量获取布尔值"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

class Config:
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8888))
    PREVIEW_MODE = get_bool_env("PREVIEW_MODE", True)
    PREVIEW_TIMEOUT = int(os.getenv("PREVIEW_TIMEOUT", "60"))
    DELAY_MODE = get_bool_env("DELAY_MODE", False)
    DELAY_TIME = int(os.getenv("DELAY_TIME", "3"))
    KNOWLEDGE_BASE_ENABLED = get_bool_env("KNOWLEDGE_BASE_ENABLED", False)

    # MCP配置
    MCP_PORT = int(os.getenv("MCP_PORT", 9999))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")

    # 认证配置
    API_KEY = os.getenv("API_KEY", "EMPTY")
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "1800"))
    MAX_CONVERSATION_MESSAGES = int(os.getenv("MAX_CONVERSATION_MESSAGES", "20"))
    MAX_CONVERSATION_TOKENS = int(os.getenv("MAX_CONVERSATION_TOKENS", "8000"))
    ENABLE_CONVERSATION_TRUNCATION = get_bool_env("ENABLE_CONVERSATION_TRUNCATION", True)

    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    EDGE_TTS_ENABLED = get_bool_env("EDGE_TTS_ENABLED", False)
    EDGE_DEFAULT_VOICE = os.getenv("EDGE_DEFAULT_VOICE", "zh-CN-XiaoyiNeural")

    # 模型按需加载配置 (默认不加载，只在首次调用时加载)
    INDEX_TTS_MODEL_ENABLED = get_bool_env("INDEX_TTS_MODEL_ENABLED", False)
    ASR_MODEL_ENABLED = get_bool_env("ASR_MODEL_ENABLED", False)
    RERANK_MODEL_ENABLED = get_bool_env("RERANK_MODEL_ENABLED", False)
    EMBEDDING_MODEL_ENABLED = get_bool_env("EMBEDDING_MODEL_ENABLED", False)
    LLM_MODEL_ENABLED = get_bool_env("LLM_MODEL_ENABLED", False)

    # 模型路径配置 (按需加载的模型路径)
    INDEX_TTS_MODEL_DIR = os.getenv("INDEX_TTS_MODEL_DIR", "/mnt/c/models/IndexTTS-1.5")
    ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", "/mnt/c/models/SenseVoiceSmall")
    RERANK_MODEL_DIR = os.getenv("RERANK_MODEL_DIR", "/mnt/c/models/bge-reranker-base")
    EMBEDDING_MODEL_DIR = os.getenv("EMBEDDING_MODEL_DIR", "/mnt/c/models/bge-small-zh-v1.5")
    LLM_MODEL_DIR = os.getenv("LLM_MODEL_DIR", "/mnt/c/models/Qwen3-0.6B")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen3-0.6B")
    NO_THINK = get_bool_env("NO_THINK", True)
    ASR_PROMPT = os.getenv("ASR_PROMPT", "")

    # LLM模型加载配置
    TRUST_REMOTE_CODE = get_bool_env("TRUST_REMOTE_CODE", True)
    USE_HALF_PRECISION = get_bool_env("USE_HALF_PRECISION", True)
    LOW_CPU_MEM_USAGE = get_bool_env("LOW_CPU_MEM_USAGE", True)
    TOKENIZERS_PARALLELISM = get_bool_env("TOKENIZERS_PARALLELISM", False)

    # LLM模型生成参数配置
    MAX_LENGTH = int(os.getenv("MAX_LENGTH", "4096"))
    NUM_RETURN_SEQUENCES = int(os.getenv("NUM_RETURN_SEQUENCES", "1"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    TOP_P = float(os.getenv("TOP_P", "0.9"))
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.1"))
    LLM_PROMPT = os.getenv("LLM_PROMPT", "").replace("\\n", "\n")

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
    INDEX_TTS_FAST_ENABLED = get_bool_env("INDEX_TTS_FAST_ENABLED", False)
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
    QUERY_CLEANING = get_bool_env("QUERY_CLEANING", True)

    # MySQL连接池配置
    DB_POOL_ENABLED = get_bool_env("DB_POOL_ENABLED", True)
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "15"))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    DB_POOL_PRE_PING = get_bool_env("DB_POOL_PRE_PING", True)

    # 熔断器配置
    DB_CIRCUIT_BREAKER_ENABLED = get_bool_env("DB_CIRCUIT_BREAKER_ENABLED", True)
    DB_CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("DB_CIRCUIT_BREAKER_THRESHOLD", "5"))
    DB_CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("DB_CIRCUIT_BREAKER_TIMEOUT", "60"))

    # 重试机制配置
    DB_RETRY_ENABLED = get_bool_env("DB_RETRY_ENABLED", True)
    DB_RETRY_MAX_ATTEMPTS = int(os.getenv("DB_RETRY_MAX_ATTEMPTS", "3"))
    DB_RETRY_BACKOFF_FACTOR = float(os.getenv("DB_RETRY_BACKOFF_FACTOR", "2"))
    DB_RETRY_MAX_DELAY = int(os.getenv("DB_RETRY_MAX_DELAY", "30"))

    # 工具系统配置

    # SQL数据库配置 (复用现有MySQL配置)
    SQL_DB_TYPE = os.getenv("SQL_DB_TYPE", "mysql")
    SQL_DB_HOST = MYSQL_HOST
    SQL_DB_PORT = MYSQL_PORT
    SQL_DB_USERNAME = MYSQL_USER
    SQL_DB_PASSWORD = MYSQL_PASSWORD
    SQL_DB_DATABASE = MYSQL_DATABASE

    # 工具系统配置
    TOOLS_ENABLED = get_bool_env("TOOLS_ENABLED", True) 
    # NL2SQL工具配置
    NL2SQL_ENABLED = get_bool_env("NL2SQL_ENABLED", True)

    # 时间工具配置
    TIME_TOOLS_ENABLED = get_bool_env("TIME_TOOLS_ENABLED", True)
    TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Shanghai")
    TIME_FORMAT_DEFAULT = os.getenv("TIME_FORMAT_DEFAULT", "%Y-%m-%d %H:%M:%S")  

    # 钉钉配置
    DINGTALK_ENABLED = get_bool_env("DINGTALK_ENABLED", False)
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    ROBOT_CODE = os.getenv("ROBOT_CODE", "")
    DINGTALK_PORT = os.getenv("DINGTALK_PORT", "6666")

    # any4dh 数字人配置
    ANY4DH_ENABLED = get_bool_env("ANY4DH_ENABLED", False)
    ANY4DH_USE_UNIFIED_INTERFACE = get_bool_env("ANY4DH_USE_UNIFIED_INTERFACE", True)
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

    # any4dh 语音知识库配置
    ANY4DH_VOICE_KB_ENABLED = get_bool_env("ANY4DH_VOICE_KB_ENABLED", False)
    ANY4DH_VOICE_KB_LANGUAGE = os.getenv("ANY4DH_VOICE_KB_LANGUAGE", "zh")
    ANY4DH_VOICE_KB_FALLBACK_TO_TTS = get_bool_env("ANY4DH_VOICE_KB_FALLBACK_TO_TTS", True)
    ANY4DH_VOICE_KB_SEMANTIC_THRESHOLD = float(os.getenv("ANY4DH_VOICE_KB_SEMANTIC_THRESHOLD", "0.1"))
    VOICE_KB_CSV_PATH = os.getenv("VOICE_KB_CSV_PATH", "data/csv/en_voice_list.csv")
    VOICE_KB_AUDIO_DIR = os.getenv("VOICE_KB_AUDIO_DIR", "data/en_answer")

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
    EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "")
    API_BASE_URL = os.getenv("API_BASE_URL", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "")
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "120"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))
    STREAM_ENABLED = get_bool_env("STREAM_ENABLED", True)
    API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
    API_RETRY_DELAY = float(os.getenv("API_RETRY_DELAY", "1.0"))

    # 本地LLM模型名称配置
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen3-0.6b")

    # ADB工具配置
    ADB_TOOLS_ENABLED = get_bool_env("ADB_TOOLS_ENABLED", False)
    ADB_COMMAND_PATH = os.getenv("ADB_COMMAND_PATH", "/mnt/c/platform-tools/adb.exe")
    ADB_TIMEOUT = int(os.getenv("ADB_TIMEOUT", 30))
    ADB_RETRY_COUNT = int(os.getenv("ADB_RETRY_COUNT", 3))
    
    # Web搜索工具配置
    WEB_SEARCH_ENABLED = get_bool_env("WEB_SEARCH_ENABLED", True)
    WEB_SEARCH_PROXY_URL = os.getenv("WEB_SEARCH_PROXY_URL", "http://127.0.0.1:10809")
    WEB_SEARCH_USE_PROXY = get_bool_env("WEB_SEARCH_USE_PROXY", False)
    WEB_SEARCH_RESULT_LIMIT = int(os.getenv("WEB_SEARCH_RESULT_LIMIT", "10"))
    WEB_SEARCH_TIMEOUT = int(os.getenv("WEB_SEARCH_TIMEOUT", "30"))
