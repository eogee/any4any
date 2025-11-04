import os
import logging
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from servers.Server import Server
from data_models.Timeout import Timeout

logger = logging.getLogger(__name__)

async def check_user_login(request: Request):
    """检查用户是否已登录"""
    if hasattr(request, 'session') and request.session.get('logged_in'):
        return True
    return False

def get_login_redirect():
    """获取登录重定向响应"""
    return RedirectResponse(url='/login', status_code=302)

class TimeoutServer(Server):
    """超时响应服务器 - 处理超时响应相关功能"""

    def __init__(self):
        super().__init__(log_init=True)
        self.timeout_model = None

    def _get_timeout_model(self):
        """获取超时响应数据模型实例"""
        if not self.timeout_model:
            self.timeout_model = Timeout()
        return self.timeout_model

    async def get_timeout_page(self, request: Request):
        """超时响应列表页面"""
        try:
            with open(os.path.join("static", "index", "timeout.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return JSONResponse({"error": "Page not found"}, status_code=404)
        except Exception as e:
            self.log_error("/timeout", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    async def get_timeout_detail_api(self, request: Request, message_id: str):
        """获取超时响应详情API - 特殊业务逻辑，保留在子类中"""
        try:
            timeout_model = self._get_timeout_model()
            detail = timeout_model.get_timeout_detail(message_id)

            if detail:
                return JSONResponse({"success": True, "data": detail})
            else:
                return JSONResponse({"success": False, "error": "超时响应记录不存在"}, status_code=404)

        except Exception as e:
            self.log_error("/api/timeout/detail", e)
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    def register_routes(self, app: FastAPI):
        """注册路由"""

        async def require_login(request: Request):
            """登录检查装饰器"""
            if not await check_user_login(request):
                return get_login_redirect()
            return None

        timeout_model = self._get_timeout_model()

        # 页面路由
        @app.get("/timeout", response_class=HTMLResponse)
        async def timeout_page(request: Request):
            self.log_request("/timeout")
            login_check = await require_login(request)
            if login_check:
                return login_check
            return await self.get_timeout_page(request)

        # 使用基类的通用路由处理器创建API路由
        @app.get("/api/timeout/list")
        async def timeout_list_api(request: Request, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                                  user_nick: str = Query(None), date_range: str = Query("all"),
                                  search: str = Query(None)):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return self.handle_list_request(timeout_model, page, limit, user_nick, date_range, search)

        @app.get("/api/timeout/stats")
        async def timeout_stats_api(request: Request, user_nick: str = Query(None), date_range: str = Query("all")):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return self.handle_stats_request(timeout_model, user_nick, date_range)

        @app.get("/api/timeout/users")
        async def timeout_users_api(request: Request):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return self.handle_users_request(timeout_model)

        # 详情API - 保留特殊业务逻辑
        @app.get("/api/timeout/detail/{message_id}")
        async def timeout_detail_api(request: Request, message_id: str):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return await self.get_timeout_detail_api(request, message_id)

        logger.info("Timeout server routes registered successfully")