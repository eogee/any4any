import logging
import torch
import queue
import asyncio
import threading
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
    
    @property
    def kb_server(self):
        """延迟获取知识库服务实例"""
        if self._kb_server is None and Config.KNOWLEDGE_BASE_ENABLED:
            try:
                from core.embedding.kb_server import get_kb_server # 延迟导入，避免循环依赖
                self._kb_server = get_kb_server()
            except Exception as e:
                logger.error(f"Failed to get knowledge base server: {e}")
        return self._kb_server

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
                # offload_state_dict=Config.USE_HALF_PRECISION,
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
            
            logger.info(f"LLM is generating stream...")
            
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
                logger.error(f"Knowledge base retrieval error: {str(e)}")
        
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

            logger.info(f"LLM is generating response...")

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