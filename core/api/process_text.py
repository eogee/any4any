from fastapi import Form, HTTPException
from config import Config
from api_models import TextRequest
from core.text_deal.chunk import chunk_text

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
