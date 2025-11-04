import os
import multiprocessing
try:
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method("spawn")
except RuntimeError:
    pass
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from config import Config
from core.log import setup_logging
from core.database.database import query_data,execute_query
from core.lifespan import lifespan
from core.model_manager import health_check,list_models
from core.asr.transcription import create_transcription
from core.tts.speech import create_speech
from core.rerank.rerank import rerank_documents
from core.chat.openai_api import openai_api
from core.embedding.openai_api import get_embedding_router
from core.mcp.mcp_tools import add,sub,mul,div

# 初始化 MCP 服务
mcp = FastMCP("tools")

# 注册工具
mcp.tool()(add)
mcp.tool()(sub)
mcp.tool()(mul)
mcp.tool()(div)

# 运行 MCP 服务
def run_mcp_server():
    """运行 MCP 服务"""
    mcp.settings.port = Config.MCP_PORT  # MCP 监听 9999 端口
    mcp.run(transport=Config.MCP_TRANSPORT)

# 初始化日志
setup_logging()

# 初始化FastAPI应用
app = FastAPI(
    title="ANY FOR ANY",
    description="any4any：开源多模态AI服务系统，提供LLM对话、ASR语音识别、TTS语音合成、文本嵌入、重排序、数字人、MCP工具和NL2SQL等AI能力的OpenAI兼容API接口",
    version="0.1.3",
    lifespan=lifespan
)

# 确保data目录存在
os.makedirs("data", exist_ok=True)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 会话中间件配置
app.add_middleware(
    SessionMiddleware,
    secret_key=Config.API_KEY or "your-secret-key",     # 使用API_KEY作为会话密钥，如果为空则使用默认值
    max_age=Config.SESSION_MAX_AGE                      # 使用配置文件中的会话有效期设置
)

# API路由
app.get("/v1/models")(list_models)
app.post("/v1/rerank")(rerank_documents)
app.post("/v1/audio/transcriptions")(create_transcription)
app.post("/v1/audio/speech")(create_speech)
app.post("/v1/chat/completions")(openai_api.chat_completions)
app.get("/health")(health_check)

app.post("/v1/db/query")(query_data)
app.post("/v1/db/execute")(execute_query)

# 注册Embedding API路由
embedding_router = get_embedding_router()
app.include_router(embedding_router)

# 注册PreviewServer路由
from servers.PreviewServer import PreviewServer
preview_server = PreviewServer()
preview_server.register_routes(app)

# 注册TimeoutServer路由
from servers.TimeoutServer import TimeoutServer
timeout_server = TimeoutServer()
timeout_server.register_routes(app)
