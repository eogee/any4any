import json
import os
import re
from fastapi import FastAPI, File, Form, UploadFile, Header, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from config import Config
from api_models import (
    Message, ChatCompletionRequest, SpeechRequest, QADocs,
    TextRequest, ProcessTextResponse, ChunkResponse, ChunkData
)


from core.text_deal.keywords import process_keywords
from core.api.process_text import process_text
from core.api.write_content import write_content
from core.api.get_chunk_content import get_chunk_content

import services
from services import (
    verify_token,
    create_transcription,
    create_speech,
    rerank_documents,
    tts_test,
    public_test,
    get_api_docs,
    list_models,
    health_check
)


# 导入工具模块
import core_services

# 初始化日志
core_services.setup_logging()

# 初始化FastAPI应用
app = FastAPI(
    title="ANY FOR ANY",
    description="eogee.com any4any：ASR、TTS、Rerank模型兼容OpenAI-API并实现数据库连接、文本分块和分块儿后文本生成功能",
    version="0.0.5",
    lifespan=services.lifespan
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
app.post("/v1/db/query")(services.query_data)
app.post("/v1/db/execute")(services.execute_query)
app.post("/process_text", response_model=ProcessTextResponse)(process_text)
app.post("/write_content")(write_content)
app.post("/get_chunk_content")(get_chunk_content)
app.get("/v1/models")(list_models)
app.get("/health")(health_check)
app.get("/tts-test")(tts_test)
app.get("/public-test")(public_test)
app.get("/api-docs")(get_api_docs)
@app.get("/")
async def root():
    return {
        "message": "文本分块处理服务",
        "usage": "发送POST请求到/process_text端点，包含JSON数据: {'text': '你的长文本内容...'}"
    }