import time
import logging
from typing import Dict, Optional
from fastapi import HTTPException
from pydantic import BaseModel
from config import Config
from data_models.Preview import Preview

class PreviewRequest(BaseModel):
    """预览请求数据模型"""
    preview_id: str
    request_data: dict
    created_at: float
    confirmed: bool = False
    response_data: Optional[dict] = None
    generated_content: Optional[str] = None
    edited_content: Optional[str] = None

class PreviewService:
    """预览服务管理类"""
    _instance = None
    _previews: Dict[str, PreviewRequest] = {}
    
    # 配置参数（直接使用Config中的配置）
    PREVIEW_TIMEOUT = Config.PREVIEW_TIMEOUT  # 预览超时时间
    CLEANUP_INTERVAL = Config.CLEANUP_INTERVAL  # 清理间隔
    MAX_PREVIEW_COUNT = Config.MAX_PREVIEW_COUNT  # 最大预览数量
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PreviewService, cls).__new__(cls)
        return cls._instance
    
    async def create_preview(self, request_data: dict) -> PreviewRequest:
        """创建新的预览请求"""
        # 检查预览模式是否启用
        if not Config.PREVIEW_MODE:
            raise HTTPException(status_code=403, detail="Preview mode is disabled")
            
        preview_id = f"preview_{int(time.time())}"
        preview = PreviewRequest(
            preview_id=preview_id,
            request_data=request_data,
            created_at=time.time()
        )
        self._previews[preview_id] = preview
        return preview
    
    async def set_generated_content(self, preview_id: str, content: str):
        """设置预览请求的生成内容"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        preview.generated_content = content
        return preview
    
    async def update_content(self, preview_id: str, edited_content: str):
        """更新预览内容（用户编辑后）"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        pre_content = preview.generated_content or ""
        
        # 更新内存中的内容
        preview.edited_content = edited_content
        
        # 将内容持久化到数据库
        try:
            preview_model = Preview()
            
            # 从request_data中提取最后一个role为user的content
            last_user_content = ""
            if preview.request_data and "messages" in preview.request_data:
                messages = preview.request_data["messages"]
                # 遍历消息列表，找到最后一个用户消息
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        last_user_content = msg.get("content", "")
                        break
            
            # 保存到数据库，包括编辑前内容、编辑后内容、请求数据等
            preview_model.save_preview_content(
                preview_id=preview_id,
                edited_content=edited_content,
                pre_content=pre_content,
                full_request=preview.request_data,
                last_request=last_user_content  # 使用最后一个用户消息作为last_request
            )
        except Exception as e:
            # 记录错误但不中断流程，确保即使数据库保存失败，内存中的更新仍然成功
            logging.error(f"Failed to save preview content to database: {e}")
        
        return preview
    
    async def get_content(self, preview_id: str) -> str:
        """获取预览内容（优先返回编辑后的内容）"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        return preview.edited_content or preview.generated_content or ""
    
    async def confirm_preview(self, preview_id: str) -> dict:
        """确认预览请求并返回最终响应"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        
        # 如果已经确认过，直接返回缓存的响应
        if preview.confirmed and preview.response_data:
            return preview.response_data
        
        # 获取最终内容（编辑后的或原生成的）
        final_content = await self.get_content(preview_id)
        
        if not final_content:
            raise HTTPException(status_code=400, detail="No content available for preview")
        
        # 构建OpenAI兼容响应
        request_data = preview.request_data
        response_data = {
            "id": f"openai_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request_data.get("model", "default"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": final_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        
        # 更新预览状态
        preview.confirmed = True
        preview.response_data = response_data
        
        return response_data
    
    async def get_preview(self, preview_id: str) -> PreviewRequest:
        """获取预览请求"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        return self._previews[preview_id]
    
    async def get_pending_previews(self) -> list:
        """获取所有等待确认的预览列表"""
        pending = []
        for preview_id, preview in self._previews.items():
            if not preview.confirmed and preview.generated_content:
                pending.append({
                    "preview_id": preview_id,
                    "created_at": preview.created_at,
                    "preview_url": f"/preview/{preview_id}",
                    "request_data": preview.request_data,  # 添加请求数据
                    "generated_content": preview.generated_content,  # 修改为完整内容
                    "generated_content_preview": preview.generated_content[:100] + "..." if len(preview.generated_content) > 100 else preview.generated_content
                })
        return pending

# 创建全局预览服务实例
preview_service = PreviewService()
