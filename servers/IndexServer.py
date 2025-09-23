import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from core.chat.preview import preview_service
from servers.Server import Server

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
        async def read_root():
            """
            处理首页请求，返回index.html内容
            """
            with open(os.path.join("static", "index", "index.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
            
        @app.get("/index", response_class=HTMLResponse)
        async def read_index():
            """
            处理/index请求，返回index.html内容
            """
            with open(os.path.join("static", "index", "index.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
            
        # 预览相关路由
        app.get("/api/pending-previews")(self.get_pending_previews)
        app.get("/v1/chat/preview/{preview_id}")(self.get_preview)
        app.post("/v1/chat/confirm/{preview_id}")(self.confirm_preview)
        app.get("/api/preview/{preview_id}")(self.get_preview_data)
        app.post("/api/preview/{preview_id}/edit")(self.update_preview_content)
        app.get("/v1/chat/completions/result/{preview_id}")(self.get_preview_data)