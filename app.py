import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from config import Config
from core.api_models import ProcessTextResponse
from utils.text_add_keywords.process_text import process_text
from utils.text_add_keywords.write_content import write_content
from utils.text_add_keywords.get_chunk_content import get_chunk_content
from core.log import setup_logging
from core.database.database import query_data,execute_query
from core.lifespan import lifespan
from core.model_manager import health_check,list_models
from core.asr.transcription import create_transcription
from core.tts.speech import create_speech
from core.rerank.rerank import rerank_documents
from core.chat.openai_api import openai_api
from core.chat.api import get_pending_previews,get_preview,confirm_preview,get_preview_data,update_preview_content
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
    description="eogee.com any4any：LLM、ASR、TTS、Rerank模型兼容OpenAI-API并实现数据库连接、文本分块和分块儿后文本生成功能",
    version="0.1.0",
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

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# API路由
app.get("/v1/models")(list_models)
app.post("/v1/rerank")(rerank_documents)
app.post("/v1/audio/transcriptions")(create_transcription)
app.post("/v1/audio/speech")(create_speech)
app.post("/v1/chat/completions")(openai_api.chat_completions)

app.get("/api/pending-previews")(get_pending_previews)
app.get("/v1/chat/preview/{preview_id}")(get_preview)
app.post("/v1/chat/confirm/{preview_id}")(confirm_preview)
app.get("/api/preview/{preview_id}")(get_preview_data)
app.post("/api/preview/{preview_id}/edit")(update_preview_content)
app.get("/v1/chat/completions/result/{preview_id}")(get_preview_data)

app.post("/v1/db/query")(query_data)
app.post("/v1/db/execute")(execute_query)

app.post("/process_text", response_model=ProcessTextResponse)(process_text)
app.post("/write_content")(write_content)
app.post("/get_chunk_content")(get_chunk_content)

app.get("/health")(health_check)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
