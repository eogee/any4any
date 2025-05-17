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
from text_processing.text_utils import chunk_text
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
    title="ANY FOR API",
    description="eogee.com any4any：ASR、TTS、Rerank模型兼容OpenAI-API并实现数据库连接",
    version="0.0.4",
    lifespan=services.lifespan
)

# 确保data目录存在
os.makedirs("data", exist_ok=True)

def write_content_to_file(content: str, filename: str = "fixed_knowledge.txt") -> str:
    """
    将内容写入文件（如果文件不存在则创建）
    :param content: 要写入的文本内容
    :param filename: 文件名（默认 fixed_knowledge.txt）
    :return: 文件路径
    """
    filepath = os.path.join("data", filename)
    with open(filepath, "a", encoding="utf-8") as file:
        file.write(content + "\n")  # 追加内容并换行
    return filepath

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
app.get("/v1/models")(list_models)
app.get("/health")(health_check)
app.get("/tts-test")(tts_test)
app.get("/public-test")(public_test)
app.get("/api-docs")(get_api_docs)

@app.post("/process_text", response_model=ProcessTextResponse)
async def process_text(
    request: TextRequest = None,
    text: str = Form(None, description="文本内容，用于form-data格式请求")
):
    """
    处理文本分块的API端点
    - 支持JSON请求: {"text": "..."}
    - 支持form-data请求: text=...
    """
    if request:
        text = request.text
    elif not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    # 检查文本长度
    if len(text) == 0:
        raise HTTPException(status_code=400, detail="Empty text provided")
    
    # 分块处理文本
    chunks = chunk_text(text)
    
    # 构建响应数据
    response_data = {
        "total_chunks": len(chunks),
        "chunk_size": Config.DEFAULT_CHUNK_SIZE,
        "overlap": Config.DEFAULT_OVERLAP,
        "chunks": [
            {
                "chunk_number": i,
                "content": chunk,
                "length": len(chunk)
            }
            for i, chunk in enumerate(chunks, 1)
        ]
    }
    
    return response_data

@app.get("/")
async def root():
    return {
        "message": "文本分块处理服务",
        "usage": "发送POST请求到/process_text端点，包含JSON数据: {'text': '你的长文本内容...'}"
    }

@app.post("/write_content")
async def write_content(
    content: str = Form(None, description="直接传递文本内容或JSON格式的content字段"), 
    keywords: str = Form(None, description="关键词内容，会过滤<think>标签并拼接<<<<<"),
    file: UploadFile = Form(None, description="或通过文件上传内容")
):
    """
    接收 form-data 格式的 POST 请求，支持多种方式提交内容：
    1. 直接传递 `content` 字段的文本
    2. 传递 `keywords` 字段的文本(会过滤<think>标签并拼接<<<<<)
    3. 传递JSON格式的content字段，如 {"content":"文本内容"}
    4. 通过文件上传（文件内容作为文本）
    """
    try:
        # 处理传入的内容
        if keywords:
            # 过滤各种形式的<think>标签并拼接<<<<<
            text_content = re.sub(r'<think\b[^>]*>.*?</think>', '', keywords, flags=re.DOTALL) + "<<<<<"
        elif content:
            try:
                # 尝试解析JSON格式的content
                content_json = json.loads(content)
                if isinstance(content_json, dict) and "content" in content_json:
                    text_content = content_json["content"]
                else:
                    text_content = content
            except json.JSONDecodeError:
                text_content = content
            # 对content字段进行额外处理
            text_content = text_content
        elif file:
            text_content = (await file.read()).decode("utf-8")
        else:
            raise HTTPException(status_code=400, detail="必须提供 content、keywords 或 file 字段")
        
        # 写入文件
        filepath = write_content_to_file(text_content)
        return JSONResponse(
            status_code=200,
            content={"message": "内容已写入文件", "filepath": filepath}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_chunk_content")
async def get_chunk_content(
    json_data: str = Form(..., description="JSON字符串格式的chunks数据"),
    round_number: int = Form(..., description="要获取的chunk编号")
):
    """
    通过form-data获取指定轮次(chunk_number)的content
    - 输入: 
        - json_data: JSON字符串(包含chunks数据)
        - round_number: 目标chunk编号
    - 输出: 对应的content或错误信息
    """
    try:
        # 直接解析JSON字符串
        data = json.loads(json_data)
        
        # 转换为Pydantic模型(用于验证)
        try:
            chunk_data = ChunkData(**data)
        except ValueError as ve:
            raise HTTPException(
                status_code=422,
                detail=f"Validation error: {str(ve)}"
            )
        
        # 查找目标chunk
        for chunk in chunk_data.chunks:
            if isinstance(chunk, dict) and chunk.get("chunk_number") == round_number:
                content = chunk.get("content")
                if content is not None:
                    return {"content": content}
        
        # 未找到时返回404
        raise HTTPException(
            status_code=404,
            detail=f"Chunk with number {round_number} not found."
        )
    except json.JSONDecodeError as je:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON format: {str(je)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


