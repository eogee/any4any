import os
import json
import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any, AsyncGenerator

logger = logging.getLogger(__name__)

class ExternalLLMService:
    """外部LLM API 服务类 - 基于OpenAI兼容格式"""

    def __init__(self):
        """初始化外部LLM服务 - OpenAI兼容格式"""
        from config import Config

        self.server_type = Config.LLM_SERVER_TYPE
        self.api_key = Config.EXTERNAL_API_KEY
        self.api_url = Config.API_URL
        self.base_url = Config.API_BASE_URL or Config.API_URL
        self.model_name = Config.MODEL_NAME
        self.timeout = Config.API_TIMEOUT
        self.max_tokens = Config.MAX_TOKENS
        self.stream_enabled = Config.STREAM_ENABLED
        self.session = None

        if self.server_type == "api" and self.api_key and self.base_url:
            logger.info(f"External LLM API (OpenAI compatible) initialized: {self.model_name} ({self.base_url})")
        elif self.server_type == "api" and not self.api_key:
            logger.warning("External LLM API key is empty, service may not work properly")
        else:
            logger.info("Using local LLM service (external API disabled)")

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话 - OpenAI标准认证"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self.session

    async def _make_api_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发起API请求 - OpenAI chat/completions格式"""
        if self.server_type != "api" or not self.api_key or not self.base_url:
            raise ValueError("External LLM API is not properly configured")

        session = await self._get_session()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed: {response.status} - {error_text}")
                    raise Exception(f"API request failed: {response.status}")
        except Exception as e:
            logger.error(f"API request exception: {str(e)}")
            raise Exception(f"API request exception: {str(e)}")

    async def generate_response(self, messages: list, temperature: float = None,
                          max_tokens: int = None, stream: bool = False) -> str:
        """生成对话响应 - OpenAI chat/completions格式"""
        if self.server_type != "api" or not self.api_key or not self.base_url:
            raise ValueError("External LLM API is not properly configured")

        # 构建请求数据
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature or 0.7,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": stream  # 使用传入的 stream 参数
        }

        response = await self._make_api_request("chat/completions", data)

        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]
            else:
                logger.error(f"Unexpected response format: {choice}")
                raise Exception("Invalid response format from API")
        else:
            logger.error(f"No choices in response: {response}")
            raise Exception("No valid choices in API response")

    async def generate_stream_response(self, messages: list, temperature: float = None,
                                 max_tokens: int = None) -> AsyncGenerator[str, None]:
        """生成流式对话响应 - OpenAI SSE格式"""
        if self.server_type != "api" or not self.api_key or not self.base_url:
            raise ValueError("External LLM API is not properly configured")

        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature or 0.7,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": self.stream_enabled
        }

        logger.debug(f"Stream API request data: {data}")

        session = await self._get_session()
        url = f"{self.base_url.rstrip('/')}/chat/completions"

        try:
            async with session.post(url, json=data) as response:
                logger.debug(f"Stream API response status: {response.status}")

                if response.status == 429:
                    logger.warning(f"API rate limit exceeded. Please try again later.")
                    raise Exception("API rate limit exceeded. Please try again later.")
                elif response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Stream API request failed: {response.status} - {error_text}")
                    raise Exception(f"Stream API request failed: {response.status}")
                else:
                    chunk_count = 0
                    async for line in response.content:
                        if line.strip():
                            # 将字节转换为字符串
                            line_str = line.decode('utf-8').strip()
                            logger.debug(f"Received SSE line: {line_str}")
                            # 解析OpenAI SSE格式的数据行
                            if line_str.startswith("data: "):
                                try:
                                    json_data = json.loads(line_str[6:])
                                    logger.debug(f"Parsed JSON data: {json_data}")

                                    # OpenAI标准格式解析
                                    if "choices" in json_data and len(json_data["choices"]) > 0:
                                        choice = json_data["choices"][0]
                                        logger.debug(f"Choice data: {choice}")

                                        # 流式响应使用delta字段
                                        if "delta" in choice and "content" in choice["delta"]:
                                            content = choice["delta"]["content"]
                                            if content:  # 确保content不为空
                                                logger.debug(f"Yielding content chunk {chunk_count}: {repr(content)}")
                                                chunk_count += 1
                                                yield content
                                        # 兼容非流式格式的message字段
                                        elif "message" in choice and "content" in choice["message"]:
                                            content = choice["message"]["content"]
                                            if content:
                                                logger.debug(f"Yielding message content: {repr(content)}")
                                                chunk_count += 1
                                                yield content

                                    # 检查是否结束
                                    if "choices" in json_data and len(json_data["choices"]) > 0:
                                        choice = json_data["choices"][0]
                                        if "finish_reason" in choice and choice["finish_reason"]:
                                            logger.info(f"Stream finished with reason: {choice['finish_reason']}")
                                            break

                                except json.JSONDecodeError as e:
                                    logger.debug(f"JSON decode error: {e}")
                                    continue
                            elif line_str == "[DONE]":
                                logger.info(f"Stream finished, total chunks: {chunk_count}")
                                break
                    logger.info(f"Stream processing completed, yielded {chunk_count} chunks")
        except Exception as e:
            logger.error(f"Stream API request exception: {str(e)}")
            raise Exception(f"Stream API request exception: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

# 全局外部LLM服务实例
external_llm_service = None

def get_external_llm_service() -> ExternalLLMService:
    """获取外部LLM服务单例"""
    global external_llm_service
    if external_llm_service is None:
        external_llm_service = ExternalLLMService()
    return external_llm_service

def generate_chat_response(messages: list, temperature: float = None,
                           max_tokens: int = None, stream: bool = False, **kwargs):
    """统一的聊天响应生成接口"""
    from config import Config

    if Config.LLM_SERVER_TYPE == "api":
        service = get_external_llm_service()
        if stream:
            # 对于流式响应，直接返回异步生成器
            return service.generate_stream_response(messages, temperature, max_tokens)
        else:
            # 对于非流式响应，返回协程
            return service.generate_response(messages, temperature, max_tokens, stream)
    else:
        # 回退到本地LLM - 传入单个消息字符串
        if messages and len(messages) > 0:
            user_message = messages[0].get("content", "") if isinstance(messages[0], dict) else str(messages[0])
        else:
            user_message = ""

        # 延迟导入避免循环依赖
        from core.chat.llm import get_llm_service
        local_service = get_llm_service()
        if stream:
            return local_service.generate_stream(user_message, **kwargs)
        else:
            return local_service.generate_response(user_message, **kwargs)

async def list_available_models() -> list:
    """获取可用模型列表"""
    from config import Config

    if Config.LLM_SERVER_TYPE == "api":
        # 对于外部API，返回配置的模型
        return [{
            "id": Config.MODEL_NAME or "gpt-3.5-turbo",
            "name": Config.MODEL_NAME or "gpt-3.5-turbo",
            "description": "External LLM API",
            "provider": "external"
        }]
    else:
        # 对于本地模型，返回本地模型信息
        try:
            # 延迟导入避免循环依赖
            from core.chat.llm import get_llm_service
            local_service = get_llm_service()
            if hasattr(local_service, 'legacy_service') and local_service.legacy_service and hasattr(local_service.legacy_service, 'model'):
                return [{
                    "id": Config.LLM_MODEL_NAME,
                    "name": Config.LLM_MODEL_NAME,
                    "description": "Local LLM Model",
                    "provider": "local"
                }]
        except Exception as e:
            logger.error(f"Failed to get local model info: {e}")
            return []

def is_external_llm_enabled() -> bool:
    """检查是否启用了外部LLM"""
    from config import Config
    return Config.LLM_SERVER_TYPE == "api" and bool(Config.EXTERNAL_API_KEY)