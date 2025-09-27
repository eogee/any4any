import os
import logging
import traceback
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from core.chat.preview import preview_service
from servers.Server import Server
from core.chat.conversation_database import ConversationDatabase

# 配置日志
logger = logging.getLogger(__name__)

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
            # 调用preview_service的confirm_preview方法
            # 注意：如果message_manager.py中已正确注册了回调，
            # 这里的调用会自动触发预览确认后的钉钉消息发送
            response = await preview_service.confirm_preview(preview_id)
            
            # 添加日志记录，用于调试
            logging.info(f"Preview confirmed for ID: {preview_id}")
            
            return JSONResponse(response)
        except Exception as e:
            # 添加错误日志记录
            logging.error(f"Error confirming preview {preview_id}: {str(e)}")
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
            
    async def get_conversation_messages(self, conversation_id: str):
        """
        获取指定conversation_id的所有消息数据
        从messages表中直接查询数据
        """
        logging.info(f"[API] 开始处理请求 - 会话ID: {conversation_id}")
        
        # 验证conversation_id参数
        if not conversation_id or not isinstance(conversation_id, str):
            error_msg = f"无效的会话ID: {conversation_id} (类型: {type(conversation_id).__name__})"
            logging.error(f"[ERROR] {error_msg}")
            return JSONResponse({
                "status": "error",
                "error": error_msg,
                "conversation_id": str(conversation_id) if conversation_id else "None",
                "error_type": "invalid_parameter"
            }, status_code=400)
        
        try:
            logging.info(f"[INFO] 尝试获取会话ID: {conversation_id} 的消息数据")
            
            # 创建数据库实例
            logging.info(f"[INFO] 创建数据库连接")
            db = ConversationDatabase()
            logging.info(f"[INFO] 数据库实例创建成功，准备查询会话ID: {conversation_id}")
            
            # 检查数据库方法是否存在
            if not hasattr(db, 'get_conversation_by_id'):
                logging.error(f"[ERROR] 数据库对象没有get_conversation_by_id方法")
                return JSONResponse({
                    "status": "error",
                    "error": "数据库方法未找到: get_conversation_by_id",
                    "conversation_id": conversation_id,
                    "error_type": "database_error"
                }, status_code=500)
            
            # 获取完整的会话数据，包括消息列表
            conversation = db.get_conversation_by_id(conversation_id)
            logging.info(f"[INFO] 查询结果: {'找到会话' if conversation else '未找到会话'}")
            
            if not conversation:
                logging.error(f"[ERROR] 会话ID {conversation_id} 不存在")
                return JSONResponse({
                    "status": "error",
                    "error": "会话不存在",
                    "conversation_id": conversation_id,
                    "error_type": "not_found"
                }, status_code=404)
            
            # 安全获取消息列表
            messages = []
            try:
                if isinstance(conversation, dict):
                    messages = conversation.get('messages', [])
                elif hasattr(conversation, 'messages'):
                    messages = conversation.messages
                else:
                    logging.warning(f"[WARNING] 会话对象格式未知，无法提取消息列表: {type(conversation)}")
            except Exception as msg_extract_error:
                logging.error(f"[ERROR] 提取消息列表时发生错误: {str(msg_extract_error)}")
                messages = []
            
            logging.info(f"[SUCCESS] 成功获取消息列表，共 {len(messages)} 条消息")
            
            # 返回消息列表和会话详情
            return JSONResponse({
                "status": "success",
                "conversation_id": conversation_id,
                "message_count": len(messages),
                "conversation": conversation,
                "messages": messages,
                "api_info": {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0"
                }
            })
            
        except ConnectionError as conn_error:
            error_message = f"数据库连接错误: {str(conn_error)}"
            logging.critical(f"[CRITICAL ERROR] {error_message}")
            logging.error(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
            return JSONResponse({
                "status": "error",
                "error": "数据库连接失败，请检查数据库服务是否运行",
                "conversation_id": conversation_id,
                "error_type": "connection_error",
                "details": str(conn_error)
            }, status_code=503)
            
        except AttributeError as attr_error:
            error_message = f"属性错误: {str(attr_error)}"
            logging.error(f"[ERROR] {error_message}")
            logging.error(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
            return JSONResponse({
                "status": "error",
                "error": "系统错误，请联系管理员",
                "conversation_id": conversation_id,
                "error_type": "attribute_error",
                "details": str(attr_error)
            }, status_code=500)
            
        except Exception as e:
            logging.error(f"[ERROR] 查询会话消息时发生错误: {str(e)}")
            logging.error(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
            return JSONResponse({
                "error": "服务器内部错误，请稍后重试",
                "error_type": type(e).__name__,
                "status": "error",
                "conversation_id": conversation_id,
                "details": str(e)
            }, status_code=500)
        
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
            
        # 支持GET和POST请求，确保预览确认能够正确处理
        @app.get("/v1/chat/confirm/{preview_id}")
        async def confirm_preview_route_get(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.confirm_preview(preview_id)
        
        @app.post("/v1/chat/confirm/{preview_id}")
        async def confirm_preview_route_post(request: Request, preview_id: str):
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
            
        # 新增PUT路由，匹配前端使用的路径格式
        @app.put("/api/previews/{preview_id}")
        async def put_update_preview_route(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.update_preview_content(preview_id, request)
            
        @app.get("/v1/chat/completions/result/{preview_id}")
        async def preview_result(request: Request, preview_id: str):
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_preview_data(preview_id)
            
        @app.get("/api/conversation/{conversation_id}/messages")
        async def conversation_messages(request: Request, conversation_id: str):
            """获取指定会话ID的所有消息"""
            if not await check_user_login(request):
                return get_login_redirect()
            return await self.get_conversation_messages(conversation_id)