import os
from fastapi import FastAPI 
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from core.api_models import ProcessTextResponse
from core.text_add_keywords.process_text import process_text
from core.text_add_keywords.write_content import write_content
from core.text_add_keywords.get_chunk_content import get_chunk_content
from core.log import setup_logging
from core.database import query_data,execute_query
from core.lifespan import lifespan
from core.models import health_check,list_models
from core.transcription import create_transcription
from core.speech import create_speech
from core.rerank import rerank_documents
from core.mcp_tools import add
from core.mcp_tools import sub

# 初始化 MCP 服务
mcp = FastMCP("tools")

# 注册工具
mcp.tool()(add)
mcp.tool()(sub)

# 运行 MCP 服务
def run_mcp_server():
    """运行 MCP 服务"""
    mcp.settings.port = 9999  # MCP 监听 9999 端口
    mcp.run(transport="sse")

# 初始化日志
setup_logging()

# 初始化FastAPI应用
app = FastAPI(
    title="ANY FOR ANY",
    description="eogee.com any4any：ASR、TTS、Rerank模型兼容OpenAI-API并实现数据库连接、文本分块和分块儿后文本生成功能",
    version="0.0.5",
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

# API路由
app.post("/v1/rerank")(rerank_documents)
app.post("/v1/audio/transcriptions")(create_transcription)
app.post("/v1/audio/speech")(create_speech)
app.post("/v1/db/query")(query_data)
app.post("/v1/db/execute")(execute_query)
app.post("/process_text", response_model=ProcessTextResponse)(process_text)
app.post("/write_content")(write_content)
app.post("/get_chunk_content")(get_chunk_content)
app.get("/v1/models")(list_models)
app.get("/health")(health_check)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("public/index/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
