import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum
import inspect

logger = logging.getLogger(__name__)

class ToolType(Enum):
    """工具类型枚举"""
    SQL_QUERY = "sql_query"
    DATABASE = "database"
    TABLE_INFO = "table_info"
    CALCULATION = "calculation"
    WEB_SEARCH = "web_search"
    FILE_OPERATION = "file_operation"
    CUSTOM = "custom"

@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None

@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]
    tool_type: ToolType
    function: Callable
    async_function: bool = False

class ToolResult:
    """工具执行结果"""
    def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }

class ToolServer:
    """工具服务器 - 管理和执行各种工具"""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.logger = logging.getLogger(__name__)
        self._register_nl2sql_tools()

    def _register_nl2sql_tools(self):
        """注册NL2SQL工具"""
        try:
            # 注册获取所有表工具
            self.register_tool(
                name="get_all_tables",
                description="获取数据库中所有表的信息，包括表名、注释和基本信息",
                parameters=[],
                function=get_all_tables,
                tool_type=ToolType.TABLE_INFO,
                async_function=False
            )

            # 注册获取相关表结构工具
            self.register_tool(
                name="get_relevant_tables",
                description="根据用户问题获取相关的数据库表结构信息",
                parameters=[
                    ToolParameter(
                        name="question",
                        type="string",
                        description="用户的自然语言问题",
                        required=True
                    )
                ],
                function=get_relevant_tables,
                tool_type=ToolType.TABLE_INFO,
                async_function=False
            )

            # 注册SQL生成和执行工具
            self.register_tool(
                name="generate_and_execute_sql",
                description="根据用户问题和表结构生成SQL查询并执行",
                parameters=[
                    ToolParameter(
                        name="question",
                        type="string",
                        description="用户的自然语言问题",
                        required=True
                    ),
                    ToolParameter(
                        name="table_schemas",
                        type="string",
                        description="数据库表结构信息",
                        required=True
                    ),
                    ToolParameter(
                        name="context",
                        type="string",
                        description="对话上下文信息",
                        required=False,
                        default=""
                    )
                ],
                function=generate_and_execute_sql,
                tool_type=ToolType.SQL_QUERY,
                async_function=True
            )

            self.logger.info("NL2SQL工具注册成功")

        except Exception as e:
            self.logger.error(f"NL2SQL工具注册失败: {e}")

    def register_tool(self,
                     name: str,
                     description: str,
                     parameters: List[ToolParameter],
                     function: Callable,
                     tool_type: ToolType = ToolType.CUSTOM,
                     async_function: bool = False) -> bool:
        """注册工具"""
        try:
            tool_def = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                tool_type=tool_type,
                function=function,
                async_function=async_function
            )

            self.tools[name] = tool_def
            self.logger.info(f"工具 '{name}' 注册成功")
            return True

        except Exception as e:
            self.logger.error(f"工具 '{name}' 注册失败: {e}")
            return False

    def unregister_tool(self, name: str) -> bool:
        """注销工具"""
        if name in self.tools:
            del self.tools[name]
            self.logger.info(f"工具 '{name}' 注销成功")
            return True
        else:
            self.logger.warning(f"工具 '{name}' 未找到，无法注销")
            return False

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        tool_list = []
        for name, tool_def in self.tools.items():
            tool_info = {
                "name": name,
                "description": tool_def.description,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required,
                        "default": param.default,
                        "enum": param.enum
                    }
                    for param in tool_def.parameters
                ],
                "type": tool_def.tool_type.value
            }
            tool_list.append(tool_info)

        return tool_list

    async def execute_tool(self, name: str, parameters: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        if name not in self.tools:
            return ToolResult(
                success=False,
                error=f"工具 '{name}' 未找到"
            )

        tool_def = self.tools[name]

        try:
            # 验证参数
            validation_result = self._validate_parameters(tool_def, parameters)
            if not validation_result.valid:
                return ToolResult(
                    success=False,
                    error=f"参数验证失败: {validation_result.error}"
                )

            # 执行工具函数
            if tool_def.async_function:
                result = await tool_def.function(**validation_result.validated_params)
            else:
                # 在异步上下文中运行同步函数
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: tool_def.function(**validation_result.validated_params)
                )

            # 包装结果
            if isinstance(result, ToolResult):
                return result
            else:
                return ToolResult(
                    success=True,
                    data=result
                )

        except Exception as e:
            self.logger.error(f"工具 '{name}' 执行错误: {e}")
            return ToolResult(
                success=False,
                error=f"工具执行失败: {str(e)}"
            )

    def _validate_parameters(self, tool_def: ToolDefinition, parameters: Dict[str, Any]):
        """验证工具参数"""
        class ValidationResult:
            def __init__(self):
                self.valid = True
                self.error = None
                self.validated_params = {}

        result = ValidationResult()

        # 检查必需参数
        for param in tool_def.parameters:
            if param.required and param.name not in parameters:
                result.valid = False
                result.error = f"缺少必需参数: {param.name}"
                return result

            # 使用默认值
            if param.name not in parameters and param.default is not None:
                result.validated_params[param.name] = param.default
                continue

            # 验证参数类型和枚举值
            if param.name in parameters:
                value = parameters[param.name]

                # 简单类型检查
                if param.type == "string" and not isinstance(value, str):
                    result.valid = False
                    result.error = f"参数 '{param.name}' 必须是字符串"
                    return result

                if param.type == "integer" and not isinstance(value, int):
                    result.valid = False
                    result.error = f"参数 '{param.name}' 必须是整数"
                    return result

                if param.type == "number" and not isinstance(value, (int, float)):
                    result.valid = False
                    result.error = f"参数 '{param.name}' 必须是数字"
                    return result

                if param.type == "boolean" and not isinstance(value, bool):
                    result.valid = False
                    result.error = f"参数 '{param.name}' 必须是布尔值"
                    return result

                # 枚举值检查
                if param.enum and value not in param.enum:
                    result.valid = False
                    result.error = f"参数 '{param.name}' 必须是 {param.enum} 中的一个"
                    return result

                result.validated_params[param.name] = value

        return result

    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具的JSON Schema格式"""
        if name not in self.tools:
            return None

        tool_def = self.tools[name]

        properties = {}
        required = []

        for param in tool_def.parameters:
            param_def = {
                "type": param.type,
                "description": param.description
            }

            if param.enum:
                param_def["enum"] = param.enum

            if param.default is not None:
                param_def["default"] = param.default

            properties[param.name] = param_def

            if param.required:
                required.append(param.name)

        return {
            "name": name,
            "description": tool_def.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def is_sql_question(self, question: str) -> bool:
        """
        判断问题是否需要SQL查询

        参数:
            question: 用户的问题

        返回:
            是否需要SQL查询
        """
        sql_keywords = [
            '查询', '统计', '计算', '显示', '列出', '多少', '几个', '总数', '平均',
            '最高', '最低', '最大', '最小', '排序', '分组', '汇总', '数据', '记录',
            '表', '字段', '数据库', 'SELECT', 'FROM', 'WHERE', 'COUNT', 'SUM', 'AVG',
            'MAX', 'MIN', 'ORDER BY', 'GROUP BY', '产品', '商品', '订单', '库存'
        ]

        data_question_patterns = [
            r'多少.*?个',
            r'多少.*?台',
            r'多少.*?件',
            r'总数.*?是',
            r'平均.*?是',
            r'最高.*?是',
            r'最低.*?是',
            r'列表.*?显示',
            r'统计.*?数据',
            r'查询.*?信息'
        ]

        import re

        question_lower = question.lower()
        has_sql_keywords = any(keyword.lower() in question_lower for keyword in sql_keywords)
        has_data_question = any(re.search(pattern, question, re.IGNORECASE) for pattern in data_question_patterns)

        return has_sql_keywords or has_data_question

# 全局工具服务器实例
_tool_server_instance = None

def get_tool_server() -> ToolServer:
    """获取工具服务器单例实例"""
    global _tool_server_instance
    if _tool_server_instance is None:
        _tool_server_instance = ToolServer()
    return _tool_server_instance

# 装饰器：注册工具
def tool(name: str,
         description: str,
         parameters: List[ToolParameter],
         tool_type: ToolType = ToolType.CUSTOM,
         async_function: bool = False):
    """工具注册装饰器"""
    def decorator(func):
        tool_server = get_tool_server()
        tool_server.register_tool(
            name=name,
            description=description,
            parameters=parameters,
            function=func,
            tool_type=tool_type,
            async_function=async_function
        )
        return func
    return decorator

# 导入NL2SQL工具
from core.tools.nl2sql.table_info import get_all_tables, get_relevant_tables
from core.tools.nl2sql.sql_executor import generate_and_execute_sql