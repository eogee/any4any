import os
import time
from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from servers.Server import Server
from data_models.Auth import AuthModel

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthServer(Server):
    def __init__(self):
        super().__init__()
        self.auth_model = AuthModel()
        
    def register_routes(self, app: FastAPI):
        @app.get("/login", response_class=HTMLResponse)
        async def read_login():
            with open(os.path.join("static", "index", "login.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
            
        @app.get("/auth/login", response_class=HTMLResponse)
        async def read_auth_login():
            with open(os.path.join("static", "index", "login.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
            
        @app.post("/auth/login", response_model=dict)
        async def login(login_request: LoginRequest = Body(...), request: Request = None):
            self.log_request("/auth/login")
            
            try:
                username = login_request.username
                password = login_request.password
                
                if not username or len(username) < 3 or len(username) > 50:
                    return {"success": False, "message": "用户名长度必须在3到50个字符之间"}
                
                if not password or len(password) < 6 or len(password) > 50:
                    return {"success": False, "message": "密码长度必须在6到50个字符之间"}
                
                user = self.auth_model.verify_user_credentials(username, password)
                
                if user:
                    if request and hasattr(request, 'session'):
                        request.session['user_id'] = user['id']
                        request.session['username'] = user['username']
                        request.session['nickname'] = user.get('nickname', user['username'])
                        request.session['logged_in'] = True
                    
                    self.logger.info(f"User {username} login successful")
                    return {
                        "success": True,
                        "message": "登录成功",
                        "username": username,
                        "nickname": user.get('nickname', username)
                    }
                else:
                    self.logger.warning(f"User {username} login failed")
                    return {"success": False, "message": "用户名或密码错误"}
                    
            except Exception as e:
                self.log_error("/auth/login", e)
                return {"success": False, "message": f"登录过程中发生错误: {str(e)}"}
                
        @app.get("/auth/logout")
        async def logout(request: Request):
            self.log_request("/auth/logout")
            
            try:
                username = "anonymous"
                if hasattr(request, 'session') and request.session.get('logged_in'):
                    username = request.session.get('username', 'unknown')
                    request.session.clear()
                    self.logger.info(f"User {username} logout successful")
                else:
                    self.logger.warning("Logout requested but no active session found")
                
                return RedirectResponse(url='/login', status_code=302)
                
            except Exception as e:
                self.log_error("/auth/logout", e)
                return {"success": False, "message": f"注销过程中发生错误: {str(e)}"}