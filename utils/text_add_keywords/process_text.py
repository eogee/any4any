from config import Config
from fastapi import Form, HTTPException
from typing import Optional, List
from pydantic import BaseModel

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

def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """将文本分块处理"""
    chunk_size = chunk_size or Config.DOC_CHUNK_SIZE
    overlap = overlap or Config.DOC_CHUNK_OVERLAP
    chunks = []
    start = 0
    end = chunk_size
    text_length = len(text)
    
    while start < text_length:
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
        end = start + chunk_size
        
        # 确保最后一块不会超出文本长度
        if end > text_length:
            end = text_length
    
    return chunks

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
        "chunk_size": Config.DOC_CHUNK_SIZE,
        "overlap": Config.DOC_CHUNK_OVERLAP,
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
