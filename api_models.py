from enum import Enum
from pydantic import BaseModel
from typing import Optional, List

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
