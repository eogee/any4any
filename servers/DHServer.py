import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from servers.Server import Server

logger = logging.getLogger(__name__)

class DHServer(Server):
    """数字人服务器"""

    def register_routes(self, app: FastAPI):
        """注册数字人相关路由"""

        @app.get("/dh/dashboard", response_class=HTMLResponse)
        @app.get("/dh/dashboard.html", response_class=HTMLResponse)
        async def dh_dashboard():
            """数字人仪表板页面"""
            try:
                with open(os.path.join("static", "dh", "dashboard.html"), "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            except FileNotFoundError:
                logger.error("Dashboard page not found: static/dh/dashboard.html")
                return JSONResponse({"error": "Dashboard page not found"}, status_code=404)

        @app.get("/dh/chat", response_class=HTMLResponse)
        @app.get("/dh/chat.html", response_class=HTMLResponse)
        async def dh_chat():
            """数字人聊天页面"""
            try:
                with open(os.path.join("static", "dh", "chat.html"), "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            except FileNotFoundError:
                logger.error("Chat page not found: static/dh/chat.html")
                return JSONResponse({"error": "Chat page not found"}, status_code=404)

        @app.get("/dh/asr", response_class=HTMLResponse)
        @app.get("/dh/asr.html", response_class=HTMLResponse)
        async def dh_asr():
            """语音识别服务页面"""
            try:
                with open(os.path.join("static", "dh", "asr.html"), "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            except FileNotFoundError:
                logger.error("ASR page not found: static/dh/asr.html")
                return JSONResponse({"error": "ASR page not found"}, status_code=404)

        @app.get("/dh", response_class=HTMLResponse)
        async def dh_redirect():
            """DH根路径重定向到仪表板"""
            return HTMLResponse("""
                <script>
                    window.location.href = '/dh/dashboard';
                </script>
            """)