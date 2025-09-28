import time
import logging
import uuid
from typing import Dict, Optional, Callable
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
    _confirm_callbacks: list[Callable] = []
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PreviewService, cls).__new__(cls)
        return cls._instance
    
    async def create_preview(self, request_data: dict) -> PreviewRequest:
        """创建新的预览请求"""
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
    
    async def update_content(self, preview_id: str, edited_content: str, session: dict = None):
        """更新预览内容"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        pre_content = preview.generated_content or ""
        preview.edited_content = edited_content
        
        # 持久化到数据库
        try:
            preview_model = Preview()
            
            # 提取当前请求内容
            current_request = ""
            if preview.request_data and "messages" in preview.request_data:
                for msg in reversed(preview.request_data["messages"]):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        current_request = msg.get("content", "")
                        break
            
            # 获取或生成 conversation_id 和 message_id
            conversation_id = preview.request_data.get("conversation_id")
            message_id = preview.request_data.get("message_id")
            
            if not message_id and preview.request_data and "messages" in preview.request_data:
                messages = preview.request_data["messages"]
                if messages and isinstance(messages[-1], dict):
                    message_id = messages[-1].get("id") or messages[-1].get("message_id")
            
            # 查询数据库获取ID
            if not conversation_id or not message_id:
                try:
                    if message_id:
                        result = preview_model.fetch_one(
                            "SELECT conversation_id FROM messages WHERE message_id = %s",
                            (message_id,)
                        )
                        if result:
                            conversation_id = result.get("conversation_id")
                    elif current_request:
                        result = preview_model.fetch_one(
                            "SELECT conversation_id, message_id FROM messages WHERE content LIKE %s ORDER BY timestamp DESC LIMIT 1",
                            (f"%{current_request[:100]}%",)
                        )
                        if result:
                            conversation_id = result.get("conversation_id")
                            message_id = result.get("message_id")
                except Exception as db_error:
                    logging.warning(f"Failed to query IDs: {db_error}")
            
            # 生成默认ID
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            if not message_id:
                message_id = str(uuid.uuid4())
            
            # 保存到数据库
            preview_model.save_preview_content(
                preview_id=preview_id,
                saved_content=edited_content,
                pre_content=pre_content,
                full_request=preview.request_data,
                current_request=current_request,
                conversation_id=conversation_id,
                message_id=message_id,
                response_time=time.time() - preview.created_at,
                user_id=session.get("user_id", 1) if session else 1
            )
        except Exception as e:
            logging.error(f"Failed to save preview content: {e}")
        
        return preview
    
    async def get_content(self, preview_id: str) -> str:
        """获取预览内容"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        return preview.edited_content or preview.generated_content or ""
    
    def register_confirm_callback(self, callback: Callable):
        """注册预览确认回调函数"""
        if callback not in self._confirm_callbacks:
            self._confirm_callbacks.append(callback)
    
    async def confirm_preview(self, preview_id: str) -> dict:
        """确认预览请求"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        preview = self._previews[preview_id]
        
        if preview.confirmed and preview.response_data:
            return preview.response_data
        
        final_content = await self.get_content(preview_id)
        if not final_content:
            raise HTTPException(status_code=400, detail="No content available")
        
        # 构建响应数据
        request_data = preview.request_data
        response_data = {
            "id": f"openai_{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request_data.get("model", "default"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": final_content},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        
        preview.confirmed = True
        preview.response_data = response_data
        
        # 触发回调
        for callback in self._confirm_callbacks:
            try:
                await callback(preview_id, final_content, request_data)
            except Exception as e:
                logging.error(f"Error in callback: {e}")
        
        return response_data
    
    async def get_preview(self, preview_id: str) -> PreviewRequest:
        """获取预览请求"""
        if preview_id not in self._previews:
            raise HTTPException(status_code=404, detail="Preview not found")
        return self._previews[preview_id]
    
    async def get_pending_previews(self) -> list:
        """获取等待确认的预览列表"""
        pending = []
        for preview_id, preview in self._previews.items():
            if not preview.confirmed and preview.generated_content:
                request_data = preview.request_data.copy() if preview.request_data else {}
                
                # 获取或生成 conversation_id
                conversation_id = request_data.get('conversation_id')
                if not conversation_id and request_data and 'messages' in request_data:
                    for msg in reversed(request_data['messages']):
                        if isinstance(msg, dict) and msg.get('role') == 'user':
                            last_user_message = msg.get('content', '')
                            if last_user_message:
                                try:
                                    preview_model = Preview()
                                    result = preview_model.fetch_one(
                                        "SELECT conversation_id FROM messages WHERE content LIKE %s ORDER BY timestamp DESC LIMIT 1",
                                        (f"%{last_user_message[:100]}%",)
                                    )
                                    if result:
                                        conversation_id = result.get('conversation_id')
                                except Exception:
                                    pass
                            break
                
                if not conversation_id:
                    conversation_id = str(uuid.uuid4())
                
                request_data['conversation_id'] = conversation_id
                
                pending.append({
                    "preview_id": preview_id,
                    "created_at": preview.created_at,
                    "preview_url": f"/preview/{preview_id}",
                    "request_data": request_data,
                    "generated_content": preview.generated_content
                })
        return pending

# 创建全局预览服务实例
preview_service = PreviewService()