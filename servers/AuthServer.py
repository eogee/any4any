import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from servers.Server import Server

class AuthServer(Server):
    """
    认证服务器类，负责处理登录相关路由
    """
    def __init__(self):
        super().__init__()
        
    def register_routes(self, app: FastAPI):
        """
        注册认证相关路由
        
        Args:
            app: FastAPI应用实例
        """
        # 登录页面路由
        @app.get("/login", response_class=HTMLResponse)
        async def read_login():
            """
            处理/login请求，返回login.html内容
            """
            with open(os.path.join("static", "index", "login.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
            
        @app.get("/auth/login", response_class=HTMLResponse)
        async def read_auth_login():
            """
            处理/auth/login请求，返回login.html内容
            """
            with open(os.path.join("static", "index", "login.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)