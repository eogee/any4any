from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import HTTPException
from core.embedding.embedding_manager import EmbeddingManager

router = APIRouter(prefix="/v1", tags=["embeddings"])

_embedding_manager = None # 延迟初始化embedding管理器

def get_embedding_manager():
    """获取embedding管理器实例"""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
    return _embedding_manager

# 定义请求和响应模型
class EmbeddingRequest(BaseModel):
    input: str | List[str]
    model: str

class Embedding(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[Embedding]
    model: str
    usage: dict

@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """创建向量表示 接收文本输入，返回对应的向量表示"""
    inputs = [request.input] if isinstance(request.input, str) else request.input
    
    # 限制最大输入数量和单个输入长度
    if len(inputs) > 100:
        raise HTTPException(status_code=400, detail="Too many inputs")

    for i, text in enumerate(inputs):
        if len(text) > 8192:
            raise HTTPException(status_code=400, detail=f"Input {i} is too long")
        
    embedding_manager = get_embedding_manager() # 获取embedding管理器    
    
    embeddings = embedding_manager.get_embeddings(inputs) # 执行向量表示计算
    
    data = [
        Embedding(object="embedding", embedding=emb, index=i)
        for i, emb in enumerate(embeddings)
    ]
    
    total_tokens = sum(len(text.split()) for text in inputs)
    
    return EmbeddingResponse(
        object="list",
        data=data,
        model=request.model,
        usage={"prompt_tokens": total_tokens, "total_tokens": total_tokens}
    )

def get_embedding_router():
    return router