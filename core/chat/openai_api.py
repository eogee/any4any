import time
import json
import asyncio
import logging
from typing import List, Optional, Literal
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from config import Config
from core.chat.preview import preview_service
from core.chat.conversation_manager import conversation_manager

class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    """聊天完成请求模型"""
    messages: List[ChatMessage]
    model: str = "default"
    stream: bool = False
    temperature: float = Config.TEMPERATURE 
    max_tokens: Optional[int] = Config.MAX_LENGTH 
    stop: Optional[List[str]] = None
    top_p: Optional[float] = Config.TOP_P
    repetition_penalty: Optional[float] = Config.REPETITION_PENALTY
    sender_id: Optional[str] = None
    sender_nickname: Optional[str] = None
    platform: Optional[str] = None
    delay_time: Optional[int] = None  # 新增延迟时间参数

class OpenAIAPI:
    
    logger = logging.getLogger(__name__)
    
    @staticmethod
    async def chat_completions(request: Request, chat_request: ChatCompletionRequest):
        """聊天接口"""
        try:
            # 特殊处理摘要请求格式
            for msg in chat_request.messages:
                if ((msg.role == "user" and 
                    "Please summarize the following query of user:" in msg.content and
                    "Only output the summary within" in msg.content and 
                    "DO NOT INCLUDE any other text" in msg.content) or 
                    (msg.role == "user" and 
                    "You are expert in summarizing user's query." in msg.content)):
                    
                    print(f"Detected summary request format, returning null response")
                    return JSONResponse({
                        "id": f"null_response_{int(time.time())}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": chat_request.model,
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": None
                            },
                            "finish_reason": "stop"
                        }],
                        "usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        }
                    })
            
            # 提取用户信息
            sender = chat_request.sender_id or request.headers.get("X-User-ID", "anonymous_user")
            user_nick = chat_request.sender_nickname or request.headers.get("X-User-Nick", "Anonymous")
            platform = chat_request.platform or request.headers.get("X-Platform", "web")
            
            # 获取用户最新消息
            user_message_content = ""
            for msg in reversed(chat_request.messages):
                if msg.role == "user":
                    user_message_content = msg.content
                    break
            
            # 特殊指令 /a
            if user_message_content.strip() == "/a":
                response, _ = await conversation_manager.process_message(sender, user_nick, platform, user_message_content)
                return JSONResponse({
                    "id": f"new_conversation_{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": len(user_message_content) // 4,
                        "completion_tokens": len(response) // 4,
                        "total_tokens": (len(user_message_content) + len(response)) // 4
                    }
                })
            
            # 处理流式/非流式响应
            if chat_request.stream:
                return await OpenAIAPI._handle_streaming_response(
                    chat_request, sender, user_nick, platform, 
                    user_message_content, Config.PREVIEW_MODE
                )
            else:
                return await OpenAIAPI._handle_non_streaming_response(
                    chat_request, sender, user_nick, platform, 
                    user_message_content, Config.PREVIEW_MODE
                )
                
        except Exception as e:
            OpenAIAPI.logger.error(f"OpenAI API error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return JSONResponse({
                "error": {
                    "message": str(e),
                    "type": "api_error",
                    "code": 500
                }
            }, status_code=500)

    @staticmethod
    async def _handle_non_streaming_response(chat_request, sender, user_nick, platform, user_message_content, preview_mode):
        """处理非流式响应"""
        try:
            # 获取message_id用于去重
            def get_msg_id(obj):
                if hasattr(obj, 'msg_id'):
                    return obj.msg_id
                elif hasattr(obj, 'dict'):
                    return obj.dict().get('msg_id')
                elif isinstance(obj, dict):
                    return obj.get('msg_id')
                return None
            
            msg_id = get_msg_id(chat_request)
            
            # 检查是否启用延迟模式
            delay_mode_enabled = getattr(Config, 'DELAY_MODE', False)
            delay_time = getattr(chat_request, 'delay_time', None) or getattr(Config, 'DELAY_TIME', 10)
            
            # 如果是延迟模式且不是预览模式，添加延迟处理标记
            is_delayed_processing = False
            if delay_mode_enabled and not preview_mode:
                # 检查当前请求是否来自延迟处理器的回调
                is_delayed_processing = getattr(chat_request, '_is_delayed_processing', False)
            
            assistant_response, conversation_id = await conversation_manager.process_message(
                sender, 
                user_nick, 
                platform, 
                user_message_content, 
                message_id=msg_id,
                delay_time=delay_time if delay_mode_enabled and not preview_mode else None,
                is_delayed_processing=is_delayed_processing
            )
            
            # 检查是否是延迟处理中的消息
            if assistant_response == "DELAY_PROCESSING" and conversation_id == "delay_processing":
                # 对于延迟处理中的后续消息，返回空响应
                return JSONResponse({
                    "id": f"delay_processing_{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": ""
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    },
                    "delay_processing": True
                })
            
            # 预览模式处理
            if preview_mode:
                preview = await preview_service.create_preview(chat_request.dict())
                preview_id = preview.preview_id
                await preview_service.set_generated_content(preview_id, assistant_response)
                
                # 等待用户确认
                timeout = getattr(Config, 'PREVIEW_TIMEOUT', 60)
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    updated_preview = await preview_service.get_preview(preview_id)
                    if updated_preview.confirmed:
                        # 用户确认
                        final_content = await preview_service.get_content(preview_id)
                        response_data = OpenAIAPI._build_response_data(
                            chat_request, user_message_content, final_content
                        )
                        response_data["preview_id"] = preview_id
                        return JSONResponse(response_data)
                    
                    if time.time() - start_time >= timeout:
                        break
                        
                    await asyncio.sleep(1)
                
                # 超时处理
                OpenAIAPI.logger.info(f"Preview confirmation timeout after {timeout} seconds")
                _, _ = await conversation_manager.process_message(
                    sender, user_nick, platform, user_message_content, is_timeout=True, 
                    message_id=msg_id, skip_save=True
                )
                
                response_data = OpenAIAPI._build_response_data(
                    chat_request, user_message_content, assistant_response
                )
                response_data["preview_id"] = preview_id
                response_data["timeout_auto_sent"] = True
                return JSONResponse(response_data)
            
            # 非预览模式 - 检查是否有缓冲消息
            buffered_count = conversation_manager.get_buffered_message_count(sender)
            if buffered_count > 0:
                response_data = OpenAIAPI._build_response_data(
                    chat_request, user_message_content, assistant_response
                )
                response_data["buffered_messages"] = buffered_count
                response_data["delay_mode"] = True
                return JSONResponse(response_data)
            
            # 普通非预览模式响应
            response_data = OpenAIAPI._build_response_data(
                chat_request, user_message_content, assistant_response
            )
            return JSONResponse(response_data)
            
        except Exception as e:
            OpenAIAPI.logger.error(f"Non-streaming response error: {str(e)}")
            raise

    @staticmethod
    async def _handle_streaming_response(chat_request, sender, user_nick, platform, user_message_content, preview_mode):
        """处理流式响应"""
        generation_id = f"chatcmpl-{int(time.time())}"
        preview_id = None
        
        # 检查延迟模式
        delay_mode_enabled = getattr(Config, 'DELAY_MODE', False)
        
        # 预览模式初始化
        if preview_mode:
            preview = await preview_service.create_preview(chat_request.dict())
            preview_id = preview.preview_id
        
        async def openai_stream():
            accumulated_content = ""
            first_chunk = True
            timeout_reached = False
            
            # 流式响应下的延迟模式提示
            if delay_mode_enabled and not preview_mode:
                warning_msg = "\n[注意：流式响应模式下，延迟合并功能不可用，将立即处理您的消息]\n"
                warning_data = {
                    "id": generation_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": warning_msg
                        } if not first_chunk else {
                            "role": "assistant",
                            "content": warning_msg
                        },
                        "finish_reason": None
                    }]
                }
                warning_str = json.dumps(warning_data, ensure_ascii=False)
                yield f"data: {warning_str}\n\n"
                accumulated_content += warning_msg
                if first_chunk:
                    first_chunk = False
            
            try:
                # 获取message_id
                def get_msg_id(obj):
                    if hasattr(obj, 'msg_id'):
                        return obj.msg_id
                    elif hasattr(obj, 'dict'):
                        return obj.dict().get('msg_id')
                    elif isinstance(obj, dict):
                        return obj.get('msg_id')
                    return None
                
                msg_id = get_msg_id(chat_request)
                
                # 流式生成 - 流式模式下不支持延迟，直接处理
                async for text_chunk in conversation_manager.process_message_stream(
                    sender, user_nick, platform, user_message_content, generation_id, 
                    is_timeout=timeout_reached, message_id=msg_id,
                    is_delayed_processing=True  # 流式模式下强制立即处理
                ):
                    if not text_chunk or text_chunk.isspace():
                        continue
                        
                    accumulated_content += text_chunk
                    
                    # 构建响应数据
                    response_data = {
                        "id": generation_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": chat_request.model,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "content": text_chunk
                            } if not first_chunk else {
                                "role": "assistant",
                                "content": text_chunk
                            },
                            "finish_reason": None
                        }]
                    }
                    
                    response_str = json.dumps(response_data, ensure_ascii=False)
                    yield f"data: {response_str}\n\n"
                    
                    if first_chunk:
                        first_chunk = False
                    
                    await asyncio.sleep(0.001)
                
                # 预览模式处理
                if preview_mode and preview_id:
                    await preview_service.set_generated_content(preview_id, accumulated_content)
                    
                    timeout = getattr(Config, 'PREVIEW_TIMEOUT', 60)
                    start_time = time.time()
                    
                    while time.time() - start_time < timeout:
                        updated_preview = await preview_service.get_preview(preview_id)
                        if updated_preview.confirmed:
                            # 用户确认，发送差异内容
                            final_content = await preview_service.get_content(preview_id)
                            if final_content != accumulated_content:
                                diff_content = final_content[len(accumulated_content):]
                                if diff_content:
                                    diff_data = {
                                        "id": generation_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": chat_request.model,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {
                                                "content": diff_content
                                            },
                                            "finish_reason": None
                                        }]
                                    }
                                    diff_str = json.dumps(diff_data, ensure_ascii=False)
                                    yield f"data: {diff_str}\n\n"
                            break
                        
                        if time.time() - start_time >= timeout:
                            timeout_reached = True
                            logging.info(f"Streaming preview timeout after {timeout} seconds")
                            break
                            
                        await asyncio.sleep(1)
                
                # 发送结束事件
                end_data = {
                    "id": generation_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                
                if timeout_reached:
                    end_data["timeout_auto_sent"] = True
                
                end_str = json.dumps(end_data, ensure_ascii=False)
                yield f"data: {end_str}\n\n"
                
                # 发送预览信息
                if preview_mode and preview_id:
                    preview_info = {
                        "preview_id": preview_id,
                        "timeout_auto_sent": timeout_reached
                    }
                    yield f"data: {json.dumps(preview_info, ensure_ascii=False)}\n\n"
                
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                OpenAIAPI.logger.error(f"Streaming error: {str(e)}")
                error_data = {
                    "id": generation_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "error"
                    }]
                }
                error_str = json.dumps(error_data, ensure_ascii=False)
                yield f"data: {error_str}\n\n"
                yield "data: [DONE]\n\n"

        headers = {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no",
        }
        
        return StreamingResponse(
            openai_stream(), 
            media_type="text/event-stream; charset=utf-8", 
            headers=headers
        )

    @staticmethod
    def _build_response_data(chat_request, user_message, assistant_response):
        """构建响应数据"""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": chat_request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": assistant_response
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(user_message) // 4,
                "completion_tokens": len(assistant_response) // 4,
                "total_tokens": (len(user_message) + len(assistant_response)) // 4
            }
        }

    @staticmethod
    async def list_models():
        """模型列表接口"""
        return JSONResponse({
            "object": "list",
            "data": [{
                "id": Config.LLM_MODEL_NAME,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local"
            }]
        })

# 创建全局OpenAI API服务实例
openai_api = OpenAIAPI()