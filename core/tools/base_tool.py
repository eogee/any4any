"""
工具基类 - 定义统一的工具接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """所有工具的基类"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def can_handle(self, user_message: str) -> bool:
        """检测是否能处理该消息"""
        pass

    @abstractmethod
    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        """处理消息并返回结果"""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """工具优先级，数字越小优先级越高"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    def get_tool_schema(self) -> Dict[str, Any]:
        """获取工具Schema（用于LLM调用）"""
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority
        }

    def is_enabled(self) -> bool:
        """检查工具是否启用"""
        return self.enabled

    async def execute(self, parameters: Dict[str, Any]) -> 'ToolResult':
        """
        执行工具的通用方法（可选实现）

        参数:
            parameters: 工具执行参数

        返回:
            ToolResult: 执行结果

        注意:
            如果工具支持直接执行，应该重写此方法
            默认返回不支持的结果
        """
        from .result import ToolResult
        return ToolResult.error_result(
            f"工具 '{self.name}' 不支持直接执行，请使用process方法",
            tool_name=self.name
        )