from typing import List, Optional, Literal
import time
import json
import asyncio
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from core.model_manager import ModelManager
from core.chat.preview import preview_service
from config import Config

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
            
            # 检查预览模式是否启用
            preview_mode = Config.PREVIEW_MODE
            
            # 将messages转换为单一提示
            user_message = ""
            system_message = ""
            for msg in chat_request.messages:
                if msg.role == "system":
                    system_message = msg.content
                    user_message += f"<|im_start|>system\n{msg.content}<|im_end|>\n"
                elif msg.role == "user":
                    user_message += f"<|im_start|>user\n{msg.content}<|im_end|>\n"
                elif msg.role == "assistant":
                    user_message += f"<|im_start|>assistant\n{msg.content}<|im_end|>\n"
            
            # 添加最后的assistant标记
            user_message += "<|im_start|>assistant\n"
            
            if preview_mode:
                # 预览模式 - 创建预览请求并生成内容
                preview = await preview_service.create_preview(chat_request.dict())
                
                # 生成模型响应
                response_content = await ModelManager.get_llm_service().generate_response(
                    user_message,
                    temperature=chat_request.temperature,
                    top_p=chat_request.top_p,
                    max_new_tokens=chat_request.max_tokens,
                    repetition_penalty=chat_request.repetition_penalty
                )
                
                # 保存生成的内容到预览中
                await preview_service.set_generated_content(preview.preview_id, response_content)
                
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
                        # 直接使用LLM服务的generate_stream方法，传递请求参数
                        async for text_chunk in ModelManager.get_llm_service().generate_stream(
                            user_message, 
                            generation_id,
                            temperature=chat_request.temperature,
                            top_p=chat_request.top_p,
                            max_new_tokens=chat_request.max_tokens,
                            repetition_penalty=chat_request.repetition_penalty
                        ):
                            # 处理特殊标记
                            cleaned_chunk = text_chunk
                            if "<|im_start|>assistant" in cleaned_chunk:
                                cleaned_chunk = cleaned_chunk.split("<|im_start|>assistant")[-1].strip()
                            if "<|im_end|>" in cleaned_chunk:
                                cleaned_chunk = cleaned_chunk.split("<|im_end|>")[0].strip()
                            
                            # 跳过空文本
                            if not cleaned_chunk or cleaned_chunk.isspace():
                                continue
                                
                            # 累积内容用于调试和token计数
                            accumulated_content += cleaned_chunk
                            
                            # 构建响应数据 - 简化格式，避免不必要的字段
                            response_data = {
                                "id": generation_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": chat_request.model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {
                                        "content": cleaned_chunk
                                    },
                                    "finish_reason": None
                                }]
                            }
                            
                            # 如果是第一个chunk，添加role信息
                            if first_chunk:
                                response_data["choices"][0]["delta"]["role"] = "assistant"
                                first_chunk = False
                            
                            response_str = json.dumps(response_data, ensure_ascii=False)
                            yield f"data: {response_str}\n\n"  # Dify可能更适应\n\n
                            
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
                # 非流式响应
                response = await ModelManager.get_llm_service().generate_response(
                    user_message,
                    temperature=chat_request.temperature,
                    top_p=chat_request.top_p,
                    max_new_tokens=chat_request.max_tokens,
                    repetition_penalty=chat_request.repetition_penalty
                )
                
                # 直接返回JSONResponse确保格式正确
                return JSONResponse({
                    "id": f"chatcmpl-{int(time.time())}",
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
                        "prompt_tokens": len(user_message) // 4,
                        "completion_tokens": len(response) // 4,
                        "total_tokens": (len(user_message) + len(response)) // 4
                    }
                })
                
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