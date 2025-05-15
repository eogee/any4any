from enum import Enum
from pydantic import BaseModel
from typing import Optional, List
import os
import torch

# 配置类
class Config:
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8888
    
    # 认证配置
    API_KEY = "EMPTY"  # 替换为你的实际API密钥
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"  # 本地ASR模型路径
    RERANK_MODEL_PATH = "/mnt/c/models/bge-reranker-base"  # 本地rerank模型路径

    # 是否开启nothink，目前仅有qwen3系列LLM模型支持
    NO_THINK = True

    # 提示词
    PROMPT = "" # 自定义提示词，会在语音转文字识别结果后面显示，建议使用中文，留空则无内容
    
    # 确保模型目录存在
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_PATH, exist_ok=True)

# 语言枚举
class Language(str, Enum):
    zh = "zh"
    en = "en"
    yue = "yue"
    ja = "ja"
    ko = "ko"

# 消息模型
class Message(BaseModel):
    role: str
    content: str

# 聊天完成请求模型
class ChatCompletionRequest(BaseModel):
    model: str = "edge-tts"
    messages: list[Message]
    voice: Optional[str] = "zh-CN-XiaoyiNeural"
    stream: Optional[bool] = False

# 语音请求模型
class SpeechRequest(BaseModel):
    input: str
    voice: Optional[str] = "zh-CN-XiaoyiNeural"
    model: Optional[str] = "edge-tts"

# Rerank数据模型
class QADocs(BaseModel):
    query: Optional[str]
    documents: Optional[List[str]]
