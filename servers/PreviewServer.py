import os
import logging
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
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
    return RedirectResponse(url='/login', status_code=302)

class PreviewServer(Server):
    """预览服务器 - 处理已回复预览相关功能"""

    def __init__(self):
        super().__init__(log_init=True)
        self.preview_model = None

    def _get_preview_model(self):
        """获取预览数据模型实例"""
        if not self.preview_model:
            self.preview_model = Preview()
        return self.preview_model

    async def get_preview_page(self, request: Request):
        """已回复预览列表页面"""
        try:
            with open(os.path.join("static", "index", "preview.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return JSONResponse({"error": "Page not found"}, status_code=404)
        except Exception as e:
            self.log_error("/preview", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    def register_routes(self, app: FastAPI):
        """注册路由"""

        async def require_login(request: Request):
            """登录检查装饰器"""
            if not await check_user_login(request):
                return get_login_redirect()
            return None

        preview_model = self._get_preview_model()

        # 页面路由
        @app.get("/preview", response_class=HTMLResponse)
        async def preview_page(request: Request):
            self.log_request("/preview")
            login_check = await require_login(request)
            if login_check:
                return login_check
            return await self.get_preview_page(request)

        # 使用基类的通用路由处理器创建API路由
        @app.get("/api/previews/list")
        async def preview_list_api(request: Request, 
                          page: int = Query(1, ge=1), 
                          limit: int = Query(20, ge=1, le=100),
                          user_nick: str = Query(None), 
                          date_range: str = Query("all"),
                          search: str = Query(None)):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return self.handle_list_request(preview_model, page, limit, user_nick, date_range, search)

        @app.get("/api/previews/stats")
        async def preview_stats_api(request: Request, user_nick: str = Query(None), date_range: str = Query("all")):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return self.handle_stats_request(preview_model, user_nick, date_range)

        @app.get("/api/users/unique")
        async def preview_users_api(request: Request):
            login_check = await require_login(request)
            if login_check:
                return login_check
            return self.handle_users_request(preview_model)