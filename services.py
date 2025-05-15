from fastapi import FastAPI, Body
import os
import re
import asyncio
import uuid
import time
import json
import logging
from typing import Optional, List
from fastapi import HTTPException, Request, Header, File, UploadFile, Form
from fastapi.responses import JSONResponse
from core_services import FileResponseWithCleanup, filter_special_chars
import torch
import torchaudio
from io import BytesIO
from edge_tts import Communicate, VoicesManager
from model import SenseVoiceSmall
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from FlagEmbedding import FlagReranker
from config import Config
from api_models import Message, ChatCompletionRequest, SpeechRequest, QADocs
from pydantic import BaseModel
import mysql.connector
from mysql.connector import Error

from pydantic import Field

class DatabaseQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="SQL query string (required)")

class DatabaseExecuteRequest(BaseModel):
    query: str

logger = logging.getLogger(__name__)

# --- 全局变量 ---
available_voices = []
reranker = None
m = None
kwargs = None
db_connection_pool = None

# --- 数据库连接 ---
def get_db_connection():
    """创建并返回MySQL数据库连接"""
    # 打印最终连接配置
    logger.info(f"DB连接配置 - host:{Config.MYSQL_HOST} port:{Config.MYSQL_PORT} "
               f"user:{Config.MYSQL_USER} db:{Config.MYSQL_DATABASE}")
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            try:
                connection = mysql.connector.connect(
                    host=Config.MYSQL_HOST,
                    port=Config.MYSQL_PORT,
                    user=Config.MYSQL_USER,
                    password=Config.MYSQL_PASSWORD,
                    database=Config.MYSQL_DATABASE,
                    connect_timeout=5
                )
            except Exception as e:
                logger.error(f"MySQL connection failed with config: "
                           f"host={Config.MYSQL_HOST}, "
                           f"port={Config.MYSQL_PORT}, "
                           f"user={Config.MYSQL_USER}, "
                           f"database={Config.MYSQL_DATABASE}")
                raise
            logger.info("Successfully connected to MySQL database")
            return connection
        except Error as e:
            logger.error(f"Attempt {attempt + 1} failed to connect to MySQL: {e}")
            if attempt == max_retries - 1:
                logger.error("All connection attempts failed")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Database connection failed",
                        "message": "Could not establish database connection",
                        "solution": "Check database service and credentials",
                        "config": {
                            "host": Config.MYSQL_HOST,
                            "port": Config.MYSQL_PORT,
                            "database": Config.MYSQL_DATABASE
                        }
                    }
                )
            time.sleep(retry_delay)

def preprocess_sql_query(query: str) -> str:
    """预处理SQL查询字符串
    1. 处理多换行，获取最后一个非空内容
    2. 去除代码块标记(```sql和```)
    3. 去除前后空格
    """
    # 去除代码块标记
    query = query.replace('```sql', '').replace('```', '')
    
    # 分割并获取最后一个非空内容
    lines = [line.strip() for line in query.split('\n\n') if line.strip()]
    if not lines:
        return ''
    
    return lines[-1]

async def query_data(
    request: Request,
    query: str = Form(None),
    db_request: DatabaseQueryRequest = Body(None)
):
    # 处理form-data格式请求
    if query is not None:
        db_request = DatabaseQueryRequest(query=query)
    # 处理json格式请求
    elif db_request is None:
        raise HTTPException(
            status_code=422,
            detail={"error": "Missing request body"}
        )
    
    # 验证查询参数
    if not db_request.query or not db_request.query.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Missing required parameter",
                "message": "The 'query' parameter is required and cannot be empty",
                "solution": "Provide a valid SQL query in the request body"
            }
        )
    
    # 如果配置开启查询清洗，则执行预处理
    query = db_request.query
    if Config.QUERY_CLEANING:
        query = preprocess_sql_query(query)
    
    """执行查询并返回结果
    WARNING: 不使用参数化查询，存在SQL注入风险
    
    请求示例:
    {
        "query": "SELECT * FROM users WHERE id = 1"
    }

    返回格式:
    [
        {
            "column1": "value1",
            "column2": "value2",
            ...
        },
        ...
    ]
    或空列表 []
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Error as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

async def execute_query(request: DatabaseExecuteRequest):
    """执行插入/更新/删除操作
    WARNING: 不使用参数化查询，存在SQL注入风险
    
    请求示例:
    {
        "query": "INSERT INTO users (name) VALUES ('John')"
    }
    """
    query = request.query
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
        return cursor.rowcount
    except Error as e:
        logger.error(f"Database execute failed: {e}")
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

# --- 认证验证 ---
async def verify_token(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authentication required",
                "message": "Please include your API key in the Authorization header",
                "format": "Bearer YOUR_API_KEY",
                "documentation": "https://example.com/api-docs"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid authorization format",
                "message": "Authorization header must start with 'Bearer '",
                "example": "Bearer abc123def456"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    token = authorization[7:]
    if token != Config.API_KEY:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Invalid API key",
                "message": "The provided API key is not valid",
                "solution": "Check your API key or contact support"
            }
        )

# --- 模型初始化 ---
async def initialize_models():
    """Initialize all models and voice list"""
    global m, kwargs, reranker, available_voices
    
    try:
        # 初始化语音转录模型
        logger.info(f"Loading model from: {Config.ASR_MODEL_DIR}")
        logger.info(f"Using device: {Config.DEVICE}")
        m, kwargs = SenseVoiceSmall.from_pretrained(
            model=Config.ASR_MODEL_DIR,
            device=Config.DEVICE
        )
        m.eval()
        logger.info("ASR model loaded successfully")

        # 初始化语音列表
        voices_manager = await VoicesManager.create()
        available_voices = voices_manager.voices
        logger.info(f"Loaded {len(available_voices)} available voices")

        # 初始化reranker模型
        reranker = FlagReranker(Config.RERANK_MODEL_DIR, use_fp16=False)
        logger.info("Reranker model loaded successfully")

    except Exception as e:
        logger.error(f"Failed to initialize models: {str(e)}")
        raise RuntimeError(f"Model initialization failed: {str(e)}")

# --- API端点处理函数 ---
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0),
    authorization: str = Header(None),
):
    """Transcribes audio into the input language."""
    await verify_token(authorization)
    
    start_time = time.time()
    try:
        audio_data = await file.read()
        data, fs = torchaudio.load(BytesIO(audio_data))
        data = data.mean(0)
        duration = len(data)/fs
        
        res = m.inference(
            data_in=[data],
            language=language.lower() if language else "auto",
            use_itn=False,
            ban_emo_unk=False,
            key=["openai_api_request"],
            fs=fs,
            **kwargs,
        )

        if not res or not res[0]:
            raise HTTPException(status_code=500, detail="Empty transcription result")

        raw_text = res[0][0]["text"]
        final_text = rich_transcription_postprocess(re.sub(r"<\|.*?\|>", "", raw_text))

        if Config.PROMPT is not None and Config.PROMPT != "":
            final_text = f"{final_text}<div style='display:none'>{Config.PROMPT}</div>"

        if Config.NO_THINK:
            final_text = f"{final_text}<div style='display:none'>/no_think</div>"
        
        logger.info(
            f"[ASR] Time: {time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Audio: {file.filename} | "
            f"Duration: {duration:.2f}s | "
            f"Processing Time: {time.time()-start_time:.2f}s | "
            f"Language: {language or 'auto'} | "
            f"Result: {final_text}"
        )

        if response_format == "text":
            return final_text
        return {"text": final_text}

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

async def create_speech(
    request: Request,
    authorization: str = Header(None),
):
    """Generates audio from the input text."""
    await verify_token(authorization)
    start_time = time.time()
    output_file = None
    
    try:
        data = await request.json()
        text = data.get("input", "")
        voice = data.get("voice", "zh-CN-XiaoyiNeural")
        
        text = filter_special_chars(text)
        
        if not any(v["ShortName"] == voice for v in available_voices):
            raise HTTPException(status_code=400, detail=f"Voice {voice} not available")

        if not text:
            # 输入为空时生成一个静默的音频文件
            output_file = f"temp_{uuid.uuid4().hex}.mp3"
            with open(output_file, 'wb') as f:
                f.write(b'')  # 写入空内容
        else:
            output_file = f"temp_{uuid.uuid4().hex}.mp3"
            communicate = Communicate(text, voice)
            await communicate.save(output_file)

        if not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Audio file creation failed")
            
        return FileResponseWithCleanup(
            output_file,
            media_type="audio/mpeg",
            filename="speech.mp3",
            cleanup_file=output_file
        )
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        raise HTTPException(status_code=500, detail=str(e))

async def rerank_documents(
    docs: QADocs,
    authorization: str = Header(None)
):
    """Rerank documents based on query"""
    await verify_token(authorization)
    
    try:
        if docs is None or len(docs.documents) == 0:
            return {"results": []}

        pairs = [[docs.query, doc] for doc in docs.documents]
        scores = reranker.compute_score(pairs, normalize=True)
        
        if isinstance(scores, float):
            scores = [scores]
            
        results = []
        for index, score in enumerate(scores):
            results.append({
                "index": index,
                "relevance_score": score,
                "text": docs.documents[index]
            })
        
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Reranking failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Reranking failed")

# --- 辅助端点 ---
async def list_models(authorization: Optional[str] = Header(None)):
    try:
        await verify_token(authorization)
    except HTTPException as e:
        if e.status_code != 401:
            raise e
    
    return {
        "data": [{
            "id": "sensevoice-small",
            "object": "model",
            "owned_by": "your-organization",
            "permissions": ["generate"]
        }]
    }

async def health_check():
    """Check service health status"""
    tts_status = "available" if available_voices else "unavailable"
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": {
            "asr": "loaded" if m is not None else "unloaded",
            "reranker": "loaded" if reranker is not None else "unloaded",
            "tts": tts_status
        }
    }

async def tts_test():
    """Test TTS functionality with a simple phrase"""
    test_text = "这是一个测试语音"
    test_voice = "zh-CN-XiaoyiNeural"
    output_file = f"test_{uuid.uuid4().hex}.mp3"
    
    try:
        if not any(v["ShortName"] == test_voice for v in available_voices):
            return JSONResponse(
                status_code=500,
                content={"error": f"Voice {test_voice} not available"}
            )
        
        communicate = Communicate(test_text, test_voice)
        await communicate.save(output_file)
        
        if not os.path.exists(output_file):
            return JSONResponse(
                status_code=500,
                content={"error": "Audio file not created"}
            )
            
        return FileResponseWithCleanup(
            output_file,
            media_type="audio/mpeg",
            filename="test.mp3",
            cleanup_file=output_file
        )
        
    except Exception as e:
        logger.error(f"TTS test failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

async def public_test():
    """Public test endpoint that doesn't require authentication"""
    return {
        "status": "success",
        "message": "Public endpoint is working",
        "next_steps": {
            "authenticated_endpoints": "Use /api-docs to learn how to authenticate",
            "tts_test": "Try /tts-test after setting up authentication"
        }
    }

async def get_api_docs():
    """Return API documentation"""
    return {
        "authentication": {
            "description": "Most API endpoints require authentication",
            "method": "Bearer token in Authorization header",
            "example": "Authorization: Bearer YOUR_API_KEY",
            "sample_requests": {
                "curl": "curl -X POST http://localhost:8888/v1/audio/speech \\\n-H 'Authorization: Bearer YOUR_API_KEY' \\\n-H 'Content-Type: application/json' \\\n-d '{\"input\":\"Hello world\",\"voice\":\"zh-CN-XiaoyiNeural\"}'",
                "python": """import requests

url = "http://localhost:8888/v1/audio/speech"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "input": "Hello world",
    "voice": "zh-CN-XiaoyiNeural"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())"""
            }
        },
        "endpoints": {
            "/v1/audio/speech": {
                "method": "POST",
                "description": "Convert text to speech",
                "parameters": {
                    "input": "Text to convert to speech",
                    "voice": "Voice to use (default: zh-CN-XiaoyiNeural)"
                },
                "example_request": {
                    "input": "Hello world",
                    "voice": "zh-CN-XiaoyiNeural"
                }
            },
            "/tts-test": {
                "method": "GET",
                "description": "Test TTS functionality (requires auth)"
            },
            "/public-test": {
                "method": "GET",
                "description": "Public test endpoint (no auth required)"
            },
            "/v1/db/query": {
                "method": "POST",
                "description": "Execute database query (WARNING: No parameterized queries, SQL injection risk)",
                "parameters": {
                    "query": "Complete SQL query string"
                },
                "request_formats": {
                    "application/json": {
                        "example": {
                            "query": "SELECT * FROM users WHERE id = 1"
                        },
                        "description": "JSON格式请求体"
                    },
                    "multipart/form-data": {
                        "example": "curl -X POST http://localhost:8888/v1/db/query \\\n-H 'Authorization: Bearer YOUR_API_KEY' \\\n-F 'query=SELECT * FROM users WHERE id = 1'",
                        "description": "表单格式请求，字段名为query"
                    }
                },
                "notes": "支持两种请求格式：JSON和表单数据",
                "example_response": [
                    {
                        "id": 1,
                        "name": "John",
                        "email": "john@example.com"
                    },
                    {
                        "id": 2,
                        "name": "Jane",
                        "email": "jane@example.com"
                    }
                ]
            },
            "/v1/db/execute": {
                "method": "POST",
                "description": "Execute database update/insert/delete (WARNING: No parameterized queries, SQL injection risk)",
                "parameters": {
                    "query": "Complete SQL statement"
                },
                "example_request": {
                    "query": "INSERT INTO users (name) VALUES ('John')"
                }
            }
        }
    }

async def lifespan(app: FastAPI):
    """Initialize models on startup"""
    await initialize_models()
    yield
    # Cleanup on shutdown if needed
