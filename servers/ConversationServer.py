import os
import logging
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from servers.Server import Server
from data_models.Conversation import Conversation

logger = logging.getLogger(__name__)

async def check_user_login(request: Request):
    """检查用户是否已登录"""
    if hasattr(request, 'session') and request.session.get('logged_in'):
        return True
    return False

def get_login_redirect():
    """获取登录重定向响应"""
    return RedirectResponse(url='/login', status_code=302)

class ConversationServer(Server):
    """会话服务器 - 处理会话相关功能"""

    def __init__(self):
        super().__init__(log_init=True)
        self.conversation_model = None

    def _get_conversation_model(self):
        """获取会话数据模型实例"""
        if not self.conversation_model:
            self.conversation_model = Conversation()
        return self.conversation_model

    async def get_conversations_page(self, request: Request):
        """会话列表页面"""
        try:
            with open(os.path.join("static", "index", "conversations.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return JSONResponse({"error": "Page not found"}, status_code=404)
        except Exception as e:
            self.log_error("/conversations", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    async def get_conversation_detail_api(self, request: Request, conversation_id: str):
        """获取会话详情API"""
        try:
            conversation_model = self._get_conversation_model()

            # 获取会话基本信息
            conversation_query = f"""
                SELECT
                    c.*,
                    DATE_FORMAT(c.created_time, '%Y-%m-%d %H:%i:%s') as created_at_formatted,
                    DATE_FORMAT(c.last_active, '%Y-%m-%d %H:%i:%s') as last_active_formatted
                FROM conversations c
                WHERE c.conversation_id = '{conversation_id}'
            """

            conversation = conversation_model.fetch_one(conversation_query)

            if not conversation:
                return JSONResponse({"success": False, "error": "会话不存在"}, status_code=404)

            # 获取会话消息历史
            messages_query = f"""
                SELECT
                    message_id,
                    content,
                    sender_type,
                    is_timeout,
                    timestamp,
                    sequence_number,
                    DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:%s') as timestamp_formatted
                FROM messages
                WHERE conversation_id = '{conversation_id}'
                ORDER BY sequence_number ASC
            """

            messages = conversation_model.fetch_all(messages_query)

            # 处理datetime对象
            from data_models.Conversation import process_dict_datetime
            conversation = process_dict_datetime(conversation)
            messages = [process_dict_datetime(msg) for msg in messages]

            return JSONResponse({
                "success": True,
                "data": {
                    "conversation": conversation,
                    "messages": messages
                }
            })

        except Exception as e:
            self.log_error("/api/conversations/detail", e)
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    def register_routes(self, app: FastAPI):
        """注册路由"""

        async def require_login(request: Request):
            """登录检查装饰器"""
            if not await check_user_login(request):
                return get_login_redirect()
            return None

        conversation_model = self._get_conversation_model()

        # 页面路由
        @app.get("/conversations", response_class=HTMLResponse)
        async def conversations_page(request: Request):
            self.log_request("/conversations")
            login_check = await require_login(request)
            if login_check:
                return login_check
            return await self.get_conversations_page(request)

        # 使用基类的通用路由处理器创建API路由
        @app.get("/api/conversations/list")
        async def conversations_list_api(request: Request, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                                        user_nick: str = Query(None), platform: str = Query(None),
                                        date_range: str = Query("all")):
            login_check = await require_login(request)
            if login_check:
                return login_check

            # 解析时间范围
            start_date, end_date = self.parse_date_range(date_range)

            # 直接调用conversation_model的分页方法
            try:
                result = conversation_model.get_conversations_paginated(
                    page=page,
                    limit=limit,
                    user_nick=user_nick,
                    platform=platform,
                    start_date=start_date,
                    end_date=end_date
                )
                return JSONResponse(result)
            except Exception as e:
                self.log_error("/api/conversations/list", e)
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.get("/api/conversations/stats")
        async def conversations_stats_api(request: Request, user_nick: str = Query(None), platform: str = Query(None),
                                         date_range: str = Query("all")):
            login_check = await require_login(request)
            if login_check:
                return login_check

            # 解析时间范围
            start_date, end_date = self.parse_date_range(date_range)

            # 直接调用conversation_model的统计方法
            try:
                count = conversation_model.get_conversation_count(
                    user_nick=user_nick,
                    platform=platform,
                    start_date=start_date,
                    end_date=end_date
                )
                return JSONResponse({"count": count})
            except Exception as e:
                self.log_error("/api/conversations/stats", e)
                return JSONResponse({"count": 0})

        @app.get("/api/conversations/users")
        async def conversations_users_api(request: Request):
            login_check = await require_login(request)
            if login_check:
                return login_check

            try:
                users = conversation_model.get_unique_users()
                return JSONResponse({"users": users})
            except Exception as e:
                self.log_error("/api/conversations/users", e)
                return JSONResponse({"users": []})

        @app.get("/api/conversations/platforms")
        async def conversations_platforms_api(request: Request):
            login_check = await require_login(request)
            if login_check:
                return login_check

            try:
                platforms = conversation_model.get_unique_platforms()
                return JSONResponse({"platforms": platforms})
            except Exception as e:
                self.log_error("/api/conversations/platforms", e)
                return JSONResponse({"platforms": []})

        # 详情API - 获取会话详细信息和消息历史
        @app.get("/api/conversations/detail/{conversation_id}")
        async def conversation_detail_api(request: Request, conversation_id: str):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return await self.get_conversation_detail_api(request, conversation_id)

        logger.info("Conversation server routes registered successfully")