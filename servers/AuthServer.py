import os
import time
from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from servers.Server import Server
from data_models.Auth import AuthModel

class LoginRequest(BaseModel):
    """
    登录请求的数据模型
    """
    username: str
    password: str

class AuthServer(Server):
    """
    认证服务器类，负责处理登录相关路由
    """
    def __init__(self):
        super().__init__()
        # 初始化认证模型
        self.auth_model = AuthModel()
        
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
            
        # 登录API接口
        @app.post("/auth/login", response_model=dict)
        async def login(login_request: LoginRequest = Body(...), request: Request = None):
            """
            处理用户登录请求
            
            Args:
                login_request: 包含用户名和密码的登录请求
                request: FastAPI请求对象，用于访问session
            
            Returns:
                dict: 包含登录结果的响应字典
            """
            # 记录请求日志
            self.log_request("/auth/login")
            
            try:
                # 获取请求数据
                username = login_request.username
                password = login_request.password
                
                # 后端验证 - 与前端验证保持一致
                # 用户名长度验证
                if not username or len(username) < 3 or len(username) > 50:
                    return {
                        "success": False,
                        "message": "用户名长度必须在3到50个字符之间"
                    }
                
                # 密码长度验证
                if not password or len(password) < 6 or len(password) > 50:
                    return {
                        "success": False,
                        "message": "密码长度必须在6到50个字符之间"
                    }
                
                # 使用AuthModel验证用户凭据
                user = self.auth_model.verify_user_credentials(username, password)
                
                if user:
                    # 在session中保存用户信息
                    if request and hasattr(request, 'session'):
                        request.session['user_id'] = user['id']
                        request.session['username'] = user['username']
                        request.session['nickname'] = user.get('nickname', user['username'])
                        request.session['logged_in'] = True
                        
                        self.logger.info(f"For user {username}, session set successfully")
                    
                    self.logger.info(f"User {username} login successful")
                    return {
                        "success": True,
                        "message": "登录成功",
                        "username": username,
                        "nickname": user.get('nickname', username)
                    }
                else:
                    self.logger.warning(f"User {username} login failed: incorrect username or password")
                    return {
                        "success": False,
                        "message": "用户名或密码错误"
                    }
                    
            except Exception as e:
                self.log_error("/auth/login", e)
                return {
                    "success": False,
                    "message": f"登录过程中发生错误: {str(e)}"
                }
                
        # 注销API接口
        @app.get("/auth/logout")
        async def logout(request: Request):
            """
            处理用户注销请求，清空并关闭session
            
            Args:
                request: FastAPI请求对象，用于访问session
            
            Returns:
                RedirectResponse: 重定向到登录页面
            """
            # 记录请求日志
            self.log_request("/auth/logout")
            
            try:
                # 检查用户是否已登录
                username = "anonymous"
                if hasattr(request, 'session') and request.session.get('logged_in'):
                    # 获取用户名用于日志记录
                    username = request.session.get('username', 'unknown')
                    
                    # 清空session中的所有数据
                    request.session.clear()
                    
                    self.logger.info(f"User {username} logout successful, session cleared")
                else:
                    self.logger.warning("Logout requested but no active session found")
                
                # 重定向到登录页面
                return RedirectResponse(url='/login', status_code=302)
                
            except Exception as e:
                self.log_error("/auth/logout", e)
                return {
                    "success": False,
                    "message": f"注销过程中发生错误: {str(e)}"
                }