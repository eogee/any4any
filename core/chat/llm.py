import logging
from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
import torch
import queue
import asyncio
import time
import gc
from config import Config
import threading

logger = logging.getLogger(__name__)

class CustomTextStreamer(TextStreamer):
    """自定义文本流处理器"""
    def __init__(self, tokenizer, text_queue, stop_event, **kwargs):
        super().__init__(tokenizer, **kwargs)
        self.text_queue = text_queue
        self.stop_event = stop_event
        self.current_text = ""

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
    def load_model(self, model_path, device=None):
        """加载模型并自动选择设备        
        Args:
            model_path: 模型路径
            device: 可选，指定设备(cpu/cuda:0等)，如为None则自动选择
        Returns:
            加载好的模型
        """
        # 自动选择设备
        if device is None:
            if torch.cuda.is_available() and Config.DEVICE.startswith("cuda"):
                device = Config.DEVICE
            else:
                device = "cpu"
        
        # 根据设备类型设置加载参数
        if device == "cpu":
            return AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map="cpu",
                trust_remote_code=Config.TRUST_REMOTE_CODE,
                dtype=torch.float32,  # CPU上不使用半精度
                low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE
            ).eval()
        else:
            # 对于CUDA设备，使用auto让模型自动分配或使用具体设备号
            if device.startswith("cuda"):
                # 提取设备号，如果是cuda:0则使用0，如果只是cuda则使用auto
                if ":" in device:
                    device_id = int(device.split(":")[-1])
                    device_map = {"":device_id}
                else:
                    device_map = "auto"
            else:
                device_map = "auto"
                
            return AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map=device_map,
                trust_remote_code=Config.TRUST_REMOTE_CODE,
                dtype=torch.float16 if Config.USE_HALF_PRECISION else torch.float32,
                low_cpu_mem_usage=Config.LOW_CPU_MEM_USAGE,
                offload_folder="offload",  # 临时offload目录
                offload_state_dict=Config.USE_HALF_PRECISION,  # 半精度时offload状态字典

            ).eval()
    def __init__(self, model_path: str = None):
        self.model_path = model_path or Config.LLM_MODEL_DIR
        self.tokenizer = None
        self.model = None
        # 自动选择设备：如果CUDA可用且配置为GPU设备，则使用GPU，否则使用CPU
        if torch.cuda.is_available() and Config.DEVICE.startswith("cuda"):
            self.device = Config.DEVICE
        else:
            self.device = "cpu"
        self.initialize_model()
        self.active_generations = {}  # 用于跟踪活动的生成任务
        self.active_queues = []  # 用于跟踪活动的队列，避免资源泄漏
        
    def cleanup(self):
        """清理所有资源，避免资源泄漏"""
        logger.info("Cleaning up LLM service resources")
        
        # 停止所有活动的生成任务
        for generation_id in list(self.active_generations.keys()):
            self.stop_generation(generation_id)
        
        # 清空活动生成任务字典
        self.active_generations.clear()
        
        # 清理活动队列 - 向队列中发送完成信号
        for text_queue in self.active_queues:
            try:
                text_queue.put(('done', None), block=False)
            except queue.Full:
                pass
            except Exception as e:
                logger.error(f"Cleanup queue error: {str(e)}")
        
        # 等待一段时间用于处理完成信号
        time.sleep(0.1)

        self.active_queues.clear()

        if hasattr(self, 'model') and self.model is not None:
            try:
                if hasattr(self.model, 'to'):
                    # 将模型移回CPU以释放GPU内存
                    self.model = self.model.to('cpu')
                del self.model
                self.model = None
            except Exception as e:
                logger.error(f"Cleanup model error: {str(e)}")
        
        # 释放分词器资源
        if hasattr(self, 'tokenizer') and self.tokenizer is not None:
            try:
                del self.tokenizer
                self.tokenizer = None
            except Exception as e:
                logger.error(f"Cleanup tokenizer error: {str(e)}")
        
        # 垃圾回收
        gc.collect()
        
        logger.info("LLM服务资源清理完成")

    def initialize_model(self):
        """初始化模型和分词器"""
        try:
            if self.model is not None:
                return
            # 初始化分词器
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=Config.TRUST_REMOTE_CODE
            )
            # 加载模型并优化
            self.model = self.load_model(
                self.model_path,
                device=self.device
            )
        except Exception as e:
            print(f"Model initialization failed: {str(e)}")
            raise e

    def stop_generation(self, generation_id: str):
        """停止指定的生成任务"""
        print(f"Attempting to stop generation task {generation_id}")
        print(f"Current active generations: {list(self.active_generations.keys())}")

        if generation_id in self.active_generations:
            stop_event = self.active_generations[generation_id]["stop_event"]
            stop_event.set()
            print(f"Stop signal sent to generation task {generation_id}")
        else:
            print(f"Generation task {generation_id} not found")

    async def generate_stream(self, user_message: str, generation_id: str = None, temperature: float = None, top_p: float = None, max_new_tokens: int = None, repetition_penalty: float = None):
        """流式生成回复"""
        if generation_id is None:
            generation_id = str(id(user_message))  # 使用消息的id作为生成任务id

        print(f"Starting generation task {generation_id}")

        try:
            # 创建停止事件
            stop_event = threading.Event()
            self.active_generations[generation_id] = {
                "stop_event": stop_event,
                "start_time": asyncio.get_event_loop().time()
            }
            print(f"Generation task {generation_id} created")

            # 构建提示
            prompt = f"<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"

            # 生成输入
            inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)

            # 创建文本流式生成器和队列
            text_queue = queue.Queue()
            self.active_queues.append(text_queue)
            streamer = CustomTextStreamer(
                self.tokenizer,
                text_queue,
                stop_event,
                skip_special_tokens=True,
                skip_prompt=True
            )

            # 使用请求参数或默认配置
            temp = temperature if temperature is not None else Config.TEMPERATURE
            top_p_val = top_p if top_p is not None else Config.TOP_P
            max_tokens = max_new_tokens if max_new_tokens is not None else Config.MAX_LENGTH
            rep_penalty = repetition_penalty if repetition_penalty is not None else Config.REPETITION_PENALTY
            
            # 在后台线程中运行生成过程
            def generate():
                try:
                    self.model.generate(
                        **inputs,
                        max_new_tokens=max_tokens, 
                        num_return_sequences=Config.NUM_RETURN_SEQUENCES,
                        temperature=temp,
                        top_p=top_p_val,
                        repetition_penalty=rep_penalty,
                        pad_token_id=self.tokenizer.pad_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                        streamer=streamer,
                        do_sample=True  # 启用采样以使用temperature和top_p参数
                    )
                except StopGenerationException:
                    print(f"Generation task {generation_id} stopped by user")
                    text_queue.put(('stopped', "Generation stopped by user"))
                except Exception as e:
                    print(f"Generation task {generation_id} error: {str(e)}")
                    text_queue.put(('error', str(e)))
                finally:
                    if generation_id in self.active_generations:
                        del self.active_generations[generation_id]
                        print(f"Generation task {generation_id} cleaned up")

            # 启动生成线程
            generate_thread = asyncio.to_thread(generate)
            asyncio.create_task(generate_thread)

            while True:
                try:
                    item = await asyncio.to_thread(text_queue.get, timeout=0.1)
                    if item[0] == 'error':
                        print(f"Generation task {generation_id} error: {item[1]}")
                        raise Exception(item[1])
                    elif item[0] == 'stopped':
                        print(f"Generation task {generation_id} stopped by user")
                        yield "\n\n*Generation stopped by user*"
                        break
                    elif item[0] == 'done':
                        print(f"Generation task {generation_id} completed")
                        break
                    elif item[0] == 'text':
                        text = item[1]
                        # 处理特殊标记
                        if "<|im_start|>assistant" in text:
                            text = text.split("<|im_start|>assistant")[-1].strip()
                        if "<|im_end|>" in text:
                            text = text.split("<|im_end|>")[0].strip()
                        if text:
                            yield text
                except queue.Empty:
                    # 检查是否应该停止
                    if generation_id in self.active_generations and self.active_generations[generation_id]["stop_event"].is_set():
                        print(f"Generation task {generation_id} stopped by user")
                        yield "\n\n*Generation stopped by user*"
                        break
                    continue
                except Exception as e:
                    print(f"Generation task {generation_id} error: {str(e)}")
                    raise e

        except Exception as e:
            print(f"Generation task {generation_id} error: {str(e)}")
            raise e
        finally:
            # 清理生成任务
            if generation_id in self.active_generations:
                del self.active_generations[generation_id]
                print(f"Generation task {generation_id} cleaned up")
            # 从活动队列列表中移除队列避免资源泄漏
            if 'text_queue' in locals() and text_queue in self.active_queues:
                self.active_queues.remove(text_queue)

    async def generate_response(self, user_message: str, temperature: float = None, top_p: float = None, max_new_tokens: int = None, repetition_penalty: float = None) -> str:
        """生成完整回复（非流式）"""
        try:
            # 使用请求参数或默认配置
            temp = temperature if temperature is not None else Config.TEMPERATURE
            top_p_val = top_p if top_p is not None else Config.TOP_P
            max_tokens = max_new_tokens if max_new_tokens is not None else Config.MAX_LENGTH
            rep_penalty = repetition_penalty if repetition_penalty is not None else Config.REPETITION_PENALTY
            
            # 构建提示
            prompt = f"<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"

            # 生成回复
            inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                num_return_sequences=Config.NUM_RETURN_SEQUENCES,
                temperature=temp, 
                top_p=top_p_val,
                repetition_penalty=rep_penalty, 
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                do_sample=True  # 启用采样以使用temperature和top_p参数
            )

            # 解码并提取回复
            response = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:],  # 只解码新生成的部分
                skip_special_tokens=True
            ).strip()

            # 只取最后一个assistant部分
            if "<|im_start|>assistant" in response:
                response = response.split("<|im_start|>assistant")[-1].strip()
            if "<|im_end|>" in response:
                response = response.split("<|im_end|>")[0].strip()

            # 确保返回有效字符串
            if not response or response.isspace():
                response = "抱歉，我无法生成有效的回复。请稍后再试。"

            return response

        except Exception as e:
            print(f"Generation task error: {str(e)}")
            # 返回默认响应而不是抛出异常
            return "抱歉，处理您的请求时出现错误。请稍后再试。"

# 模块级变量，用于存储模型实例
_global_llm_service = None

def get_llm_service():
    """获取LLM服务实例"""
    global _global_llm_service
    if _global_llm_service is None:
        _global_llm_service = LLMService()
    return _global_llm_service