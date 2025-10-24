import logging
import torch
import queue
import asyncio
import threading
from typing import Dict, Any, List, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from config import Config

logger = logging.getLogger(__name__)

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

class StopGenerationException(Exception):
    """用于终止生成的自定义异常"""
    pass

class LLMService:
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self._model_initialized = False
        self.device = Config.DEVICE if torch.cuda.is_available() and Config.DEVICE.startswith("cuda") else "cpu"
        self.active_generations = {}
        self.active_queues = []
        self._kb_server = None  # 延迟初始化，不在构造函数中立即获取
        self._tool_server = None  # 工具服务器实例
        self._tools_enabled = getattr(Config, 'TOOLS_ENABLED', True)  # 是否启用工具
    
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

    @property
    def tool_server(self):
        """延迟获取工具服务器实例"""
        if self._tool_server is None and self._tools_enabled:
            try:
                from core.chat.tool_server import get_tool_server
                self._tool_server = get_tool_server()
            except Exception as e:
                logger.error(f"Tool server init error: {e}")
        return self._tool_server

    def load_model(self, model_path, device=None):
        """加载模型并自动选择设备"""
        if device is None:
            device = self.device
        
        if device == "cpu":
            return AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map="cpu",
                trust_remote_code=Config.TRUST_REMOTE_CODE,
                torch_dtype=torch.float16 if Config.USE_HALF_PRECISION else torch.float32,
                low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE
            ).eval()
        else:
            device_map = "auto"
            if device.startswith("cuda") and ":" in device:
                device_id = int(device.split(":")[-1])
                device_map = {"": device_id}
                
            return AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map=device_map,
                trust_remote_code=Config.TRUST_REMOTE_CODE,
                torch_dtype=torch.float16 if Config.USE_HALF_PRECISION else torch.float32,
                low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE,
                offload_folder="offload",
            ).eval()

    async def initialize_model(self):
        """初始化模型和分词器"""
        if self._model_initialized:
            return
        
        import os
        is_main_process = self._check_main_process()
        
        if not is_main_process:
            logger.info(f"Skipping model loading in non-main process {os.getpid()}")
            return
            
        try:            
            self.tokenizer = AutoTokenizer.from_pretrained(
                Config.LLM_MODEL_DIR,
                trust_remote_code=Config.TRUST_REMOTE_CODE
            )
            
            self.model = self.load_model(Config.LLM_MODEL_DIR, self.device)
            self._model_initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            return False

    def _check_main_process(self):
        """检查是否为主进程"""
        import os
        if os.environ.get('IS_MAIN_PROCESS') == 'true':
            return True
        current_port = os.environ.get('CURRENT_PORT', 'unknown')
        return current_port != '9999' and current_port != 'unknown'

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
            # 构建提示
            prompt = self._build_prompt(user_message)
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

    def _build_prompt(self, user_message: str) -> str:
        """构建提示文本"""
        system_prompt = getattr(Config, 'LLM_PROMPT', '')

        if Config.KNOWLEDGE_BASE_ENABLED and self.kb_server: # 知识库检索
            try:
                retrieval_result = self.kb_server.retrieve_documents(user_message)

                if retrieval_result.get('success') and retrieval_result.get('has_results'):

                    knowledge_content = "\n\n[知识库检索结果]\n"

                    for i, doc in enumerate(retrieval_result.get('documents', []), 1):
                        content = doc.get('chunk_text', '')
                        file_name = doc.get('file_name', '未知文件')
                        knowledge_content += f"【资料{i}】来自文件：{file_name}\n"
                        knowledge_content += f"内容：{content}\n\n"

                    system_prompt += knowledge_content # 将知识库内容添加到system_prompt

            except Exception as e:
                logger.error(f"KB retrieval error: {e}")

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        enable_thinking = not getattr(Config, 'NO_THINK', True)

        try:
            text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking
            )
            return text
        except Exception as e:
            logger.warning(f"Chat template failed: {e}, using manual format")

            return self._manual_chat_format(system_prompt, user_message)

    def _manual_chat_format(self, system_prompt: str, user_message: str) -> str:
        """手动构建聊天格式"""
        if system_prompt:
            return f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"
        else:
            return f"<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"

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

    async def generate_response(self, user_message: str, **kwargs) -> str:
        """生成完整回复（非流式）"""
        if not self._check_model_initialized():
            return "抱歉，模型未初始化。"

        try:
            prompt = self._build_prompt(user_message)

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

    async def process_with_tools(self, user_message: str) -> str:
        """使用工具处理用户消息"""
        if not self._tools_enabled or not self.tool_server:
            return await self.generate_response(user_message)

        try:
            # 检查是否是SQL查询问题 - 使用新的NL2SQL工作流
            if self.tool_server.is_sql_question(user_message):
                from core.tools.nl2sql.workflow import get_nl2sql_workflow

                workflow = get_nl2sql_workflow()
                workflow_result = await workflow.process_sql_question(user_message)

                if workflow_result['success']:
                    return workflow_result['final_answer']
                else:
                    return await self.generate_response(user_message)
            else:
                # 非SQL问题，使用原有的工具分析逻辑
                return await self._process_general_tools(user_message)

        except Exception as e:
            logger.error(f"Tool processing error: {e}")
            return await self.generate_response(user_message)

    async def _process_general_tools(self, user_message: str) -> str:
        """处理通用工具调用"""
        try:
            tool_decision = await self._analyze_tool_needs(user_message)

            if tool_decision["needs_tools"]:
                tool_results = await self._execute_tools(tool_decision["tool_calls"], user_message)
                response = await self._generate_response_with_tools(user_message, tool_results)
                return response
            else:
                return await self.generate_response(user_message)

        except Exception as e:
            logger.error(f"General tool processing error: {e}")
            return await self.generate_response(user_message)

    async def _analyze_tool_needs(self, user_message: str) -> Dict[str, Any]:
        """LLM分析是否需要工具调用"""
        try:
            available_tools = self.get_available_tools()

            if not available_tools:
                return {"needs_tools": False, "tool_calls": []}

            tools_schema = self._build_tools_schema(available_tools)

            system_prompt = "智能助手：判断问题是否需要工具调用。数据查询/计算/外部访问时使用工具，一般对话不需要。"

            user_prompt = f"""问题: {user_message}

可用工具:
{tools_schema}

需要工具时返回：
{{"needs_tools": true, "tool_calls": ["工具名"], "reason": "原因"}}

不需要时返回：
{{"needs_tools": false, "reason": "原因"}}

只返回JSON。"""

            analysis_prompt = f"{system_prompt}\n\n{user_prompt}"
            analysis_result = await self.generate_response(analysis_prompt)

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
                for param in tool['parameters']:
                    required = "必需" if param.get('required', False) else "可选"
                    schema_lines.append(f"    - {param['name']} ({param['type']}, {required}): {param['description']}")

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
                result = await self.tool_server.execute_tool(tool_name, {})

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

    async def _generate_response_with_tools(self, user_message: str, tool_results: List[Dict[str, Any]]) -> str:
        """基于工具结果生成回复"""
        try:
            tool_context = self._build_tool_context(tool_results)
            response_prompt = f"""问题: {user_message}

{tool_context}

基于工具结果回答问题。成功则回答，失败则解释原因。回答自然简洁。"""

            return await self.generate_response(response_prompt)

        except Exception as e:
            logger.error(f"Error generating response with tools: {e}")
            return "获取信息时遇到困难，请稍后再试。"

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

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        if not self._tools_enabled or not self.tool_server:
            return []

        try:
            tools = self.tool_server.get_tool_list()
            return tools
        except Exception as e:
            logger.error(f"Get available tools error: {e}")
            return []

_global_llm_service = None
_llm_service_pid = None

def get_llm_service():
    """获取全局 LLM 服务实例"""
    import os
    global _global_llm_service, _llm_service_pid
    
    current_pid = os.getpid()
    
    if _global_llm_service is None or _llm_service_pid != current_pid:
        _global_llm_service = LLMService()
        _llm_service_pid = current_pid
    
    return _global_llm_service