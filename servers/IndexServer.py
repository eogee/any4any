import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from core.chat.preview import preview_service
from servers.Server import Server

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
            response = await preview_service.confirm_preview(preview_id)
            return JSONResponse(response)
        except Exception as e:
            return JSONResponse({
                "error": str(e),
                "status": "error"
            }, status_code=400)
            
    async def get_preview_data(self, preview_id: str):
        """获取预览数据"""
        try:
            preview = await preview_service.get_preview(preview_id)
            return JSONResponse({
                "preview_id": preview.preview_id,
                "request": preview.request_data,
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
            await preview_service.update_content(preview_id, edited_content)
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
            
        @app.post("/v1/chat/confirm/{preview_id}")
        async def confirm_preview_route(request: Request, preview_id: str):
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
            
        @app.get("/v1/chat/completions/result/{preview_id}")
        async def preview_result(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_preview_data(preview_id)
            
        # 保持原始API方法不变，以便其他地方调用
        self._original_get_pending_previews = self.get_pending_previews
        self._original_get_preview = self.get_preview
        self._original_confirm_preview = self.confirm_preview
        self._original_get_preview_data = self.get_preview_data
        self._original_update_preview_content = self.update_preview_content