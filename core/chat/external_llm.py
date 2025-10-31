import os
import json
import logging
import aiohttp
import asyncio
import time
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
        self.max_retries = Config.API_MAX_RETRIES
        self.retry_delay = Config.API_RETRY_DELAY
        self.session = None

        if self.server_type == "api" and self.api_key and self.base_url:
            logger.info(f"External LLM API (OpenAI compatible) initialized: {self.model_name} ({self.base_url})")
        elif self.server_type == "api" and not self.api_key:
            logger.warning("External LLM API key is empty, service may not work properly")
        else:
            logger.info("Using local LLM service (external API disabled)")

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话 - 优化的连接池配置"""
        if self.session is None or self.session.closed:
            # 配置连接器以优化连接池
            connector = aiohttp.TCPConnector(
                limit=100,              # 总连接池大小
                limit_per_host=30,      # 每个主机的连接数
                ttl_dns_cache=300,      # DNS缓存时间
                use_dns_cache=True,
                keepalive_timeout=30,   # 保持连接时间
                enable_cleanup_closed=True
            )

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.timeout,
                    connect=30,          # 连接超时
                    sock_read=60         # 读取超时
                ),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "any4any/1.0"
                }
            )
        return self.session

    async def _make_api_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发起API请求  chat/completions格式"""
        if self.server_type != "api" or not self.api_key or not self.base_url:
            raise ValueError("External LLM API is not properly configured")

        session = await self._get_session()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 包含初始尝试
            try:
                start_time = time.time()

                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        request_time = time.time() - start_time
                        logger.info(f"API request successful on attempt {attempt + 1}, took {request_time:.2f}s")
                        return result
                    else:
                        error_text = await response.text()
                        last_exception = Exception(f"API request failed: {response.status} - {error_text}")

                        # 某些错误码不重试
                        if response.status in [401, 403, 404]:
                            logger.error(f"API request failed with non-retryable status {response.status}: {error_text}")
                            raise last_exception

                        logger.warning(f"API request attempt {attempt + 1} failed with status {response.status}: {error_text}")

            except asyncio.TimeoutError as e:
                last_exception = Exception(f"API request timeout on attempt {attempt + 1}: {str(e)}")
                logger.warning(f"API request attempt {attempt + 1} timed out")

            except Exception as e:
                last_exception = Exception(f"API request exception on attempt {attempt + 1}: {str(e)}")
                logger.warning(f"API request attempt {attempt + 1} failed: {str(e)}")

            if attempt < self.max_retries:
                wait_time = self.retry_delay * (2 ** attempt)
                logger.info(f"Retrying API request in {wait_time:.1f}s... (attempt {attempt + 2}/{self.max_retries + 1})")
                await asyncio.sleep(wait_time)

        # 所有重试都失败了
        logger.error(f"API request failed after {self.max_retries + 1} attempts: {last_exception}")
        raise last_exception

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
            "stream": stream
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

    async def close(self):
        """清理HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("External LLM service session closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

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

                            if line_str.startswith("data: "):
                                try:
                                    json_data = json.loads(line_str[6:])
                                    logger.debug(f"Parsed JSON data: {json_data}")

                                    if "choices" in json_data and len(json_data["choices"]) > 0:
                                        choice = json_data["choices"][0]
                                        logger.debug(f"Choice data: {choice}")

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
            return service.generate_stream_response(messages, temperature, max_tokens)
        else:
            return service.generate_response(messages, temperature, max_tokens, stream)
    else:
        if messages and len(messages) > 0:
            user_message = messages[0].get("content", "") if isinstance(messages[0], dict) else str(messages[0])
        else:
            user_message = ""

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
        return [{
            "id": Config.MODEL_NAME or "gpt-3.5-turbo",
            "name": Config.MODEL_NAME or "gpt-3.5-turbo",
            "description": "External LLM API",
            "provider": "external"
        }]
    else:
        try:
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