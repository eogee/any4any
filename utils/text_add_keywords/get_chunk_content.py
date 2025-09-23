import json
from fastapi import Form, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# 分块数据模型(用于内容检索)
class ChunkData(BaseModel):
    total_chunks: int
    chunk_size: Optional[int] = None
    overlap: Optional[int] = None
    chunks: List[Dict[str, Any]]

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
