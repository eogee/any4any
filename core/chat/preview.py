import time
import logging
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
            current_request = ""
            if preview.request_data and "messages" in preview.request_data:
                messages = preview.request_data["messages"]
                # 遍历消息列表，找到最后一个用户消息
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        current_request = msg.get("content", "")
                        break
            
            # 获取conversation_id和message_id
            # 首先尝试从request_data的messages列表中查找最后一个消息的message_id
            # 然后从messages表中获取对应的conversation_id
            message_id = None
            conversation_id = None
            
            # 尝试从request_data中直接获取
            if preview.request_data:
                # 优先从request_data中直接获取
                conversation_id = preview.request_data.get("conversation_id")
                message_id = preview.request_data.get("message_id")
                
                # 如果没有直接获取到，尝试从messages列表中提取
                if not message_id and "messages" in preview.request_data:
                    messages = preview.request_data["messages"]
                    # 找到最后一条消息
                    if messages and isinstance(messages[-1], dict):
                        message_id = messages[-1].get("id") or messages[-1].get("message_id")
                
                # 如果仍然没有获取到，尝试根据消息内容查询数据库
                if not conversation_id or not message_id:
                    try:
                        # 使用Preview模型的数据库连接来查询
                        if message_id:
                            # 如果有message_id，直接查询对应的conversation_id
                            result = preview_model.fetch_one(
                                "SELECT conversation_id FROM messages WHERE message_id = %s",
                                (message_id,)
                            )
                            if result:
                                conversation_id = result.get("conversation_id")
                        elif current_request:
                            # 如果没有message_id但有current_request，尝试根据内容查询
                            result = preview_model.fetch_one(
                                "SELECT conversation_id, message_id FROM messages WHERE content LIKE %s ORDER BY timestamp DESC LIMIT 1",
                                (f"%{current_request[:100]}%",)  # 使用内容的前100个字符作为模糊查询条件
                            )
                            if result:
                                conversation_id = result.get("conversation_id")
                                message_id = result.get("message_id")
                    except Exception as db_error:
                        logging.warning(f"Failed to query conversation_id and message_id: {db_error}")
            
            # 如果以上方法都没有获取到，才生成默认值
            # 使用与messages表一致的UUID格式
            import uuid
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            if not message_id:
                message_id = str(uuid.uuid4())
            
            # 计算响应时间（如果preview对象有response_time属性则使用，否则计算）
            if hasattr(preview, 'response_time'):
                response_time = preview.response_time
            else:
                # 估算响应时间：从创建时间到现在
                response_time = time.time() - preview.created_at
            
            # 从request_data中尝试获取user_id，默认为1
            user_id = preview.request_data.get("user_id", 1)
            
            # 保存到数据库，包括编辑前内容、编辑后内容、请求数据等
            preview_model.save_preview_content(
                preview_id=preview_id,
                saved_content=edited_content,  # 对应数据库中的saved_content
                pre_content=pre_content,
                full_request=preview.request_data,
                current_request=current_request,  # 对应数据库中的current_request
                conversation_id=conversation_id,
                message_id=message_id,
                response_time=response_time,
                user_id=user_id
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
    
    def register_confirm_callback(self, callback: Callable):
        """注册预览确认回调函数"""
        if callback not in self._confirm_callbacks:
            self._confirm_callbacks.append(callback)
            logging.info(f"Preview confirm callback registered: {callback.__name__}")
    
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
        
        # 触发所有注册的回调函数
        for callback in self._confirm_callbacks:
            try:
                # 异步调用回调函数
                await callback(preview_id, final_content, request_data)
            except Exception as e:
                logging.error(f"Error in preview confirm callback {callback.__name__}: {e}")
        
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
                # 创建request_data的副本，避免直接修改原始数据
                request_data = preview.request_data.copy() if preview.request_data else {}
                
                # 尝试获取或生成conversation_id
                conversation_id = None
                
                # 1. 尝试从request_data中直接获取
                if 'conversation_id' in request_data:
                    conversation_id = request_data['conversation_id']
                
                # 2. 如果没有，尝试从messages列表中查找最后一个用户消息的内容，然后查询对应的conversation_id
                elif request_data and 'messages' in request_data:
                    # 查找最后一个用户消息
                    last_user_message = None
                    for msg in reversed(request_data['messages']):
                        if isinstance(msg, dict) and msg.get('role') == 'user':
                            last_user_message = msg.get('content', '')
                            break
                    
                    if last_user_message:
                        try:
                            # 导入必要的模块
                            from data_models.Preview import Preview
                            import logging
                            
                            # 使用Preview模型查询conversation_id
                            preview_model = Preview()
                            # 根据消息内容查询最近的conversation_id
                            result = preview_model.fetch_one(
                                "SELECT conversation_id FROM messages WHERE content LIKE %s ORDER BY timestamp DESC LIMIT 1",
                                (f"%{last_user_message[:100]}%",)  # 使用内容的前100个字符作为模糊查询条件
                            )
                            if result:
                                conversation_id = result.get('conversation_id')
                        except Exception as db_error:
                            # 只记录警告级别日志，不影响功能
                            logging.warning(f"Failed to query conversation_id for preview {preview_id}: {db_error}")
                
                # 3. 如果仍然没有找到，生成一个新的UUID格式的conversation_id
                if not conversation_id:
                    import uuid
                    conversation_id = str(uuid.uuid4())
                
                # 将conversation_id添加到request_data中
                request_data['conversation_id'] = conversation_id
                
                pending.append({
                    "preview_id": preview_id,
                    "created_at": preview.created_at,
                    "preview_url": f"/preview/{preview_id}",
                    "request_data": request_data,  # 使用添加了conversation_id的request_data
                    "generated_content": preview.generated_content,  # 修改为完整内容
                    "generated_content_preview": preview.generated_content
                })
        return pending

# 创建全局预览服务实例
preview_service = PreviewService()
