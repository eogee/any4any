import time
import asyncio
import logging
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

class DelayMessage:
    """延迟消息数据模型"""
    def __init__(self, user_id: str, content: str, request_data: dict):
        self.user_id = user_id
        self.content = content
        self.request_data = request_data
        self.timestamp = time.time()

class DelayManager:
    """延迟消息管理器（单例模式）"""
    _instance = None
    
    def __init__(self):
        # 单例模式初始化检查
        if not hasattr(self, '_buffered_messages'):
            self._buffered_messages: Dict[str, List[DelayMessage]] = {}  # 用户消息缓冲区
            self._processing_tasks: Dict[str, asyncio.Task] = {}         # 处理任务字典
            self._lock = asyncio.Lock()                                  # 异步锁
            self._processing_callbacks: List[Callable] = []              # 处理回调函数列表
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(DelayManager, cls).__new__(cls)
        return cls._instance
    
    def add_processing_callback(self, callback: Callable):
        """添加消息处理回调函数"""
        if callback not in self._processing_callbacks:
            self._processing_callbacks.append(callback)
    
    def remove_processing_callback(self, callback: Callable):
        """移除消息处理回调函数"""
        if callback in self._processing_callbacks:
            self._processing_callbacks.remove(callback)
    
    async def add_message(self, user_id: str, content: str, request_data: dict, delay_time: int) -> Optional[asyncio.Task]:
        """添加消息到缓冲区并设置延迟处理 """
        async with self._lock:
            # 初始化用户消息列表
            if user_id not in self._buffered_messages:
                self._buffered_messages[user_id] = []
            
            # 创建新消息并添加到缓冲区
            new_message = DelayMessage(user_id, content, request_data)
            self._buffered_messages[user_id].append(new_message)
            
            # 取消现有的处理任务（因为有新消息）
            if user_id in self._processing_tasks and not self._processing_tasks[user_id].done():
                self._processing_tasks[user_id].cancel()
            
            # 创建新的延迟处理任务
            task = asyncio.create_task(self._process_after_delay(user_id, delay_time))
            self._processing_tasks[user_id] = task
            return task
    
    async def _process_after_delay(self, user_id: str, delay_time: int):
        """延迟指定时间后处理用户消息"""
        try:
            # 等待延迟时间
            await asyncio.sleep(delay_time)
            
            async with self._lock:
                # 检查是否有待处理消息
                if user_id in self._buffered_messages and self._buffered_messages[user_id]:
                    # 获取并清空用户消息缓冲区
                    messages = self._buffered_messages[user_id].copy()
                    self._buffered_messages[user_id] = []
                    
                    # 合并所有消息内容
                    combined_content = " ".join([msg.content for msg in messages])
                    
                    # 使用最后一条消息的请求数据作为基础
                    latest_request = messages[-1].request_data.copy()
                    
                    # 添加合并消息的相关信息（关键修复）
                    latest_request['combined_content'] = combined_content
                    latest_request['message_count'] = len(messages)
                    latest_request['delay_processed'] = True
                    latest_request['original_message_id'] = f"combined_{int(time.time())}"
                    
                    # 清理处理任务引用
                    if user_id in self._processing_tasks:
                        del self._processing_tasks[user_id]
                    
                    # 执行所有注册的回调函数
                    for callback in self._processing_callbacks:
                        try:
                            await callback(latest_request)
                        except Exception as e:
                            logger.error(f"Callback error for {user_id}: {e}")
                
                # 如果没有消息，清理任务引用
                elif user_id in self._processing_tasks:
                    del self._processing_tasks[user_id]
                    
        except asyncio.CancelledError:
            # 任务被取消（通常是因为有新消息进来）
            logger.debug(f"Processing cancelled for {user_id}")
        except Exception as e:
            logger.error(f"Delay processing error for {user_id}: {e}")
    
    def get_buffered_count(self, user_id: str) -> int:
        """获取用户当前缓冲的消息数量"""
        return len(self._buffered_messages.get(user_id, []))
    
    def clear_buffers(self, user_id: str = None):
        """清空缓冲区"""
        if user_id:
            # 清空指定用户的缓冲区
            if user_id in self._buffered_messages:
                del self._buffered_messages[user_id]
            if user_id in self._processing_tasks:
                self._processing_tasks[user_id].cancel()
                del self._processing_tasks[user_id]
        else:
            # 清空所有缓冲区
            for task in self._processing_tasks.values():
                if not task.done():
                    task.cancel()
            self._buffered_messages.clear()
            self._processing_tasks.clear()

# 全局延迟管理器实例
delay_manager = DelayManager()