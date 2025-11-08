import logging
import torch
import queue
import asyncio
import threading
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from config import Config

from .external_llm import generate_chat_response, is_external_llm_enabled
from core.tools import process_with_tools

logger = logging.getLogger(__name__)

class KnowledgeBaseManager:
    def __init__(self, cache_ttl: float = 300.0):
        self._kb_server = None
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = cache_ttl
        self._lock = asyncio.Lock()

    async def get_kb_server(self):
        if self._kb_server is None:
            async with self._lock:
                if self._kb_server is None:
                    from core.embedding.kb_server import get_kb_server
                    self._kb_server = get_kb_server()
        return self._kb_server

    async def retrieve_documents(self, query: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        if not use_cache:
            return await self._fresh_retrieve(query)

        cache_key = hash(query)
        current_time = asyncio.get_event_loop().time()

        if (cache_key in self._cache and
            cache_key in self._cache_timestamps and
            current_time - self._cache_timestamps[cache_key] < self._cache_ttl):
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self._cache[cache_key]

        result = await self._fresh_retrieve(query)

        if result:
            async with self._lock:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = current_time
                await self._cleanup_expired_cache(current_time)

        return result

    async def _fresh_retrieve(self, query: str) -> Optional[Dict[str, Any]]:
        try:
            kb_server = await self.get_kb_server()
            if not kb_server:
                logger.warning("Knowledge base server not available")
                return None
            return kb_server.retrieve_documents(query)
        except Exception as e:
            logger.error(f"Knowledge base retrieval failed: {e}")
            return None

    async def _cleanup_expired_cache(self, current_time: float):
        expired_keys = [
            key for key, timestamp in self._cache_timestamps.items()
            if current_time - timestamp >= self._cache_ttl
        ]

        for key in expired_keys:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

_kb_manager = None

def get_kb_manager() -> KnowledgeBaseManager:
    global _kb_manager
    if _kb_manager is None:
        _kb_manager = KnowledgeBaseManager()
    return _kb_manager

def manual_chat_format(messages: List[Dict[str, str]]) -> str:
    """手动构建聊天格式"""
    prompt = ""
    for message in messages:
        if message["role"] == "system":
            prompt += f"<|im_start|>system\n{message['content']}<|im_end|>\n"
        elif message["role"] == "user":
            prompt += f"<|im_start|>user\n{message['content']}<|im_end|>\n"

    prompt += "<|im_start|>assistant\n"
    return prompt

def format_knowledge_content(documents: List[Dict[str, Any]], source: str = "tool processor") -> str:
    """格式化知识库内容"""
    if not documents:
        return ""

    knowledge_content = "\n\n[知识库检索结果]\n"
    logger.info(f"Found {len(documents)} knowledge base documents in {source}")

    for i, doc in enumerate(documents, 1):
        content = doc.get('chunk_text', '')
        file_name = doc.get('file_name', '未知文件')
        if content:
            knowledge_content += f"【资料{i}】来自：{file_name}\n{content}\n\n"

    return knowledge_content

def handle_model_error(error: Exception) -> str:
    """处理模型相关错误"""
    if isinstance(error, ModelNotInitializedError):
        logger.error(f"Model initialization error: {str(error)}")
        return "抱歉，模型未正确初始化，请稍后再试。"
    elif isinstance(error, torch.cuda.OutOfMemoryError):
        logger.error(f"GPU out of memory: {str(error)}")
        return "抱歉，模型内存不足，请稍后再试。"
    else:
        logger.error(f"Model error: {str(error)}")
        return "抱歉，处理您的请求时出现错误。"


class StopGenerationException(Exception):
    """停止生成异常"""
    pass

class ModelNotInitializedError(Exception):
    """模型未初始化异常"""
    pass

class ToolExecutionError(Exception):
    """工具执行异常"""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")

class KnowledgeBaseError(Exception):
    """知识库异常"""
    pass

class CustomTextStreamer(TextStreamer):
    """自定义文本流处理器"""
    
    def __init__(self, tokenizer, text_queue, stop_event, **kwargs):
        super().__init__(tokenizer, **kwargs)
        self.text_queue = text_queue
        self.stop_event = stop_event

    def on_finalized_text(self, text: str, stream_end: bool = False):
        """处理生成的文本"""
        if self.stop_event.is_set():
            raise StopGenerationException("User stopped generation")
        if text:
            self.text_queue.put(('text', text))
        if stream_end:
            self.text_queue.put(('done', None))



class LocalLLMService:
    """本地LLM服务"""

    def __init__(self):
        """初始化本地LLM服务"""
        self.tokenizer = None
        self.model = None
        self._model_initialized = False
        self.device = self._get_device()
        self.active_generations = {}
        self.active_queues = set()
        self._cleanup_count = 0
        self._kb_server = None

    def _get_device(self):
        """获取设备配置"""
        if torch.cuda.is_available() and Config.DEVICE.startswith("cuda"):
            return Config.DEVICE
        return "cpu"

    def get_service_type(self):
        """获取服务类型"""
        if is_external_llm_enabled():
            return "external"
        return "local"

    async def initialize(self):
        """异步初始化本地LLM服务"""
        if self.get_service_type() == "external":
            logger.info("External LLM API detected, local model initialization skipped")
            return True

        if not self._check_main_process():
            logger.info(f"Skipping model loading in non-main process")
            return False

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                Config.LLM_MODEL_DIR,
                trust_remote_code=Config.TRUST_REMOTE_CODE,
                torch_dtype=torch.float16 if Config.USE_HALF_PRECISION else torch.float32,
                low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE
            )

            self.model = self._load_model(Config.LLM_MODEL_DIR)
            self._model_initialized = True
            logger.info("Local LLM service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Local LLM model loading failed: {e}")
            return False

    def _check_main_process(self):
        """检查是否主进程"""
        import os
        current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
        return current_port != str(Config.MCP_PORT)

    def _load_model(self, model_path):
        """加载模型"""
        return AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map=self.device if self.device.startswith("cuda") else "cpu",
            trust_remote_code=Config.TRUST_REMOTE_CODE,
            torch_dtype=torch.float16 if Config.USE_HALF_PRECISION else torch.float32,
            low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE,
        ).eval()

    @property
    def kb_server(self):
        """延迟获取知识库服务实例"""
        if self._kb_server is None and Config.KNOWLEDGE_BASE_ENABLED:
            try:
                from core.embedding.kb_server import get_kb_server
                self._kb_server = get_kb_server()
            except Exception as e:
                logger.error(f"KB server init error: {e}")
        return self._kb_server

    def stop_generation(self, generation_id: str):
        """停止指定的生成任务"""
        if generation_id in self.active_generations:
            self.active_generations[generation_id]["stop_event"].set()

    async def generate_stream(self, user_message: str, generation_id: str = None, **kwargs):
        """流式生成回复"""
        if generation_id is None:
            generation_id = str(id(user_message))

        if not self._check_model_initialized():
            yield "抱歉，模型未初始化。"
            return

        stop_event = threading.Event()
        text_queue = queue.Queue()

        self.active_generations[generation_id] = {"stop_event": stop_event}
        self.active_queues.add(text_queue)

        try:
            prompt = self._build_legacy_prompt(user_message)
            inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)

            streamer = CustomTextStreamer(
                self.tokenizer, text_queue, stop_event,
                skip_special_tokens=True, skip_prompt=True
            )

            # 启动生成线程
            asyncio.create_task(self._run_generation(inputs, streamer, generation_id, kwargs))

            # 流式输出
            async for text_chunk in self._stream_output(text_queue, generation_id, stop_event):
                yield text_chunk

        except Exception as e:
            logger.error(f"Generation error: {str(e)}")
            yield f"生成过程中出现错误: {str(e)}"
        finally:
            self._cleanup_generation(generation_id, text_queue)

    def _check_model_initialized(self):
        """检查模型是否初始化"""
        if not self._model_initialized:
            logger.error("LLM service not initialized")
            return False
        if self.tokenizer is None:
            logger.error("Tokenizer not initialized")
            raise ModelNotInitializedError("Tokenizer not initialized")
        if self.model is None:
            logger.error("LLM model not initialized")
            raise ModelNotInitializedError("LLM model not initialized")
        return True

    async def _run_generation(self, inputs, streamer, generation_id, kwargs):
        """在后台线程中运行生成过程"""
        def generate():
            try:
                self.model.generate(
                    **inputs,
                    max_new_tokens=kwargs.get('max_new_tokens', Config.MAX_LENGTH),
                    temperature=kwargs.get('temperature', Config.TEMPERATURE),
                    top_p=kwargs.get('top_p', Config.TOP_P),
                    repetition_penalty=kwargs.get('repetition_penalty', Config.REPETITION_PENALTY),
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    streamer=streamer,
                    do_sample=True
                )
            except StopGenerationException:
                logger.info(f"Generation stopped for {generation_id}")
            except Exception as e:
                logger.error(f"Generation thread error: {str(e)}")
                streamer.text_queue.put(('error', str(e)))

        await asyncio.to_thread(generate)

    async def _stream_output(self, text_queue, generation_id, stop_event):
        """流式输出处理"""
        while True:
            try:
                item = await asyncio.to_thread(text_queue.get, timeout=0.1)
                if item[0] == 'error':
                    raise Exception(item[1])
                elif item[0] == 'stopped':
                    yield "\n\n*Generation stopped by user*"
                    break
                elif item[0] == 'done':
                    break
                elif item[0] == 'text':
                    text = self._clean_text(item[1])
                    if text:
                        yield text
            except queue.Empty:
                if (generation_id in self.active_generations and 
                    self.active_generations[generation_id]["stop_event"].is_set()):
                    yield "\n\n*Generation stopped by user*"
                    break
                continue

    def _clean_text(self, text: str) -> str:
        """清理文本中的特殊标记"""
        if "<|im_start|>assistant" in text:
            text = text.split("<|im_start|>assistant")[-1].strip()
        if "<|im_end|>" in text:
            text = text.split("<|im_end|>")[0].strip()
        return text

    def _cleanup_generation(self, generation_id, text_queue):
        """清理生成任务"""
        if generation_id in self.active_generations:
            del self.active_generations[generation_id]
        self.active_queues.discard(text_queue)
        self._cleanup_count += 1
        if self._cleanup_count % 100 == 0:
            logger.debug(f"Generation cleanup count: {self._cleanup_count}")

    def _build_legacy_prompt(self, user_message: str) -> str:
        """为本地LLM构建提示格式"""
        system_prompt = getattr(Config, 'LLM_PROMPT', '')

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        try:
            if hasattr(self.tokenizer, 'apply_chat_template'):
                enable_thinking = not getattr(Config, 'NO_THINK', True)
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=enable_thinking
                )
                return prompt
            else:
                logger.warning("Chat template not found, using manual format")
                return self._manual_chat_format(messages)
        except Exception as e:
            logger.warning(f"Chat template failed: {e}, using manual format")
            return self._manual_chat_format(messages)

    def _manual_chat_format(self, messages: List[Dict[str, str]]) -> str:
        """手动构建聊天格式"""
        return manual_chat_format(messages)

    async def generate_response(self, user_message: str, **kwargs) -> str:
        """生成完整回复（非流式）"""
        if not self._check_model_initialized():
            return "抱歉，模型未初始化。"

        try:
            prompt = self._build_legacy_prompt(user_message)
            inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)

            outputs = self.model.generate(
                **inputs,
                max_new_tokens=kwargs.get('max_new_tokens', Config.MAX_LENGTH),
                temperature=kwargs.get('temperature', Config.TEMPERATURE),
                top_p=kwargs.get('top_p', Config.TOP_P),
                repetition_penalty=kwargs.get('repetition_penalty', Config.REPETITION_PENALTY),
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                do_sample=True
            )

            response = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:],
                skip_special_tokens=True
            ).strip()

            response = self._clean_text(response)
            return response if response else "抱歉，我无法生成有效的回复。"

        except Exception as e:
            return handle_model_error(e)

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if self.model:
            return [{
                "id": Config.LLM_MODEL_NAME,
                "name": Config.LLM_MODEL_NAME,
                "description": "Local LLM Model",
                "provider": "local"
            }]
        return []

    def cleanup(self):
        """清理资源"""
        for generation_id in list(self.active_generations.keys()):
            self.stop_generation(generation_id)
        self.active_generations.clear()
        self.active_queues.clear()


class UnifiedLLMService:
    """LLM服务 - 支持本地和外部LLM"""

    def __init__(self):
        self.local_service = None
        self.service_type = "external" if is_external_llm_enabled() else "local"
        self._tools_enabled = getattr(Config, 'TOOLS_ENABLED', True)
        self._initialized = False

    async def initialize(self):
        """初始化统一LLM服务"""
        if self._initialized:
            return True

        logger.info(f"Initializing LLM service type: {self.service_type}")

        if self.service_type == "external":
            logger.info("Using External LLM API service")
            self._initialized = True
            return True

        # 初始化本地LLM服务
        self.local_service = LocalLLMService()
        success = await self.local_service.initialize()
        self._initialized = success
        return success

    def get_service_type(self):
        """获取当前服务类型"""
        return self.service_type

    def _check_initialized(self) -> bool:
        """检查服务是否已初始化"""
        if not self._initialized:
            logger.warning("LLM service not initialized")
            return False
        return True

    def _prepare_messages(self, user_message: str) -> List[Dict[str, str]]:
        """准备消息格式 - 统一处理消息数组格式"""
        system_prompt = self._get_system_prompt()
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 检查是否已经是OpenAI格式的messages数组
        if (isinstance(user_message, list) and
            all(isinstance(msg, dict) and 'role' in msg and 'content' in msg for msg in user_message)):
            for msg in user_message:
                if msg["role"] != "system":
                    messages.append(msg)
        else:
            messages.append({"role": "user", "content": user_message})

        return messages

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._get_config_value('LLM_PROMPT', '').strip()

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """统一配置访问方法"""
        return getattr(Config, key, default)

    
    def _format_messages_for_external(self, messages: List[Dict[str, str]]) -> str:
        """为外部LLM格式化消息"""
        prompt_parts = []
        system_prompt = getattr(Config, 'LLM_PROMPT', '').strip()

        for message in messages:
            if message["role"] == "system":
                prompt_parts.append(f"System: {message['content']}\n\n")
            elif message["role"] == "user":
                if system_prompt and not any(msg["role"] == "system" for msg in messages):
                    prompt_parts.append(f"System: {system_prompt}\n\n")
                prompt_parts.append(f"User: {message['content']}\n\nAssistant: ")

        return "".join(prompt_parts)

    def _format_messages_for_local(self, messages: List[Dict[str, str]]) -> str:
        """为本地LLM格式化消息"""
        if not self.local_service or not self.local_service.tokenizer:
            return self._format_messages_for_external(messages)

        try:
            enable_thinking = not self._get_config_value('NO_THINK', True)
            text = self.local_service.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking
            )
            return text
        except Exception as e:
            logger.warning(f"Chat template failed: {e}, using manual format")
            return self._manual_chat_format(messages)

    def _manual_chat_format(self, messages: List[Dict[str, str]]) -> str:
        """手动构建聊天格式"""
        return manual_chat_format(messages)

    async def generate_stream(self, user_message: str, generation_id: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成回复"""
        if not self._check_initialized():
            yield "LLM服务未正确初始化。"
            return

        if self.service_type == "external":
            messages = self._prepare_messages(user_message)
            async for chunk in generate_chat_response(
                messages=messages,
                stream=True,
                **kwargs
            ):
                yield chunk
        elif self.local_service:
            async for chunk in self.local_service.generate_stream(
                user_message=user_message,
                generation_id=generation_id,
                **kwargs
            ):
                yield chunk
        else:
            yield "LLM服务未正确初始化。"

    async def generate_response(self, user_message: str, **kwargs) -> str:
        """生成完整回复"""
        if not self._check_initialized():
            return "LLM服务未正确初始化。"

        if self.service_type == "external":
            messages = self._prepare_messages(user_message)
            return await generate_chat_response(
                messages=messages,
                stream=False,
                **kwargs
            )
        elif self.local_service:
            return await self.local_service.generate_response(
                user_message=user_message,
                **kwargs
            )
        else:
            return "LLM服务未正确初始化。"

    async def process_with_tools_support(
        self,
        user_message: str,
        conversation_manager=None,
        user_id: str = None,
        platform: str = None,
        force_web_search=False
    ) -> str:
        """处理用户消息，支持工具调用"""
        if not self._tools_enabled:
            return await self.generate_response(user_message)

        try:
            # 调用tools模块的处理逻辑
            tool_result = await process_with_tools(
                user_message, self.generate_response,
                conversation_manager, user_id, platform,
                force_web_search=force_web_search
            )

            # 如果工具处理成功，返回结果
            if tool_result:
                return tool_result

            # 否则回退到普通LLM响应
            return await self.generate_response(user_message)

        except Exception as e:
            logger.error(f"Tool processing error: {e}")
            return await self.generate_response(user_message)

    def is_tool_supported(self) -> bool:
        """检查是否支持工具功能"""
        return self._tools_enabled

    # 保持向后兼容的方法
    async def process_with_tools(
        self,
        user_message: str,
        conversation_manager=None,
        user_id: str = None,
        platform: str = None,
        force_web_search=False
    ) -> str:
        """使用工具处理用户消息（向后兼容）"""
        return await self.process_with_tools_support(
            user_message,
            conversation_manager,
            user_id,
            platform,
            force_web_search
        )

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if self.service_type == "external":
            return [{
                "id": self._get_config_value('MODEL_NAME', "gpt-3.5-turbo"),
                "name": self._get_config_value('MODEL_NAME', "gpt-3.5-turbo"),
                "description": "External LLM API",
                "provider": "external"
            }]
        else:
            if self.local_service:
                return await self.local_service.list_available_models()
            else:
                return []

    def cleanup(self):
        """清理资源"""
        if self.local_service:
            self.local_service.cleanup()

# 全局服务实例
llm_service = UnifiedLLMService()
