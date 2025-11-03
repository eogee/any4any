import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse
from servers.Server import Server
from data_models.Preview import Preview

logger = logging.getLogger(__name__)

async def check_user_login(request: Request):
    """检查用户是否已登录"""
    if hasattr(request, 'session') and request.session.get('logged_in'):
        return True
    return False

def get_login_redirect():
    """获取登录重定向响应"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url='/login', status_code=302)

class PreviewServer(Server):
    """预览服务器 - 处理已回复预览相关功能"""

    def __init__(self):
        super().__init__()
        self.preview_model = None

    def _get_preview_model(self):
        """获取预览数据模型实例"""
        if not self.preview_model:
            self.preview_model = Preview()
        return self.preview_model

    async def get_preview_page(self, request: Request):
        """已回复预览列表页面"""
        try:
            with open(os.path.join("static", "preview", "preview.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return JSONResponse({"error": "Page not found"}, status_code=404)
        except Exception as e:
            logger.error(f"Failed to load preview page: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    async def get_preview_list_api(self, request: Request, page: int = Query(1, ge=1),
                                 limit: int = Query(20, ge=1, le=100),
                                 user_nick: str = Query(None),
                                 date_range: str = Query("all"),
                                 search: str = Query(None)):
        """获取预览列表API"""
        try:
            preview_model = self._get_preview_model()

            # 解析时间范围
            start_date_str, end_date_str = preview_model.parse_date_range(date_range)

            # 获取分页数据
            result = preview_model.get_previews_paginated(
                page=page,
                limit=limit,
                user_nick=user_nick,
                start_date=start_date_str,
                end_date=end_date_str,
                search=search
            )

            return JSONResponse(result)

        except Exception as e:
            logger.error(f"Failed to get preview list: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    async def get_preview_stats_api(self, request: Request):
        """获取预览统计数据API"""
        try:
            preview_model = self._get_preview_model()
            preview_count = preview_model.get_previews_count()
            return JSONResponse({"count": preview_count})
        except Exception as e:
            logger.error(f"Failed to get preview stats: {e}")
            return JSONResponse({"count": 0})

    async def get_unique_users_api(self, request: Request):
        """获取唯一用户列表API"""
        try:
            preview_model = self._get_preview_model()
            users = preview_model.get_unique_users()
            return JSONResponse({"users": users})
        except Exception as e:
            logger.error(f"Failed to get unique users: {e}")
            return JSONResponse({"users": []})

    
    def register_routes(self, app: FastAPI):
        """注册路由"""

        async def require_login(request: Request):
            """登录检查装饰器"""
            if not await check_user_login(request):
                return get_login_redirect()
            return None

        @app.get("/preview", response_class=HTMLResponse)
        async def preview_page(request: Request):
            """已回复预览列表页面"""
            if redirect := await require_login(request):
                return redirect
            return await self.get_preview_page(request)

        @app.get("/api/preview/list")
        async def preview_list_api(
            request: Request,
            page: int = Query(1, ge=1),
            limit: int = Query(20, ge=1, le=100),
            user_nick: str = Query(None),
            date_range: str = Query("all"),
            search: str = Query(None)
        ):
            """预览列表API"""
            if redirect := await require_login(request):
                return redirect
            return await self.get_preview_list_api(request, page, limit, user_nick, date_range, search)

        @app.get("/api/stats/preview")
        async def preview_stats_api(request: Request):
            """预览统计数据API"""
            if redirect := await require_login(request):
                return redirect
            return await self.get_preview_stats_api(request)

        @app.get("/api/users/unique")
        async def unique_users_api(request: Request):
            """获取唯一用户列表API"""
            if redirect := await require_login(request):
                return redirect
            return await self.get_unique_users_api(request)

        