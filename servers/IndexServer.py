import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from core.chat.preview import preview_service
from servers.Server import Server
from core.chat.conversation_database import ConversationDatabase

logger = logging.getLogger(__name__)

async def check_user_login(request: Request):
    """检查用户是否已登录"""
    if hasattr(request, 'session') and request.session.get('logged_in'):
        return True
    return False

def get_login_redirect():
    """获取登录重定向响应"""
    return RedirectResponse(url='/login', status_code=302)

class IndexServer(Server):
    """首页服务器"""
    
    async def get_pending_previews(self):
        """获取等待确认的预览列表"""
        try:
            pending_previews = await preview_service.get_pending_previews()
            return JSONResponse(pending_previews)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)
    
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
            return JSONResponse({"error": str(e)}, status_code=400)
    
    async def confirm_preview(self, preview_id: str):
        """确认预览请求"""
        try:
            response = await preview_service.confirm_preview(preview_id)
            logging.info(f"Preview confirmed: {preview_id}")
            return JSONResponse(response)
        except Exception as e:
            logging.error(f"Error confirming preview {preview_id}: {str(e)}")
            return JSONResponse({"error": str(e)}, status_code=400)
    
    async def get_preview_data(self, preview_id: str):
        """获取预览数据"""
        try:
            preview = await preview_service.get_preview(preview_id)
            request_data = preview.request_data.copy() if preview.request_data else {}
            
            # 获取或生成conversation_id
            conversation_id = None
            
            if 'conversation_id' in request_data:
                conversation_id = request_data['conversation_id']
            elif request_data and 'messages' in request_data:
                # 查找最后一个用户消息
                last_user_message = None
                for msg in reversed(request_data['messages']):
                    if isinstance(msg, dict) and msg.get('role') == 'user':
                        last_user_message = msg.get('content', '')
                        break
                
                if last_user_message:
                    try:
                        db = ConversationDatabase()
                        result = db.fetch_one(
                            "SELECT conversation_id FROM messages WHERE content LIKE %s ORDER BY timestamp DESC LIMIT 1",
                            (f"%{last_user_message[:100]}%",)
                        )
                        if result:
                            conversation_id = result.get('conversation_id')
                    except Exception:
                        pass
            
            if not conversation_id:
                import uuid
                conversation_id = str(uuid.uuid4())
            
            request_data['conversation_id'] = conversation_id
            
            return JSONResponse({
                "preview_id": preview.preview_id,
                "request": request_data,
                "generated_content": preview.generated_content,
                "edited_content": preview.edited_content,
                "status": "preview"
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)
    
    async def update_preview_content(self, preview_id: str, request: Request):
        """更新预览内容"""
        try:
            data = await request.json()
            edited_content = data.get("content", "")
            session = request.session or {}
            await preview_service.update_content(preview_id, edited_content, session)
            return JSONResponse({"status": "success"})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)
    
    async def get_conversation_messages(self, conversation_id: str):
        """获取会话消息"""
        if not conversation_id or not isinstance(conversation_id, str):
            return JSONResponse({
                "success": False,
                "error": "Invalid conversation_id"
            }, status_code=400)
        
        try:
            db = ConversationDatabase()
            conversation = db.get_conversation_by_id(conversation_id)
            
            if not conversation:
                return JSONResponse({
                    "success": False,
                    "error": "Conversation not found"
                }, status_code=404)
            
            # 序列化datetime字段
            def safe_serialize(value):
                if hasattr(value, 'isoformat'):
                    return value.isoformat()
                return value
            
            conversation_info = {
                "conversation_id": conversation.get("conversation_id"),
                "user_nick": conversation.get("user_nick"),
                "platform": conversation.get("platform"),
                "message_count": conversation.get("message_count", 0)
            }
            
            for field in ['created_at', 'updated_at', 'last_message_time']:
                if field in conversation:
                    conversation_info[field] = safe_serialize(conversation[field])
            
            messages = conversation.get("messages", [])
            
            return JSONResponse({
                "success": True,
                "conversation_info": conversation_info,
                "messages": messages
            })
            
        except ConnectionError:
            return JSONResponse({
                "success": False,
                "error": "Database connection failed"
            }, status_code=503)
        except Exception as e:
            logging.error(f"Error querying messages: {str(e)}")
            return JSONResponse({
                "success": False,
                "error": "Internal server error"
            }, status_code=500)
    
    def register_routes(self, app: FastAPI):
        """注册路由"""
        
        async def require_login(request: Request):
            """登录检查装饰器"""
            if not await check_user_login(request):
                return get_login_redirect()
            return None
        
        @app.get("/", response_class=HTMLResponse)
        @app.get("/index", response_class=HTMLResponse)
        async def read_root(request: Request):
            """首页"""
            if redirect := await require_login(request):
                return redirect
            
            with open(os.path.join("static", "index", "index.html"), "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        
        @app.get("/api/pending-previews")
        async def pending_previews(request: Request):
            if redirect := await require_login(request):
                return redirect
            return await self.get_pending_previews()
        
        @app.get("/v1/chat/preview/{preview_id}")
        async def preview(request: Request, preview_id: str):
            if redirect := await require_login(request):
                return redirect
            return await self.get_preview(preview_id)
        
        @app.get("/v1/chat/confirm/{preview_id}")
        @app.post("/v1/chat/confirm/{preview_id}")
        async def confirm_preview_route(request: Request, preview_id: str):
            if redirect := await require_login(request):
                return redirect
            return await self.confirm_preview(preview_id)
        
        @app.get("/api/preview/{preview_id}")
        async def preview_data(request: Request, preview_id: str):
            if redirect := await require_login(request):
                return redirect
            return await self.get_preview_data(preview_id)
        
        @app.post("/api/preview/{preview_id}/edit")
        @app.put("/api/previews/{preview_id}")
        async def update_preview_route(request: Request, preview_id: str):
            if redirect := await require_login(request):
                return redirect
            return await self.update_preview_content(preview_id, request)
        
        @app.get("/v1/chat/completions/result/{preview_id}")
        async def preview_result(request: Request, preview_id: str):
            if redirect := await require_login(request):
                return redirect
            return await self.get_preview_data(preview_id)
        
        @app.get("/api/conversation/{conversation_id}/messages")
        async def conversation_messages(request: Request, conversation_id: str):
            if redirect := await require_login(request):
                return redirect
            return await self.get_conversation_messages(conversation_id)