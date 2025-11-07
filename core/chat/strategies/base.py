"""
处理策略基类
"""
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any

class ProcessingStrategy(ABC):
    """处理策略抽象基类"""

    @abstractmethod
    async def can_handle(self, user_message: str) -> bool:
        """判断是否能处理该消息"""
        pass

    @abstractmethod
    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        """处理消息"""
        pass