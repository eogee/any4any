"""
统一工具执行结果类
"""
from typing import Dict, Any, Optional

class ToolResult:
    """工具执行结果"""

    def __init__(self, success: bool, data: Any = None, error: str = None,
                 metadata: Dict = None, tool_name: str = None):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}
        self.tool_name = tool_name

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "tool_name": self.tool_name
        }

    @classmethod
    def success_result(cls, data: Any, tool_name: str = None,
                      metadata: Dict = None) -> 'ToolResult':
        """创建成功结果"""
        return cls(
            success=True,
            data=data,
            tool_name=tool_name,
            metadata=metadata
        )

    @classmethod
    def error_result(cls, error: str, tool_name: str = None,
                    metadata: Dict = None) -> 'ToolResult':
        """创建错误结果"""
        return cls(
            success=False,
            error=error,
            tool_name=tool_name,
            metadata=metadata
        )

    def __str__(self) -> str:
        if self.success:
            return f"ToolResult(success=True, tool={self.tool_name})"
        else:
            return f"ToolResult(success=False, tool={self.tool_name}, error={self.error})"

    def __repr__(self) -> str:
        return self.__str__()

    def __bool__(self) -> bool:
        """工具结果可以直接用于布尔判断"""
        return self.success