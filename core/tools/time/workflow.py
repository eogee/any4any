"""
时间工具 - 提供时间相关的工具功能
"""
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from ..base_tool import BaseTool
from ..result import ToolResult
from .time_utils import get_time_utils

logger = logging.getLogger(__name__)

class TimeTool(BaseTool):
    """时间工具 - 提供时间查询、解析和SQL时间条件生成"""

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self.time_utils = get_time_utils()

    @property
    def priority(self) -> int:
        return 3  # 中等优先级

    @property
    def name(self) -> str:
        return "time"

    @property
    def description(self) -> str:
        return "时间工具，支持时间查询、自然语言时间解析和SQL时间条件生成"

    async def can_handle(self, user_message: str) -> bool:
        """检测是否为时间相关问题"""
        if not user_message or not user_message.strip() or not self.enabled:
            return False

        # 检查配置
        try:
            from config import Config
            if not getattr(Config, 'TIME_TOOLS_ENABLED', True):
                return False
        except Exception as e:
            self.logger.warning(f"Failed to check TIME_TOOLS_ENABLED: {e}")
            return False

        # 现在由LLM进行功能识别，工具本身不做关键词检测
        # 只检查是否启用和基本配置
        return True

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        """处理时间相关请求"""
        try:
            # 使用LLM进行智能意图识别和响应生成
            return await self._process_with_llm(
                user_message, generate_response_func,
                conversation_manager, user_id, platform
            )

        except Exception as e:
            self.logger.error(f"Time tool processing failed: {e}")
            return f"时间处理失败: {str(e)}"

    async def _process_with_llm(self, user_message: str, generate_response_func: Callable,
                              conversation_manager=None, user_id: str = None,
                              platform: str = None) -> Optional[str]:
        """使用LLM进行智能时间处理"""
        try:
            # 获取当前时间信息
            current_time_result = await self._get_current_time({})
            current_time_info = ""
            if current_time_result.success and current_time_result.data.get("success"):
                current_time_info = current_time_result.data.get('current_time', '')

            # 尝试提取时间表达式
            expressions = self.time_utils.extract_time_expressions(user_message)
            expressions_info = ""
            if expressions:
                expressions_info = "识别到的时间表达式: " + ", ".join(expressions) + "\n"
                for expr in expressions:
                    parse_result = self.time_utils.parse_time_expression(expr)
                    if parse_result.get("success"):
                        expressions_info += f"'{expr}' 解析结果: {parse_result}\n"
                    else:
                        expressions_info += f"'{expr}' 解析失败: {parse_result.get('error', '未知错误')}\n"

            # 构建LLM提示词
            prompt = f"""你是一个时间助手，请根据用户的时间相关问题提供准确和友好的回答。

用户问题: {user_message}

当前时间: {current_time_info}

{expressions_info}

请根据用户问题和我提供的时间信息，生成自然、友好的回答。回答要求：
1. 如果用户询问当前时间，直接告诉用户时间
2. 如果用户询问时间表达式，解释解析结果
3. 如果用户需要时间相关的其他帮助，提供适当的指导
4. 语言要自然、礼貌、简洁

请直接回答用户问题，不要添加其他说明：
"""

            # 调用LLM生成智能响应
            response = await generate_response_func(prompt)

            # 清理响应，移除可能的格式标记
            if response:
                response = response.strip()
                # 移除可能的引号
                if response.startswith('"') and response.endswith('"'):
                    response = response[1:-1]

            return response if response else "抱歉，我无法处理您的时间请求。"

        except Exception as e:
            self.logger.error(f"LLM time processing failed: {e}")
            # 回退到简单处理
            return await self._fallback_processing(user_message)

    async def _fallback_processing(self, user_message: str) -> Optional[str]:
        """回退处理逻辑"""
        try:
            message_lower = user_message.lower()

            if '现在' in message_lower or '当前' in message_lower or '今天' in message_lower:
                result = await self._get_current_time({})
                if result.success and result.data.get("success"):
                    return f"当前时间: {result.data.get('current_time', '未知')}"
                else:
                    return "获取时间失败"

            return "请明确您需要的时间操作，如查询当前时间等"

        except Exception as e:
            return f"时间处理失败: {str(e)}"

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行时间工具方法（兼容原接口）"""
        try:
            operation = parameters.get("operation", "")

            if operation == "get_current_time":
                return await self._get_current_time(parameters)

            elif operation == "parse_time_expression":
                return await self._parse_time_expression(parameters)

            elif operation == "generate_sql_time_condition":
                return await self._generate_sql_time_condition(parameters)

            else:
                return ToolResult.error_result(
                    f"不支持的操作: {operation}",
                    tool_name=self.name
                )

        except Exception as e:
            self.logger.error(f"Time tool execution failed: {e}")
            return ToolResult.error_result(
                f"时间工具执行失败: {str(e)}",
                tool_name=self.name
            )

    async def _get_current_time(self, parameters: Dict[str, Any]) -> ToolResult:
        """获取当前时间"""
        try:
            time_format = parameters.get("format", "%Y-%m-%d %H:%M:%S")
            result = self.time_utils.get_current_time(time_format)

            return ToolResult(
                success=result.get("success", False),
                data=result,
                tool_name=self.name,
                metadata={"operation": "get_current_time", "format": time_format}
            )
        except Exception as e:
            self.logger.error(f"Get current time failed: {e}")
            return ToolResult.error_result(str(e), tool_name=self.name)

    async def _parse_time_expression(self, parameters: Dict[str, Any]) -> ToolResult:
        """解析时间表达式"""
        try:
            expression = parameters.get("expression", "")
            base_date = parameters.get("base_date", "")

            if not expression:
                return ToolResult.error_result(
                    "缺少必需参数: expression",
                    tool_name=self.name
                )

            result = self.time_utils.parse_time_expression(expression, base_date)

            return ToolResult(
                success=result.get("success", False),
                data=result,
                tool_name=self.name,
                metadata={
                    "operation": "parse_time_expression",
                    "expression": expression,
                    "base_date": base_date
                }
            )
        except Exception as e:
            self.logger.error(f"Parse time expression failed: {e}")
            return ToolResult.error_result(str(e), tool_name=self.name)

    async def _generate_sql_time_condition(self, parameters: Dict[str, Any]) -> ToolResult:
        """生成SQL时间条件"""
        try:
            import json

            time_range = parameters.get("time_range", "")
            column_name = parameters.get("column_name", "")
            date_format = parameters.get("date_format", "YYYY-MM-DD")

            if not time_range:
                return ToolResult.error_result(
                    "缺少必需参数: time_range",
                    tool_name=self.name
                )

            if not column_name:
                return ToolResult.error_result(
                    "缺少必需参数: column_name",
                    tool_name=self.name
                )

            # 解析时间范围信息
            if isinstance(time_range, str):
                try:
                    time_range_info = json.loads(time_range)
                except json.JSONDecodeError:
                    return ToolResult.error_result(
                        "time_range 参数格式错误，应为有效的JSON字符串",
                        tool_name=self.name
                    )
            else:
                time_range_info = time_range

            sql_condition = self.time_utils.generate_sql_time_range(time_range_info, column_name, date_format)

            return ToolResult.success_result(
                data={
                    "sql_condition": sql_condition,
                    "column_name": column_name,
                    "date_format": date_format,
                    "time_range_info": time_range_info
                },
                tool_name=self.name,
                metadata={
                    "operation": "generate_sql_time_condition",
                    "column_name": column_name
                }
            )
        except Exception as e:
            self.logger.error(f"Generate SQL time condition failed: {e}")
            return ToolResult.error_result(str(e), tool_name=self.name)

# 工厂函数
def get_time_tool() -> TimeTool:
    """获取时间工具实例"""
    return TimeTool()