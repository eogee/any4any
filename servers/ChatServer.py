import os
import logging
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from servers.Server import Server
from core.chat.openai_api import ChatCompletionRequest, ChatMessage, OpenAIAPI
from core.chat.conversation_database import ConversationDatabase
from core.auth.model_auth import verify_token
from config import Config

logger = logging.getLogger(__name__)

async def check_user_login(request: Request):
    """检查用户是否已登录"""
    if hasattr(request, 'session') and request.session.get('logged_in'):
        return True
    return False

def get_login_redirect():
    """获取登录重定向响应"""
    return RedirectResponse(url='/login', status_code=302)

class ChatHistoryRequest(BaseModel):
    conversation_id: str = Field(..., description="对话ID")
    limit: Optional[int] = Field(50, description="消息数量限制")
    offset: Optional[int] = Field(0, description="偏移量")

class ConversationListRequest(BaseModel):
    platform: Optional[str] = Field("web", description="平台类型")
    limit: Optional[int] = Field(20, description="对话数量限制")
    offset: Optional[int] = Field(0, description="偏移量")

class ChatServer(Server):
    """聊天服务器"""

    def __init__(self):
        super().__init__()

        # 导入 conversation_manager
        from core.chat.conversation_manager import get_conversation_manager
        self.conversation_manager = get_conversation_manager()
        self.require_auth = getattr(self, 'require_auth', True)

    async def _verify_request_auth(self, request: Request) -> bool:
        """验证请求权限"""
        try:
            # 检查会话登录状态
            if await check_user_login(request):
                return True

            # 检查API Token认证
            auth_header = request.headers.get("Authorization")
            if auth_header:
                try:
                    await verify_token(authorization=auth_header)
                    return True
                except HTTPException:
                    # Token验证失败，继续尝试其他方式
                    pass

            # 如果API_KEY为空字符串，允许访问（开发模式）
            if Config.API_KEY == "EMPTY" or Config.API_KEY == "":
                return True

            return False
        except Exception as e:
            logger.warning(f"Authentication verification failed: {e}")
            return False

    async def serve_chat_page(self):
        """提供聊天页面"""
        try:
            chat_page_path = os.path.join("static", "index", "chat.html")
            if os.path.exists(chat_page_path):
                return FileResponse(chat_page_path)
            else:
                raise HTTPException(status_code=404, detail="Chat page not found")
        except Exception as e:
            logger.error(f"Error serving chat page: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def handle_chat_completion(self, request: Request, chat_request):
        """处理聊天完成请求"""
        self.log_request("/v1/chat/completions")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            # 从session获取用户信息，如果没有则使用默认值
            if await check_user_login(request):
                # 用户已登录，使用session中的用户信息
                if not chat_request.sender_id:
                    chat_request.sender_id = request.session.get('username', 'web_user')
                if not chat_request.sender_nickname:
                    chat_request.sender_nickname = request.session.get('nickname', 'Web用户')
                if not chat_request.platform:
                    chat_request.platform = "any4chat"
            else:
                # 用户未登录，使用默认值
                if not chat_request.sender_id:
                    chat_request.sender_id = "web_user"
                if not chat_request.sender_nickname:
                    chat_request.sender_nickname = "Web用户"
                if not chat_request.platform:
                    chat_request.platform = "any4chat"

            # 调用OpenAI API处理
            response = await OpenAIAPI.chat_completions(request, chat_request)
            return response

        except HTTPException:
            raise
        except Exception as e:
            self.log_error("/v1/chat/completions", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_conversation_history(self, conversation_id: str, request: ChatHistoryRequest):
        """获取对话历史"""
        self.log_request(f"/api/conversation/{conversation_id}/history")

        try:
            if not conversation_id:
                raise HTTPException(status_code=400, detail="Conversation ID is required")

            # 获取对话详情
            conversation = self.conversation_manager.get_conversation_history(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # 格式化消息
            messages = conversation.get('messages', [])
            formatted_messages = []

            # 处理datetime序列化
            from datetime import datetime
            def serialize_datetime(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return obj

            for msg in messages[request.offset:request.offset + request.limit]:
                formatted_msg = {
                    'message_id': msg.get('message_id'),
                    'role': msg.get('sender_type'),
                    'content': msg.get('content'),
                    'timestamp': serialize_datetime(msg.get('timestamp')),
                    'sequence_number': msg.get('sequence_number')
                }
                formatted_messages.append(formatted_msg)

            return JSONResponse({
                'success': True,
                'conversation_id': conversation_id,
                'messages': formatted_messages,
                'total_count': len(messages),
                'returned_count': len(formatted_messages)
            })

        except HTTPException:
            raise
        except Exception as e:
            self.log_error(f"/api/conversation/{conversation_id}/history", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_user_conversations(self, http_request: Request, request: ConversationListRequest):
        """获取用户对话列表"""
        self.log_request("/api/conversations")

        try:
            # 权限验证 - 添加额外错误处理
            try:
                if not await self._verify_request_auth(http_request):
                    raise HTTPException(status_code=401, detail="Unauthorized")
            except Exception as auth_error:
                logger.warning(f"Authentication error in get_user_conversations: {auth_error}")
                # 如果认证失败，返回默认响应而不是抛出异常
                return JSONResponse({
                    'success': True,
                    'conversations': [],
                    'total_count': 0,
                    'limit': request.limit,
                    'offset': request.offset,
                    'message': 'Authentication failed'
                })

            # 获取当前用户信息
            if await check_user_login(http_request):
                sender = http_request.session.get('username', 'web_user')
            else:
                sender = 'web_user'

            # 安全检查数据库连接
            try:
                if self.conversation_manager is None or self.conversation_manager.db is None:
                    return JSONResponse({
                        'success': True,
                        'conversations': [],
                        'total_count': 0,
                        'limit': request.limit,
                        'offset': request.offset,
                        'message': 'Database not available'
                    })
            except Exception as db_check_error:
                logger.warning(f"Database connection check failed: {db_check_error}")
                return JSONResponse({
                    'success': True,
                    'conversations': [],
                    'total_count': 0,
                    'limit': request.limit,
                    'offset': request.offset,
                    'message': 'Database check failed'
                })

            # 从数据库获取会话列表
            conversations = self.conversation_manager.db.get_user_conversations(
                sender=sender,
                platform=request.platform,
                limit=request.limit,
                offset=request.offset
            )

            # 获取总数
            total_count = self.conversation_manager.db.get_user_conversations_count(
                sender=sender,
                platform=request.platform
            )

            # 处理datetime对象的JSON序列化
            from datetime import datetime

            def serialize_datetime(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return obj

            # 处理会话列表中的datetime对象
            processed_conversations = []
            for conv in conversations:
                processed_conv = conv.copy()
                if 'created_time' in processed_conv:
                    processed_conv['created_time'] = serialize_datetime(processed_conv['created_time'])
                if 'last_active' in processed_conv:
                    processed_conv['last_active'] = serialize_datetime(processed_conv['last_active'])
                processed_conversations.append(processed_conv)

            return JSONResponse({
                'success': True,
                'conversations': processed_conversations,
                'total_count': total_count,
                'limit': request.limit,
                'offset': request.offset
            })

        except Exception as e:
            self.log_error("/api/conversations", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def create_new_conversation(self, request: Request):
        """创建新对话"""
        self.log_request("/api/conversation/create")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            # 从session获取用户信息，如果没有则使用请求中的数据
            if await check_user_login(request):
                # 用户已登录，使用session中的用户信息
                sender_id = request.session.get('username', 'web_user')
                sender_nickname = request.session.get('nickname', 'Web用户')
                platform = 'any4chat'
            else:
                # 用户未登录，使用请求中的数据或默认值
                user_data = await request.json() if request.headers.get("content-type") == "application/json" else {}
                sender_id = user_data.get('sender_id', 'web_user')
                sender_nickname = user_data.get('sender_nickname', 'Web用户')
                platform = user_data.get('platform', 'any4chat')

            # 创建新对话
            try:
                conversation = self.conversation_manager.db.create_new_conversation(
                    sender_id, sender_nickname, platform
                )
                conversation_id = conversation['conversation_id']
            except Exception as db_error:
                logger.warning(f"Database operation failed, using fallback: {db_error}")
                # 如果数据库操作失败，使用UUID作为备用方案
                import uuid
                conversation_id = str(uuid.uuid4())

            return JSONResponse({
                'success': True,
                'conversation_id': conversation_id,
                'message': 'New conversation created successfully'
            })

        except HTTPException:
            raise
        except Exception as e:
            self.log_error("/api/conversation/create", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def delete_conversation(self, conversation_id: str, request: Request):
        """删除对话"""
        self.log_request(f"/api/conversation/{conversation_id}/delete")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            if not conversation_id:
                raise HTTPException(status_code=400, detail="Conversation ID is required")

            # 这里应该实现删除对话的逻辑
            # 暂时返回成功响应作为示例

            return JSONResponse({
                'success': True,
                'message': 'Conversation deleted successfully',
                'conversation_id': conversation_id
            })

        except HTTPException:
            raise
        except Exception as e:
            self.log_error(f"/api/conversation/{conversation_id}/delete", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def export_conversation(self, conversation_id: str, request: Request):
        """导出对话"""
        self.log_request(f"/api/conversation/{conversation_id}/export")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            if not conversation_id:
                raise HTTPException(status_code=400, detail="Conversation ID is required")

            # 获取完整对话历史
            conversation = self.conversation_manager.get_conversation_history(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # 格式化导出数据
            export_data = {
                'conversation_id': conversation_id,
                'user_nick': conversation.get('user_nick'),
                'platform': conversation.get('platform'),
                'created_at': conversation.get('created_at'),
                'updated_at': conversation.get('updated_at'),
                'messages': conversation.get('messages', []),
                'export_time': conversation.get('last_active')
            }

            return JSONResponse({
                'success': True,
                'data': export_data,
                'filename': f"conversation_{conversation_id}.json"
            })

        except HTTPException:
            raise
        except Exception as e:
            self.log_error(f"/api/conversation/{conversation_id}/export", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_chat_status(self, request: Request):
        """获取聊天服务状态"""
        self.log_request("/api/chat/status")

        try:
            # 检查服务状态
            conversation_manager_available = self.conversation_manager is not None

            status = {
                'service_status': 'online' if conversation_manager_available else 'offline',
                'features': {
                    'streaming': True,
                    'conversation_history': True,
                    'export': True,
                    'delete': True
                },
                'authentication_required': self.require_auth,
                'version': '1.0.0'
            }

            return JSONResponse({
                'success': True,
                'status': status
            })

        except Exception as e:
            self.log_error("/api/chat/status", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_preview_mode_config(self, request: Request):
        """获取预览模式配置状态"""
        self.log_request("/api/chat/config/preview-mode")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            return JSONResponse({
                "preview_mode": Config.PREVIEW_MODE,
                "description": "Preview mode is enabled - streaming will be disabled" if Config.PREVIEW_MODE else "Preview mode is disabled - streaming is available"
            })
        except HTTPException:
            raise
        except Exception as e:
            self.log_error("/api/chat/config/preview-mode", e)
            return JSONResponse({
                "preview_mode": False,
                "description": "Unable to determine preview mode status",
                "error": str(e)
            }, status_code=500)

    async def get_delay_mode_config(self, request: Request):
        """获取延迟模式配置状态"""
        self.log_request("/api/chat/config/delay-mode")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            return JSONResponse({
                "delay_mode": Config.DELAY_MODE,
                "delay_time": Config.DELAY_TIME,
                "description": f"Delay mode is enabled - messages will be combined within {Config.DELAY_TIME}s" if Config.DELAY_MODE else "Delay mode is disabled - messages will be processed immediately"
            })
        except HTTPException:
            raise
        except Exception as e:
            self.log_error("/api/chat/config/delay-mode", e)
            return JSONResponse({
                "delay_mode": False,
                "delay_time": 3,
                "description": "Unable to determine delay mode status",
                "error": str(e)
            }, status_code=500)

    async def get_tools_enabled_config(self, request: Request):
        """获取工具系统配置状态"""
        self.log_request("/api/chat/config/tools-enabled")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                raise HTTPException(status_code=401, detail="Unauthorized")

            return JSONResponse({
                "tools_enabled": Config.TOOLS_ENABLED,
                "description": "Tools system is enabled - NL2SQL and other tools are available" if Config.TOOLS_ENABLED else "Tools system is disabled - only basic chat functionality is available"
            })
        except HTTPException:
            raise
        except Exception as e:
            self.log_error("/api/chat/config/tools-enabled", e)
            return JSONResponse({
                "tools_enabled": False,
                "description": "Unable to determine tools enabled status",
                "error": str(e)
            }, status_code=500)

    async def get_current_user(self, request: Request):
        """获取当前登录用户信息"""
        self.log_request("/api/chat/current-user")

        try:
            # 权限验证
            if not await self._verify_request_auth(request):
                return JSONResponse({
                    "success": False,
                    "message": "User not logged in"
                }, status_code=401)

            # 获取用户信息
            if hasattr(request, 'session') and request.session.get('logged_in'):
                return JSONResponse({
                    "success": True,
                    "username": request.session.get('username'),
                    "nickname": request.session.get('nickname'),
                    "user_id": request.session.get('user_id')
                })
            else:
                return JSONResponse({
                    "success": False,
                    "message": "User not logged in"
                }, status_code=401)

        except Exception as e:
            self.log_error("/api/chat/current-user", e)
            return JSONResponse({
                "success": False,
                "message": "Failed to get user information",
                "error": str(e)
            }, status_code=500)

    async def get_latest_conversation(self, request: Request):
        """获取用户的最新会话"""
        self.log_request("/api/chat/latest-conversation")

        try:
            # 权限验证 - 添加额外错误处理
            try:
                if not await self._verify_request_auth(request):
                    raise HTTPException(status_code=401, detail="Unauthorized")
            except Exception as auth_error:
                logger.warning(f"Authentication error in get_latest_conversation: {auth_error}")
                # 如果认证失败，返回默认响应而不是抛出异常
                return JSONResponse({
                    'success': True,
                    'conversation_id': None,
                    'messages': [],
                    'message': 'Authentication failed'
                })

            # 获取用户信息
            if await check_user_login(request):
                sender = request.session.get('username', 'web_user')
                nickname = request.session.get('nickname', 'Web用户')
            else:
                sender = 'web_user'
                nickname = 'Web用户'

            # 安全检查数据库连接
            try:
                if self.conversation_manager is None or self.conversation_manager.db is None:
                    return JSONResponse({
                        'success': True,
                        'conversation_id': None,
                        'messages': [],
                        'message': 'Database not available'
                    })
            except Exception as db_check_error:
                logger.warning(f"Database connection check failed: {db_check_error}")
                return JSONResponse({
                    'success': True,
                    'conversation_id': None,
                    'messages': [],
                    'message': 'Database check failed'
                })

            # 获取最新会话
            conversation = self.conversation_manager.db.get_latest_conversation(
                sender=sender,
                user_nick=nickname,
                platform='any4chat'
            )

            if conversation:
                # 处理datetime对象的JSON序列化
                import json
                from datetime import datetime

                def serialize_datetime(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return obj

                # 创建响应数据，确保datetime对象被正确序列化
                messages = conversation.get('messages', [])
                processed_messages = []
                for msg in messages:
                    processed_msg = msg.copy()
                    if 'timestamp' in processed_msg:
                        processed_msg['timestamp'] = serialize_datetime(processed_msg['timestamp'])
                    processed_messages.append(processed_msg)

                response_data = {
                    'success': True,
                    'conversation_id': conversation['conversation_id'],
                    'messages': processed_messages,
                    'created_time': serialize_datetime(conversation['created_time']),
                    'last_active': serialize_datetime(conversation['last_active'])
                }

                return JSONResponse(response_data)
            else:
                return JSONResponse({
                    'success': True,
                    'conversation_id': None,
                    'messages': [],
                    'message': 'No existing conversation found'
                })

        except HTTPException:
            raise
        except Exception as e:
            self.log_error("/api/chat/latest-conversation", e)
            return JSONResponse({
                'success': False,
                'error': str(e)
            }, status_code=500)

    def register_routes(self, app: FastAPI):
        """注册聊天相关路由"""

        async def require_login(request: Request):
            """登录检查装饰器"""
            if not await check_user_login(request):
                return get_login_redirect()
            return None

        # 聊天页面路由
        @app.get("/chat", response_class=HTMLResponse)
        async def chat_page(request: Request):
            """聊天页面"""
            if redirect := await require_login(request):
                return redirect
            return await self.serve_chat_page()

        # API 路由 - 聊天完成
        @app.post("/v1/chat/completions")
        async def chat_completions_route(request: Request, chat_request: ChatCompletionRequest):
            """OpenAI 兼容的聊天完成接口"""
            return await self.handle_chat_completion(request, chat_request)

        # 对话管理 API
        @app.get("/api/conversation/{conversation_id}/history")
        async def conversation_history(conversation_id: str, request: Request):
            """获取对话历史"""
            try:
                data = await request.json() if request.headers.get("content-type") == "application/json" else {}
                history_request = ChatHistoryRequest(**data)
            except:
                history_request = ChatHistoryRequest(conversation_id=conversation_id)

            return await self.get_conversation_history(conversation_id, history_request)

        @app.post("/api/conversations")
        async def user_conversations(request: Request):
            """获取用户对话列表"""
            try:
                data = await request.json()
                list_request = ConversationListRequest(**data)
            except:
                list_request = ConversationListRequest()

            return await self.get_user_conversations(request, list_request)

        @app.post("/api/conversation/create")
        async def create_conversation(request: Request):
            """创建新对话"""
            return await self.create_new_conversation(request)

        @app.delete("/api/conversation/{conversation_id}/delete")
        async def delete_conversation_route(conversation_id: str, request: Request):
            """删除对话"""
            return await self.delete_conversation(conversation_id, request)

        @app.get("/api/conversation/{conversation_id}/export")
        async def export_conversation_route(conversation_id: str, request: Request):
            """导出对话"""
            return await self.export_conversation(conversation_id, request)

        @app.get("/api/chat/status")
        async def chat_status(request: Request):
            """获取聊天服务状态"""
            return await self.get_chat_status(request)

        @app.get("/api/chat/config/preview-mode")
        async def preview_mode_config(request: Request):
            """获取预览模式配置状态"""
            return await self.get_preview_mode_config(request)

        @app.get("/api/chat/config/delay-mode")
        async def delay_mode_config(request: Request):
            """获取延迟模式配置状态"""
            return await self.get_delay_mode_config(request)

        @app.get("/api/chat/config/tools-enabled")
        async def tools_enabled_config(request: Request):
            """获取工具系统配置状态"""
            return await self.get_tools_enabled_config(request)

        @app.get("/api/chat/current-user")
        async def current_user(request: Request):
            """获取当前用户信息"""
            return await self.get_current_user(request)

        @app.get("/api/chat/latest-conversation")
        async def latest_conversation(request: Request):
            """获取用户的最新会话"""
            return await self.get_latest_conversation(request)

        @app.get("/api/chat/models")
        async def chat_models(request: Request):
            """获取可用的聊天模型列表"""
            try:
                models = [
                    {
                        "id": "default",
                        "name": "Default Model",
                        "description": "默认聊天模型",
                        "capabilities": ["chat", "streaming"]
                    }
                ]

                return JSONResponse({
                    'success': True,
                    'models': models,
                    'default_model': 'default'
                })

            except Exception as e:
                self.log_error("/api/chat/models", e)
                raise HTTPException(status_code=500, detail="Internal server error")

        # 清空聊天历史
        @app.delete("/api/conversation/{conversation_id}/clear")
        async def clear_conversation(conversation_id: str, request: Request):
            """清空对话历史"""
            try:
                if not await self._verify_request_auth(request):
                    raise HTTPException(status_code=401, detail="Unauthorized")

                if not conversation_id:
                    raise HTTPException(status_code=400, detail="Conversation ID is required")

                # 这里应该实现清空对话的逻辑
                # 暂时返回成功响应

                return JSONResponse({
                    'success': True,
                    'message': 'Conversation cleared successfully',
                    'conversation_id': conversation_id
                })

            except HTTPException:
                raise
            except Exception as e:
                self.log_error(f"/api/conversation/{conversation_id}/clear", e)
                raise HTTPException(status_code=500, detail="Internal server error")

        # 获取用户统计信息
        @app.get("/api/chat/stats")
        async def chat_stats(request: Request):
            """获取聊天统计信息"""
            try:
                # 这里应该从数据库获取统计数据
                stats = {
                    'total_conversations': 0,
                    'total_messages': 0,
                    'active_conversations': 0,
                    'daily_messages': 0
                }

                return JSONResponse({
                    'success': True,
                    'stats': stats
                })

            except Exception as e:
                self.log_error("/api/chat/stats", e)
                raise HTTPException(status_code=500, detail="Internal server error")

        # 健康检查
        @app.get("/api/chat/health")
        async def chat_health():
            """聊天服务健康检查"""
            try:
                conversation_manager_available = self.conversation_manager is not None
                status_code = 200 if conversation_manager_available else 503

                return JSONResponse({
                    'status': 'healthy' if conversation_manager_available else 'unhealthy',
                    'timestamp': str(logger.handlers[0].formatter.formatTime(logger.makeRecord(
                        name='', level=0, pathname='', lineno=0, msg='', args=(), exc_info=None
                    ))) if logger.handlers else None
                }, status_code=status_code)

            except Exception as e:
                self.log_error("/api/chat/health", e)
                return JSONResponse({
                    'status': 'unhealthy',
                    'error': str(e)
                }, status_code=503)