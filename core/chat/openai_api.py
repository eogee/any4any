import time
import json
import asyncio
from typing import List, Optional, Literal
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from config import Config
from core.model_manager import ModelManager
from core.chat.preview import preview_service
from core.chat.conversation_manager import conversation_manager

class ChatRequest(BaseModel):
    message: str
    generation_id: str = None

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "default"
    stream: bool = False
    temperature: float = Config.TEMPERATURE 
    max_tokens: Optional[int] = Config.MAX_LENGTH 
    stop: Optional[List[str]] = None
    top_p: Optional[float] = Config.TOP_P
    repetition_penalty: Optional[float] = Config.REPETITION_PENALTY
    # 添加可选的用户信息字段，用于从请求体中提取
    sender_id: Optional[str] = None
    sender_nickname: Optional[str] = None
    platform: Optional[str] = None

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = "stop"

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage

class ModelData(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "local"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelData]

class OpenAIAPI:
    @staticmethod
    async def chat_completions(request: Request, chat_request: ChatCompletionRequest):
        """OpenAI API兼容的聊天完成接口"""
        try:
            # 特殊处理：检查是否为特定的摘要请求格式，直接返回null（由于astrbot会有系统自动发起的请求）
            for msg in chat_request.messages:
                if ((msg.role == "user" and 
                    "Please summarize the following query of user:" in msg.content and
                    "Only output the summary within" in msg.content and 
                    "DO NOT INCLUDE any other text" in msg.content) or (msg.role == "user" and 
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
            
            # 从请求体中提取用户信息，如果请求体中没有，则从请求头中获取，最后使用默认值
            # 优先使用请求体中的sender_id, sender_nickname和platform字段
            sender = chat_request.sender_id or request.headers.get("X-User-ID", "anonymous_user")
            user_nick = chat_request.sender_nickname or request.headers.get("X-User-Nick", "Anonymous")
            platform = chat_request.platform or request.headers.get("X-Platform", "web")
            
            # 获取用户最新消息内容
            user_message_content = ""
            for msg in reversed(chat_request.messages):
                if msg.role == "user":
                    user_message_content = msg.content
                    break
            
            # 检查特殊指令 /a
            if user_message_content.strip() == "/a":
                # 使用会话管理器处理新会话创建
                response, _ = await conversation_manager.process_message(sender, user_nick, platform, user_message_content)
                
                # 返回新会话已开启的提示
                return JSONResponse({
                    "id": f"new_conversation_{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response  # "新会话已开启，请输入您的问题。"
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": len(user_message_content) // 4,
                        "completion_tokens": len(response) // 4,
                        "total_tokens": (len(user_message_content) + len(response)) // 4
                    }
                })
            
            # 检查预览模式是否启用
            preview_mode = Config.PREVIEW_MODE
            
            # 无论是否是预览模式，都使用会话管理器处理消息
            # 调用会话管理器处理消息
            assistant_response, _ = await conversation_manager.process_message(
                sender, 
                user_nick, 
                platform, 
                user_message_content
            )
            
            # 非流式响应直接返回
            if not chat_request.stream:
                # 如果是预览模式，创建预览请求并保存生成的内容
                if preview_mode:
                    preview = await preview_service.create_preview(chat_request.dict())
                    await preview_service.set_generated_content(preview.preview_id, assistant_response)
                
                return JSONResponse({
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
                        "prompt_tokens": len(user_message_content) // 4,
                        "completion_tokens": len(assistant_response) // 4,
                        "total_tokens": (len(user_message_content) + len(assistant_response)) // 4
                    }
                })
            
            # 流式响应的情况下，如果是预览模式，创建预览请求
            if preview_mode:
                preview = await preview_service.create_preview(chat_request.dict())
                
                # 等待用户确认（使用配置中的超时时间）
                timeout = getattr(Config, 'PREVIEW_TIMEOUT', 300)  # 默认5分钟超时
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    # 检查是否已确认
                    updated_preview = await preview_service.get_preview(preview.preview_id)
                    if updated_preview.confirmed:
                        # 返回最终编辑后的内容
                        final_content = await preview_service.get_content(preview.preview_id)
                        return JSONResponse({
                            "id": f"openai_{int(time.time())}",
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": chat_request.model,
                            "choices": [{
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": final_content
                                },
                                "finish_reason": "stop"
                            }],
                            "usage": {
                                "prompt_tokens": len(user_message) // 4,
                                "completion_tokens": len(final_content) // 4,
                                "total_tokens": (len(user_message) + len(final_content)) // 4
                            }
                        })
                    
                    # 等待 1 秒后再次检查
                    await asyncio.sleep(1)
                
                # 超时后返回原始内容
                return JSONResponse({
                    "id": f"openai_{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": chat_request.model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response_content + "\n\n（注：预览确认超时，返回原始内容）"
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": len(user_message) // 4,
                        "completion_tokens": len(response_content) // 4,
                        "total_tokens": (len(user_message) + len(response_content)) // 4
                    }
                })
            
            if chat_request.stream:
                # 流式响应
                generation_id = f"chatcmpl-{int(time.time())}"  # 使用OpenAI格式的ID
                
                async def openai_stream():
                    first_chunk = True
                    accumulated_content = ""
                    start_time = time.time()
                    
                    try:
                        # 无论是否是预览模式，都使用会话管理器的流式处理
                        # 调用会话管理器处理流式消息
                        async for text_chunk in conversation_manager.process_message_stream(
                            sender, 
                            user_nick, 
                            platform, 
                            user_message_content,
                            generation_id
                        ):
                            # 跳过空文本
                            if not text_chunk or text_chunk.isspace():
                                continue
                                  
                            # 累积内容用于调试和token计数
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
                                    },
                                    "finish_reason": None
                                }]
                            }
                              
                            # 如果是第一个chunk，添加role信息
                            if first_chunk:
                                response_data["choices"][0]["delta"]["role"] = "assistant"
                                first_chunk = False
                              
                            response_str = json.dumps(response_data, ensure_ascii=False)
                            yield f"data: {response_str}\n\n"
                              
                            # 添加小延迟避免发送过快
                            await asyncio.sleep(0.01)
                        
                        # 发送结束事件（正常完成）
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
                        end_str = json.dumps(end_data, ensure_ascii=False)
                        yield f"data: {end_str}\n\n"
                        
                        # 发送流结束标记
                        yield "data: [DONE]\n\n"
                        print(f"Streaming response completed, total content length: {len(accumulated_content)}")
                        
                        # 如果是预览模式，保存生成的内容
                        if preview_mode:
                            await preview_service.set_generated_content(preview.preview_id, accumulated_content)
                    except Exception as e:
                        print(f"Streaming response error: {str(e)}")
                        # 检查是否为停止生成异常
                        error_type = "stop" if "StopGenerationException" in str(e) or "停止" in str(e) or "终止" in str(e) else "error"
                        
                        error_data = {
                            "id": generation_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": chat_request.model,
                            "choices": [{
                                "index": 0,
                                "delta": {} if error_type == "stop" else {
                                    "content": f"\n\n[错误: {str(e)}]"
                                },
                                "finish_reason": error_type
                            }]
                        }
                        error_str = json.dumps(error_data, ensure_ascii=False)
                        yield f"data: {error_str}\n\n"
                        yield "data: [DONE]\n\n"
                
                # 设置Dify兼容的响应头
                headers = {
                    "Content-Type": "text/event-stream; charset=utf-8",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "X-Accel-Buffering": "no",  # 防止Nginx缓冲
                }
                
                return StreamingResponse(
                    openai_stream(), 
                    media_type="text/event-stream; charset=utf-8", 
                    headers=headers
                )
            else:
                # 这个分支理论上不应该被执行，因为我们已经在前面处理了所有情况
                # 但为了安全起见，保留一个简单的错误响应
                print("Unexpected code path: Non-streaming response reached after previous handling")
                return JSONResponse({
                    "error": {
                        "message": "Unexpected response path",
                        "type": "invalid_request_error",
                        "code": "unexpected_code_path"
                    }
                }, status_code=400)
                
        except Exception as e:
            print(f"OpenAI API err: {str(e)}")
            return JSONResponse({
                "error": {
                    "message": str(e),
                    "type": "api_error",
                    "code": 500
                }
            }, status_code=500)

    @staticmethod
    async def list_models():
        """OpenAI API兼容的模型列表接口"""
        return JSONResponse({
            "object": "list",
            "data": [{
                "id": Config.LLM_MODEL_NAME,  # 使用配置中的模型名称
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local"
            }]
        })

# 创建全局OpenAI API服务实例
openai_api = OpenAIAPI()