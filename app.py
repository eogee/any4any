import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
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
from core.chat.preview import preview_service
from core.mcp.mcp_tools import add, sub, mul, div

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
app.post("/v1/rerank")(rerank_documents)
app.post("/v1/audio/transcriptions")(create_transcription)
app.post("/v1/audio/speech")(create_speech)
app.post("/v1/chat/completions")(openai_api.chat_completions)

@app.get("/api/pending-previews")
async def get_pending_previews():
    """获取所有等待确认的预览列表"""
    try:
        pending_previews = await preview_service.get_pending_previews()
        return JSONResponse(pending_previews)
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

@app.get("/v1/chat/preview/{preview_id}")
async def get_preview(preview_id: str):
    """获取预览详情"""
    try:
        preview = await preview_service.get_preview(preview_id)
        return JSONResponse({
            "preview_id": preview.preview_id,
            "request": preview.request_data,
            "status": "preview"
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

@app.post("/v1/chat/confirm/{preview_id}")
async def confirm_preview(preview_id: str):
    """确认预览请求并返回最终响应"""
    try:
        response = await preview_service.confirm_preview(preview_id)
        return JSONResponse(response)
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

@app.get("/api/preview/{preview_id}")
async def get_preview_data(preview_id: str):
    """获取预览数据"""
    try:
        preview = await preview_service.get_preview(preview_id)
        return JSONResponse({
            "preview_id": preview.preview_id,
            "request": preview.request_data,
            "generated_content": preview.generated_content,
            "edited_content": preview.edited_content,
            "status": "preview"
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

@app.post("/api/preview/{preview_id}/edit")
async def update_preview_content(preview_id: str, request: Request):
    """更新保存预览内容"""
    try:
        data = await request.json()
        edited_content = data.get("content", "")
        await preview_service.update_content(preview_id, edited_content)
        return JSONResponse({
            "status": "success",
            "message": "Content updated successfully"
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)


app.post("/v1/db/query")(query_data)
app.post("/v1/db/execute")(execute_query)
app.get("/v1/models")(list_models)

app.post("/process_text", response_model=ProcessTextResponse)(process_text)
app.post("/write_content")(write_content)
app.post("/get_chunk_content")(get_chunk_content)

app.get("/health")(health_check)

@app.get("/v1/chat/completions/result/{preview_id}")
async def get_final_result(preview_id: str):
    """获取预览确认后的最终结果"""
    try:
        preview = await preview_service.get_preview(preview_id)
        if not preview.confirmed:
            return JSONResponse({
                "status": "waiting",
                "message": "Preview not confirmed yet",
                "preview_url": f"/preview/{preview_id}"
            })
        
        # 返回确认后的最终响应
        return JSONResponse(preview.response_data)
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
