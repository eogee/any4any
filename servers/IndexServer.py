import os
import logging
import traceback
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from core.chat.preview import preview_service
from servers.Server import Server
from core.chat.conversation_database import ConversationDatabase

# 配置日志
logger = logging.getLogger(__name__)

# 用于检查用户是否登录的装饰器
async def check_user_login(request: Request):
    """
    检查用户是否已登录
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        bool: 是否已登录
    """
    if hasattr(request, 'session'):
        # 检查session中是否包含登录信息
        if request.session.get('logged_in'):
            return True
    return False

# 用于获取登录页面的重定向响应
def get_login_redirect():
    """
    获取重定向到登录页面的响应
    
    Returns:
        RedirectResponse: 重定向到登录页面的响应对象
    """
    return RedirectResponse(url='/login', status_code=302)

class IndexServer(Server):
    """
    首页服务器类，负责处理首页及预览相关路由
    """
    def __init__(self):
        super().__init__()
        
    async def get_pending_previews(self):
        """获取所有等待确认的预览列表"""
        try:
            pending_previews = await preview_service.get_pending_previews()
            return JSONResponse(pending_previews)
        except Exception as e:
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def get_preview(self, preview_id: str):
        """获取预览详情"""
        try:
            preview = await preview_service.get_preview(preview_id)
            return JSONResponse({
                "preview_id": preview.preview_id,
                "request": preview.request_data,
                "status": "preview"
            })
        except Exception as e:
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def confirm_preview(self, preview_id: str):
        """确认预览请求并返回最终响应"""
        try:
            # 调用preview_service的confirm_preview方法
            # 注意：如果message_manager.py中已正确注册了回调，
            # 这里的调用会自动触发预览确认后的钉钉消息发送
            response = await preview_service.confirm_preview(preview_id)
            
            # 添加日志记录，用于调试
            logging.info(f"Preview confirmed for ID: {preview_id}")
            
            return JSONResponse(response)
        except Exception as e:
            # 添加错误日志记录
            logging.error(f"Error confirming preview {preview_id}: {str(e)}")
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def get_preview_data(self, preview_id: str):
        """获取预览数据"""
        try:
            preview = await preview_service.get_preview(preview_id)
            
            # 创建一个request_data的副本，避免直接修改原始数据
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
                        # 使用ConversationDatabase查询conversation_id
                        db = ConversationDatabase()
                        # 根据消息内容查询最近的conversation_id
                        result = db.fetch_one(
                            "SELECT conversation_id FROM messages WHERE content LIKE %s ORDER BY timestamp DESC LIMIT 1",
                            (f"%{last_user_message[:100]}%",)  # 使用内容的前100个字符作为模糊查询条件
                        )
                        if result:
                            conversation_id = result.get('conversation_id')
                    except Exception as db_error:
                        logging.warning(f"Failed to query conversation_id: {db_error}")
            
            # 3. 如果仍然没有找到，生成一个新的UUID格式的conversation_id
            if not conversation_id:
                import uuid
                conversation_id = str(uuid.uuid4())
            
            # 将conversation_id添加到request_data中
            request_data['conversation_id'] = conversation_id
            
            return JSONResponse({
                "preview_id": preview.preview_id,
                "request": request_data,
                "generated_content": preview.generated_content,
                "edited_content": preview.edited_content,
                "status": "preview"
            })
        except Exception as e:
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def update_preview_content(self, preview_id: str, request: Request):
        """更新保存预览内容"""
        try:
            data = await request.json()
            edited_content = data.get("content", "")
            # 从request中获取session
            session = request.session or {}
            await preview_service.update_content(preview_id, edited_content, session)
            return JSONResponse({
                "status": "success",
                "message": "Content updated successfully"
            })
        except Exception as e:
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def get_final_result(self, preview_id: str):
        """获取预览确认后的最终结果"""
        try:
            preview = await preview_service.get_preview(preview_id)
            if not preview.confirmed:
                return JSONResponse({
                    "status": "waiting",
                    "message": "Preview not confirmed yet",
                    "preview_url": f"/preview/{preview_id}"
                })
            
            # 返回确认后的最终响应
            return JSONResponse(preview.response_data)
        except Exception as e:
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def get_conversation_messages(self, conversation_id: str):
        """
        获取指定conversation_id的所有消息数据
        根据需求优化为简洁高效的查询，返回会话信息和按时间排序的消息列表
        """
        logging.info(f"Start querying conversation messages - conversation_id: {conversation_id}")
        
        # 验证conversation_id参数
        if not conversation_id or not isinstance(conversation_id, str):
            error_msg = f"Invalid conversation_id: {conversation_id} (type: {type(conversation_id).__name__})"
            logging.error(f"{error_msg}")
            return JSONResponse({
                "success": False,
                "error": error_msg,
                "error_type": "invalid_parameter"
            }, status_code=400)
        
        try:
            # 创建数据库实例
            db = ConversationDatabase()
            
            # 直接获取完整的会话数据
            conversation = db.get_conversation_by_id(conversation_id)
            
            if not conversation:
                logging.error(f"Conversation ID {conversation_id} not found")
                return JSONResponse({
                    "success": False,
                    "error": "Conversation not found",
                    "error_type": "not_found"
                }, status_code=404)
            
            # 处理会话对象中的datetime字段，确保可以JSON序列化
            def safe_serialize(value):
                if hasattr(value, 'isoformat'):
                    return value.isoformat()
                return value
                
            # 构建所需的返回结构，处理所有可能的datetime字段
            conversation_info = {
                "conversation_id": conversation.get("conversation_id"),
                "user_nick": conversation.get("user_nick"),
                "platform": conversation.get("platform"),
                "message_count": conversation.get("message_count", 0)
            }
            
            # 检查并序列化可能存在的datetime字段
            for field in ['created_at', 'updated_at', 'last_message_time']:
                if field in conversation:
                    conversation_info[field] = safe_serialize(conversation[field])
            
            # 获取并格式化消息列表
            messages = conversation.get("messages", [])
            
            logging.info(f"Successfully retrieved message list, total {len(messages)} messages")
            
            # 返回规范化的响应格式
            return JSONResponse({
                "success": True,
                "conversation_info": conversation_info,
                "messages": messages
            })
            
        except ConnectionError as conn_error:
            error_message = f"Database connection error: {str(conn_error)}"
            logging.critical(f"{error_message}")
            return JSONResponse({
                "success": False,
                "error": "Database connection failed, please check if database service is running",
                "error_type": "connection_error"
            }, status_code=503)
            
        except Exception as e:
            logging.error(f"Error occurred while querying conversation messages: {str(e)}")
            return JSONResponse({
                "success": False,
                "error": "Internal server error, please try again later",
                "error_type": type(e).__name__
            }, status_code=500)
        
    def register_routes(self, app: FastAPI):
        """
        注册首页及预览相关路由
        
        Args:
            app: FastAPI应用实例
        """
        # 首页路由
        @app.get("/", response_class=HTMLResponse)
        async def read_root(request: Request):
            """
            处理首页请求，返回index.html内容
            """
            # 检查用户是否已登录
            if not await check_user_login(request):
                return get_login_redirect()
            
            with open(os.path.join("static", "index", "index.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
            
        @app.get("/index", response_class=HTMLResponse)
        async def read_index(request: Request):
            """
            处理/index请求，返回index.html内容
            """
            # 检查用户是否已登录
            if not await check_user_login(request):
                return get_login_redirect()
            
            with open(os.path.join("static", "index", "index.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
            
        # 预览相关路由 - 需要登录才能访问
        @app.get("/api/pending-previews")
        async def pending_previews(request: Request):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_pending_previews()
            
        @app.get("/v1/chat/preview/{preview_id}")
        async def preview(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_preview(preview_id)
            
        # 支持GET和POST请求，确保预览确认能够正确处理
        @app.get("/v1/chat/confirm/{preview_id}")
        async def confirm_preview_route_get(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.confirm_preview(preview_id)
        
        @app.post("/v1/chat/confirm/{preview_id}")
        async def confirm_preview_route_post(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.confirm_preview(preview_id)
            
        @app.get("/api/preview/{preview_id}")
        async def preview_data(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_preview_data(preview_id)
            
        @app.post("/api/preview/{preview_id}/edit")
        async def update_preview_route(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            # 为update_preview_content方法提供request参数
            return await self.update_preview_content(preview_id, request)
            
        # 新增PUT路由，匹配前端使用的路径格式
        @app.put("/api/previews/{preview_id}")
        async def put_update_preview_route(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.update_preview_content(preview_id, request)
            
        @app.get("/v1/chat/completions/result/{preview_id}")
        async def preview_result(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_preview_data(preview_id)
            
        async def _handle_conversation_messages(request: Request, conversation_id: str):
            """处理会话消息请求的内部函数"""
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_conversation_messages(conversation_id)
            
        @app.get("/api/conversation/{conversation_id}/messages")
        async def conversation_messages(request: Request, conversation_id: str):
            """获取指定会话ID的所有消息"""
            return await _handle_conversation_messages(request, conversation_id)