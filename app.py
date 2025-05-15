from fastapi import FastAPI, File, Form, UploadFile, Header, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from api_models import Config, Message, ChatCompletionRequest, SpeechRequest, QADocs
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
    description="eogee.com any4any ASR、TTS和Rerank模型兼容OpenAI-API",
    version="0.0.3",
    lifespan=services.lifespan
)

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
app.get("/v1/models")(list_models)
app.get("/health")(health_check)
app.get("/tts-test")(tts_test)
app.get("/public-test")(public_test)
app.get("/api-docs")(get_api_docs)

# 启动服务
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,
        log_level="info"
    )
