"""
API 接口的数据模型
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

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

# 文本处理请求模型
class TextRequest(BaseModel):
    text: str

# 文本分块响应模型
class ChunkResponse(BaseModel):
    chunk_number: int
    content: str
    length: int

# 处理结果响应模型
class ProcessTextResponse(BaseModel):
    total_chunks: int
    chunk_size: int
    overlap: int
    chunks: List[ChunkResponse]

# 分块数据模型(用于内容检索)
class ChunkData(BaseModel):
    total_chunks: int
    chunk_size: Optional[int] = None
    overlap: Optional[int] = None
    chunks: List[Dict[str, Any]]
