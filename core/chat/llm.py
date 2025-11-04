import logging
import torch
import queue
import asyncio
import threading
from typing import Dict, Any, List, Optional, AsyncGenerator
from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from config import Config

from .external_llm import generate_chat_response, is_external_llm_enabled

logger = logging.getLogger(__name__)

class StopGenerationException(Exception):
    """停止生成异常"""
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

class ToolProcessor:
    """统一的工具处理器"""
    
    def __init__(self, tools_enabled=True):
        self._tools_enabled = tools_enabled
        self._tool_manager = None

    @property
    def tool_manager(self):
        """延迟获取工具管理器实例"""
        if self._tool_manager is None and self._tools_enabled:
            try:
                from core.chat.tool_manager import get_tool_manager
                self._tool_manager = get_tool_manager()
            except Exception as e:
                logger.error(f"Tool manager init error: {e}")
        return self._tool_manager

    def _is_sql_question(self, user_message: str) -> bool:
        """统一的SQL问题检测 - 使用tool_manager中的实现"""
        if not user_message or not user_message.strip():
            return False

        return self.tool_manager.is_sql_question(user_message)

    def _is_voice_kb_question(self, user_message: str) -> bool:
        """统一的语音知识库问题检测"""
        if not user_message or not user_message.strip():
            return False

        return self.tool_manager.is_voice_kb_question(user_message)

    def _build_tool_context(self, tool_results: List[Dict[str, Any]]) -> str:
        """构建工具结果上下文 - 智能格式化"""
        if not tool_results:
            return ""

        context = "\n## 工具执行结果\n\n"

        for i, tool_result in enumerate(tool_results, 1):
            tool_name = tool_result["tool"]
            result_data = tool_result["result"]

            if result_data.get("success"):
                if tool_name == "sql_query":
                    data = result_data.get("data", {})
                    context += f"**数据库查询结果**:\n"

                    # 提取关键信息
                    if 'formatted_result' in data:
                        # 智能格式化SQL结果
                        formatted = data['formatted_result']
                        if '查询结果:' in formatted:
                            # 提取表格数据
                            lines = formatted.split('\n')
                            data_start = False
                            table_data = []
                            for line in lines:
                                if '查询结果:' in line:
                                    data_start = True
                                elif data_start and line.strip():
                                    table_data.append(line.strip())

                            if table_data:
                                context += "\n".join(table_data[:10])  # 限制显示行数
                                if len(table_data) > 10:
                                    context += f"\n... (共{len(table_data)}行数据)"
                            else:
                                context += formatted
                        else:
                            context += formatted
                    else:
                        context += "查询完成，但没有返回具体数据。"
                else:
                    context += f"**{tool_name} 执行结果**:\n"
                    context += f"{result_data.get('data', '操作完成')}\n"
            else:
                context += f"**工具执行失败** ({tool_name}):\n"
                context += f"错误信息: {result_data.get('error', '未知错误')}\n"

            context += "\n"  # 工具之间的分隔

        return context

    async def process_with_tools(
        self,
        user_message: str,
        generate_response_func,
        conversation_manager=None,
        user_id: str = None,
        platform: str = None
    ) -> str:
        """统一的工具处理逻辑

        Args:
            user_message: 用户消息
            generate_response_func: 响应生成函数
            conversation_manager: 会话管理器实例（用于获取历史记录）
            user_id: 用户ID（用于获取历史记录）
            platform: 平台标识（用于获取历史记录）
        """
        if not self._tools_enabled:
            # 如果不启用工具，仍然要检查知识库
            return await self._process_with_knowledge_base(user_message, generate_response_func)

        try:
            # 检查是否是语音知识库问题
            if self._is_voice_kb_question(user_message):
                voice_result = await self._process_voice_kb(user_message)
                if voice_result:
                    return voice_result  # 返回语音回复标记

            # 检查是否是SQL查询问题
            if self._is_sql_question(user_message):
                from core.tools.nl2sql.workflow import get_nl2sql_workflow
                workflow = get_nl2sql_workflow()
                workflow_result = await workflow.process_sql_question(
                    question=user_message,
                    context="",
                    conversation_manager=conversation_manager,
                    user_id=user_id,
                    platform=platform
                )

                if workflow_result['success']:
                    return workflow_result['final_answer']
                else:
                    error_msg = workflow_result.get('error', '')
                    # 如果是无法确定表的问题，静默回退到正常处理
                    if '无法确定需要查询哪些表' in error_msg or '找不到相关表' in error_msg:
                        logger.info(f"NL2SQL: {error_msg}, falling back to normal LLM response")
                    else:
                        logger.warning(f"NL2SQL workflow failed: {error_msg}")
                    return await self._process_with_knowledge_base(user_message, generate_response_func)
            else:
                # 其它问题，使用一般的工具分析逻辑
                return await self._process_general_tools(user_message, generate_response_func)

        except Exception as e:
            logger.error(f"Tool processing error: {e}")
            return await self._process_with_knowledge_base(user_message, generate_response_func)

    async def _process_with_knowledge_base(self, user_message: str, generate_response_func) -> str:
        """使用知识库处理用户消息"""
        try:
            # 检查知识库
            from config import Config
            if Config.KNOWLEDGE_BASE_ENABLED:
                logger.info(f"Tool processor checking knowledge base for: {user_message}")

                # 获取知识库内容
                from core.embedding.kb_server import get_kb_server
                kb_server = get_kb_server()

                if kb_server:
                    retrieval_result = kb_server.retrieve_documents(user_message)
                    if retrieval_result.get('success') and retrieval_result.get('has_results'):
                        knowledge_content = "\n\n[知识库检索结果]\n"
                        documents = retrieval_result.get('documents', [])
                        logger.info(f"Found {len(documents)} knowledge base documents in tool processor")

                        for i, doc in enumerate(documents, 1):
                            content = doc.get('chunk_text', '')
                            file_name = doc.get('file_name', '未知文件')
                            if content:
                                knowledge_content += f"【资料{i}】来自：{file_name}\n{content}\n\n"

                        # 构建包含知识库的提示
                        enhanced_prompt = f"{user_message}\n{knowledge_content}\n\n请基于以上资料回答问题。"
                        return await generate_response_func(enhanced_prompt)
                    else:
                        logger.info(f"No knowledge base results in tool processor for: {user_message}")
                else:
                    logger.warning("Knowledge base server not available in tool processor")

            # 如果没有知识库内容，直接回复
            return await generate_response_func(user_message)

        except Exception as e:
            logger.error(f"Knowledge base processing in tool processor failed: {e}")
            return await generate_response_func(user_message)

    async def _process_voice_kb(self, user_message: str) -> str:
        """处理语音知识库查询"""
        try:
            from config import Config
            if not Config.ANY4DH_VOICE_KB_ENABLED:
                return None

            from core.tools.voice_kb.voice_workflow import get_voice_workflow

            workflow = get_voice_workflow()
            result = await workflow.process_voice_query(user_message)

            if result["success"] and result["should_use_voice"]:
                voice_info = result["voice_info"]
                if voice_info:
                    # 返回特殊标记，告诉any4dh使用语音文件
                    # 格式: [VOICE_KB_RESPONSE:filename:text_content]
                    return f"[VOICE_KB_RESPONSE:{voice_info['audio_file']}:{voice_info['response_text']}]"
                else:
                    logger.warning("Voice info is empty, falling back to text")
                    return None
            else:
                # 不使用语音，返回None让系统继续处理
                logger.info(f"Voice KB not suitable: confidence={result.get('confidence', 0):.3f}, threshold={result.get('threshold', 0.8)}")
                return None

        except Exception as e:
            logger.error(f"Voice KB processing failed: {e}")
            return None

    async def _process_general_tools(self, user_message: str, generate_response_func) -> str:
        """处理通用工具调用"""
        try:
            # 分析是否需要工具调用
            tool_decision = await self._analyze_tool_needs(user_message, generate_response_func)

            if tool_decision["needs_tools"]:
                tool_results = await self._execute_tools(tool_decision["tool_calls"], user_message)
                response = await self._generate_response_with_tools(user_message, tool_results, generate_response_func)
                return response
            else:
                # 不需要工具，检查知识库
                return await self._process_with_knowledge_base(user_message, generate_response_func)

        except Exception as e:
            logger.error(f"General tool processing error: {e}")
            return await self._process_with_knowledge_base(user_message, generate_response_func)

    async def _analyze_tool_needs(self, user_message: str, generate_response_func) -> Dict[str, Any]:
        """LLM分析是否需要工具调用"""
        try:
            available_tools = self.get_available_tools()

            if not available_tools:
                return {"needs_tools": False, "tool_calls": []}

            tools_schema = self._build_tools_schema(available_tools)

            system_prompt = "智能助手：判断问题是否需要工具调用。数据查询/计算/外部访问时使用工具，一般对话不需要。"

            user_prompt = f"""问题: {user_message}

可用工具:
-{tools_schema}

需要工具时返回：
{{"needs_tools": true, "tool_calls": ["工具名"], "reason": "原因"}}

不需要时返回：
{{"needs_tools": false, "reason": "原因"}}

只返回JSON。"""

            analysis_prompt = f"{system_prompt}\n\n{user_prompt}"
            analysis_result = await generate_response_func(analysis_prompt)

            parsed_decision = self._parse_json_decision(analysis_result, available_tools)
            return parsed_decision

        except Exception as e:
            logger.error(f"Tool analysis error: {e}")
            return {"needs_tools": False, "tool_calls": [], "reason": "工具分析失败"}

    def _build_tools_schema(self, available_tools: List[Dict]) -> str:
        """构建工具的JSON Schema格式描述"""
        schema_lines = []

        for tool in available_tools:
            schema_lines.append(f"{tool['name']}:")
            schema_lines.append(f"  描述: {tool['description']}")

            if tool.get('parameters'):
                schema_lines.append("  参数:")
                parameters = tool['parameters']

                # 处理 properties 字段
                if isinstance(parameters, dict) and 'properties' in parameters:
                    for param_name, param_info in parameters['properties'].items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', '无描述')
                        required_list = parameters.get('required', [])
                        required = "必需" if param_name in required_list else "可选"
                        schema_lines.append(f"    - {param_name} ({param_type}, {required}): {param_desc}")
                else:
                    # 如果格式不符合预期，显示原始信息
                    schema_lines.append(f"    参数格式: {parameters}")

            schema_lines.append("")  # 空行分隔

        return "\n".join(schema_lines)

    def _parse_json_decision(self, analysis_result: str, available_tools: List[Dict]) -> Dict[str, Any]:
        """解析LLM的JSON格式决策"""
        try:
            import json

            # 清理markdown代码块标记
            cleaned_result = analysis_result.strip()

            if cleaned_result.startswith("```json"):
                cleaned_result = cleaned_result[7:]
            elif cleaned_result.startswith("```"):
                cleaned_result = cleaned_result[3:]

            if cleaned_result.endswith("```"):
                cleaned_result = cleaned_result[:-3].strip()

            cleaned_result = cleaned_result.strip()

            if not cleaned_result:
                return {"needs_tools": False, "tool_calls": [], "reason": "返回了空的结果"}

            # 解析JSON
            decision = json.loads(cleaned_result)

            # 验证决策格式
            if not isinstance(decision, dict):
                raise ValueError("Invalid JSON object")

            if 'needs_tools' not in decision:
                raise ValueError("Missing 'needs_tools' field")

            if decision.get('needs_tools') and 'tool_calls' not in decision:
                raise ValueError("Missing 'tool_calls' field")

            # 验证工具是否可用
            valid_tools = []
            available_tool_names = [tool['name'] for tool in available_tools]

            if decision.get('needs_tools') and decision.get('tool_calls'):
                for tool_name in decision['tool_calls']:
                    if tool_name in available_tool_names:
                        valid_tools.append(tool_name)

            return {
                "needs_tools": decision.get('needs_tools', False) and len(valid_tools) > 0,
                "tool_calls": valid_tools,
                "reason": decision.get('reason', '无原因说明')
            }

        except json.JSONDecodeError:
            return {"needs_tools": False, "tool_calls": [], "reason": "返回了无效的JSON格式"}

        except Exception as e:
            logger.error(f"Decision parsing error: {e}")
            return {"needs_tools": False, "tool_calls": [], "reason": f"决策解析失败: {str(e)}"}

    async def _execute_tools(self, tool_names: List[str], user_message: str) -> List[Dict[str, Any]]:
        """执行工具调用"""
        tool_results = []

        for tool_name in tool_names:
            try:
                result = await self.tool_manager.execute_tool(tool_name, {})

                tool_results.append({
                    "tool": tool_name,
                    "result": result.to_dict()
                })

            except Exception as e:
                logger.error(f"Tool execution error '{tool_name}': {e}")
                tool_results.append({
                    "tool": tool_name,
                    "result": {"success": False, "error": str(e)}
                })

        return tool_results

    async def _generate_response_with_tools(self, user_message: str, tool_results: List[Dict[str, Any]], generate_response_func) -> str:
        """基于工具结果生成回复"""
        try:
            tool_context = self._build_tool_context(tool_results)
            response_prompt = f"""问题: {user_message}

-{tool_context}

基于工具结果回答问题。成功则回答，失败则解释原因。回答自然简洁。"""

            return await generate_response_func(response_prompt)

        except Exception as e:
            logger.error(f"Error generating response with tools: {e}")
            return "获取信息时遇到困难，请稍后再试。"

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        if not self._tools_enabled or not self.tool_manager:
            return []

        try:
            tools = self.tool_manager.get_tool_list()
            return tools
        except Exception as e:
            logger.error(f"Get available tools error: {e}")
            return []

class LegacyLLMService:
    """本地LLM服务 - 保持向后兼容"""

    def __init__(self):
        """初始化本地LLM服务"""
        from config import Config
        from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
        import torch
        import queue
        import threading

        self.tokenizer = None
        self.model = None
        self._model_initialized = False
        self.device = Config.DEVICE if torch.cuda.is_available() and Config.DEVICE.startswith("cuda") else "cpu"
        self.active_generations = {}
        self.active_queues = []
        self._kb_server = None  # 延迟初始化，不在构造函数中立即获取

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

        # 初始化本地LLM服务
        import os
        is_main_process = self._check_main_process()
        if not is_main_process:
            logger.info(f"Skipping model loading in non-main process {os.getpid()}")
            return

        try:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                Config.LLM_MODEL_DIR,
                trust_remote_code=Config.TRUST_REMOTE_CODE,
                torch_dtype=torch.float16 if Config.USE_HALF_PRECISION else torch.float32,
                low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE
            )

            self.model = self.load_model(
                Config.LLM_MODEL_DIR,
                device=self.device
            )

            self._model_initialized = True
            return True

        except Exception as e:
            logger.error(f"Legacy LLM model loading failed: {e}")
            return False

    def _check_main_process(self):
        """检查是否主进程"""
        import os
        current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
        return current_port != str(Config.MCP_PORT)

    def load_model(self, model_path, device=None):
        """加载模型并自动选择设备"""
        if device is None:
            device = self.device

        from transformers import AutoModelForCausalLM, TextStreamer
        return AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map=device if device.startswith("cuda") else "cpu",
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
        self.active_generations[generation_id] = {"stop_event": stop_event}

        try:
            # 构建提示 - 使用本地LLM的格式
            prompt = self._build_legacy_prompt(user_message)
            inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)

            text_queue = queue.Queue()
            self.active_queues.append(text_queue)

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
            raise e
        finally:
            self._cleanup_generation(generation_id, text_queue)

    def _check_model_initialized(self):
        """检查模型是否初始化"""
        if not hasattr(self, 'tokenizer') or self.tokenizer is None:
            logger.error("Tokenizer not initialized")
            return False
        if not hasattr(self, 'model') or self.model is None:
            logger.error("LLM model not initialized")
            return False
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
                pass
            except Exception as e:
                logger.error(f"Generation thread error: {str(e)}")

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
                if generation_id in self.active_generations and self.active_generations[generation_id]["stop_event"].is_set():
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
        if text_queue in self.active_queues:
            self.active_queues.remove(text_queue)

    def _build_legacy_prompt(self, user_message: str) -> str:
        """为本地LLM构建提示格式"""
        system_prompt = getattr(Config, 'LLM_PROMPT', '')

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        # 使用tokenizer的chat template
        try:
            if hasattr(self.tokenizer, 'apply_chat_template'):
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                     enable_thinking=not getattr(Config, 'NO_THINK', True)
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
        prompt = ""
        for message in messages:
            if message["role"] == "system":
                prompt += f"<|im_start|>system\n{message['content']}<|im_end|>\n"
            elif message["role"] == "user":
                prompt += f"<|im_start|>user\n{message['content']}<|im_end|>\n"

        prompt += "<|im_start|>assistant\n"
        return prompt

    async def generate_response(self, user_message: str, **kwargs) -> str:
        """生成完整回复（非流式）"""
        if not self._check_model_initialized():
            return "抱歉，模型未初始化。"

        try:
            # 构建提示 - 使用本地LLM的格式
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
            logger.error(f"LLM generation error: {str(e)}")
            return "抱歉，处理您的请求时出现错误。"

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if hasattr(self, 'model') and self.model:
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
    """统一的LLM服务 - 支持本地和外部LLM"""

    def __init__(self):
        self.legacy_service = None
        self.service_type = "external" if is_external_llm_enabled() else "local"
        self.tool_processor = ToolProcessor(getattr(Config, 'TOOLS_ENABLED', True))
        # 为了向后兼容，添加 _tools_enabled 属性
        self._tools_enabled = self.tool_processor._tools_enabled

    async def initialize(self):
        """初始化统一LLM服务"""
        logger.info(f"LLM service type: {self.service_type}")

        if self.service_type == "external":
            logger.info("Using External LLM API service")
            return True

        # 初始化本地LLM服务
        self.legacy_service = LegacyLLMService()
        return await self.legacy_service.initialize()

    def get_service_type(self):
        """获取当前服务类型"""
        return self.service_type

    def _build_prompt(self, user_message: str) -> str:
        """统一的提示构建方法 - 公共一致的接口"""
        system_prompt = getattr(Config, 'LLM_PROMPT', '')
        
        # 知识库检索 - 统一处理
        if Config.KNOWLEDGE_BASE_ENABLED:
            kb_content = self._retrieve_knowledge_base(user_message)
            if kb_content:
                system_prompt += kb_content

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        # 根据服务类型使用不同的格式化方式
        if self.service_type == "external":
            # 外部LLM直接使用OpenAI格式
            return self._format_messages_for_external(messages)
        else:
            # 本地LLM使用tokenizer的格式化方法
            return self._format_messages_for_local(messages)

    def _retrieve_knowledge_base(self, user_message: str) -> str:
        """统一的知识库检索"""
        if not Config.KNOWLEDGE_BASE_ENABLED:
            return ""

        try:
            logger.info(f"Attempting knowledge base retrieval for: {user_message}")

            # 直接获取知识库服务器，不依赖服务类型
            from core.embedding.kb_server import get_kb_server
            kb_server = get_kb_server()

            if not kb_server:
                logger.warning("Knowledge base server not available")
                return ""

            retrieval_result = kb_server.retrieve_documents(user_message)
            logger.debug(f"KB retrieval result: {retrieval_result}")

            if retrieval_result.get('success') and retrieval_result.get('has_results'):
                knowledge_content = "\n\n[知识库检索结果]\n"
                documents = retrieval_result.get('documents', [])
                logger.info(f"Found {len(documents)} knowledge base documents")

                for i, doc in enumerate(documents, 1):
                    content = doc.get('chunk_text', '')
                    file_name = doc.get('file_name', '未知文件')
                    if content:
                        knowledge_content += f"【资料{i}】来自：{file_name}\n{content}\n\n"

                return knowledge_content
            else:
                logger.info(f"No knowledge base results for: {user_message}")
                return ""

        except Exception as e:
            logger.error(f"Knowledge base retrieval failed: {e}")
            return ""

    def _format_messages_for_external(self, messages: List[Dict[str, str]]) -> str:
        """为外部LLM格式化消息 - 支持系统提示词"""
        from config import Config

        system_prompt = getattr(Config, 'LLM_PROMPT', '').strip()

        prompt_parts = []

        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n\n")
            for message in messages:
                if message["role"] == "user":
                    prompt_parts.append(f"User: {message['content']}\n\nAssistant: ")
        else:
            for message in messages:
                if message["role"] == "system":
                    prompt_parts.append(f"System: {message['content']}\n\n")
                elif message["role"] == "user":
                    prompt_parts.append(f"User: {message['content']}\n\nAssistant: ")

        return "".join(prompt_parts)

    def _format_messages_for_local(self, messages: List[Dict[str, str]]) -> str:
        """为本地LLM格式化消息"""
        if not self.legacy_service or not self.legacy_service.tokenizer:
            return self._format_messages_for_external(messages)
            
        try:
            enable_thinking = not getattr(Config, 'NO_THINK', True)
            text = self.legacy_service.tokenizer.apply_chat_template(
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
        prompt = ""
        for message in messages:
            if message["role"] == "system":
                prompt += f"<|im_start|>system\n{message['content']}<|im_end|>\n"
            elif message["role"] == "user":
                prompt += f"<|im_start|>user\n{message['content']}<|im_end|>\n"
        
        prompt += "<|im_start|>assistant\n"
        return prompt

    def _format_messages(self, user_message: str) -> List[Dict[str, str]]:
        """格式化消息为对话格式"""
        return [
            {"role": "user", "content": user_message}
        ]

    async def generate_stream(self, user_message: str, generation_id: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成回复"""
        if self.service_type == "external":
            from config import Config

            system_prompt = getattr(Config, 'LLM_PROMPT', '').strip()

            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 检查user_message是否已经是OpenAI格式的messages数组
            if isinstance(user_message, list) and all(isinstance(msg, dict) and 'role' in msg and 'content' in msg for msg in user_message):

                for msg in user_message:
                    if msg["role"] != "system":
                        messages.append(msg)
            else:
                # 是字符串，转换为OpenAI格式
                messages.append({"role": "user", "content": user_message})

            async for chunk in generate_chat_response(
                messages=messages,
                stream=True,
                **kwargs
            ):
                yield chunk
        elif self.legacy_service:
            async for chunk in self.legacy_service.generate_stream(
                user_message=user_message,
                generation_id=generation_id,
                **kwargs
            ):
                yield chunk
        else:
            yield "LLM服务未正确初始化。"

    async def generate_response(self, user_message: str, **kwargs) -> str:
        """生成完整回复"""
        if self.service_type == "external":
            from config import Config

            system_prompt = getattr(Config, 'LLM_PROMPT', '').strip()

            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 检查user_message是否已经是OpenAI格式的messages数组
            if isinstance(user_message, list) and all(isinstance(msg, dict) and 'role' in msg and 'content' in msg for msg in user_message):

                for msg in user_message:
                    if msg["role"] != "system":
                        messages.append(msg)
            else:
                # 是字符串，转换为OpenAI格式
                messages.append({"role": "user", "content": user_message})

            return await generate_chat_response(
                messages=messages,
                stream=False,
                **kwargs
            )
        elif self.legacy_service:
            return await self.legacy_service.generate_response(
                user_message=user_message,
                **kwargs
            )
        else:
            return "LLM服务未正确初始化。"

    async def generate_response_with_tools(self, user_message: str, tool_results: List[Dict[str, Any]], **kwargs) -> str:
        """基于工具结果生成回复"""
        try:
            # 统一的工具结果处理
            tool_context = self.tool_processor._build_tool_context(tool_results)
            response_prompt = f"""问题: {user_message}

-{tool_context}

基于工具结果回答问题。成功则回答，失败则解释原因。回答自然简洁。"""

            return await self.generate_response(response_prompt)

        except Exception as e:
            logger.error(f"Error generating response with tools: {e}")
            return "获取信息时遇到困难，请稍后再试。"

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if self.service_type == "external":
            return await self.llm_manager.list_available_models()
        elif self.legacy_service:
            return await self.legacy_service.list_available_models()
        else:
            return []

    def cleanup(self):
        """清理资源"""
        if self.legacy_service:
            return self.legacy_service.cleanup()

    async def process_with_tools(
        self,
        user_message: str,
        conversation_manager=None,
        user_id: str = None,
        platform: str = None
    ) -> str:
        """使用工具处理用户消息"""
        return await self.tool_processor.process_with_tools(
            user_message,
            self.generate_response,
            conversation_manager,
            user_id,
            platform
        )

    def is_tool_supported(self) -> bool:
        """检查是否支持工具功能"""
        return self.tool_processor._tools_enabled

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if self.service_type == "external":
            # 对于外部API，返回配置的模型信息
            return [{
                "id": getattr(Config, 'MODEL_NAME', "gpt-3.5-turbo"),
                "name": getattr(Config, 'MODEL_NAME', "gpt-3.5-turbo"),
                "description": "External LLM API",
                "provider": "external"
            }]
        else:
            # 对于本地模型，返回本地模型信息
            if self.legacy_service:
                return await self.legacy_service.list_available_models()
            else:
                return []

    def cleanup(self):
        """清理资源"""
        if self.legacy_service:
            return self.legacy_service.cleanup()

# 向后兼容的全局服务实例
llm_service = UnifiedLLMService()

# 向后兼容的函数
_global_llm_service = None
_llm_service_pid = None

def get_llm_service():
    """获取全局 LLM 服务实例 - 向后兼容"""
    import os
    global _global_llm_service, _llm_service_pid

    current_pid = os.getpid()

    if _global_llm_service is None or _llm_service_pid != current_pid:
        _global_llm_service = llm_service
        _llm_service_pid = current_pid

    return _global_llm_service