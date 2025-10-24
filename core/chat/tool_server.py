import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

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
    """工具服务器 - 用于SQL问题识别"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._tools = self._initialize_tools()

    def _initialize_tools(self) -> List[Dict[str, Any]]:
        """初始化工具列表"""
        return [
            {
                "name": "sql_query",
                "description": "执行SQL查询，用于数据库操作和数据分析",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要执行的SQL查询语句"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        return self._tools

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行指定的工具

        参数:
            tool_name: 工具名称
            parameters: 工具参数

        返回:
            工具执行结果
        """
        try:
            if tool_name == "sql_query":
                return await self._execute_sql_query(parameters.get("query", ""))
            else:
                return ToolResult(
                    success=False,
                    error=f"未知工具: {tool_name}",
                    metadata={"tool_name": tool_name}
                )
        except Exception as e:
            self.logger.error(f"Tool execution error '{tool_name}': {e}")
            return ToolResult(
                success=False,
                error=f"工具执行失败: {str(e)}",
                metadata={"tool_name": tool_name}
            )

    async def _execute_sql_query(self, query: str) -> ToolResult:
        """
        执行SQL查询

        参数:
            query: SQL查询语句

        返回:
            查询结果
        """
        try:
            # 安全检查：只允许SELECT查询
            if not query.strip().upper().startswith('SELECT'):
                return ToolResult(
                    success=False,
                    error="出于安全考虑，只允许执行SELECT查询",
                    metadata={"query": query}
                )

            # 导入SQL执行器
            from core.tools.nl2sql.sql_executor import sql_executor

            # 执行查询
            result = await sql_executor.execute_query(query)

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "query": query,
                    "type": "sql_query"
                }
            )

        except Exception as e:
            self.logger.error(f"SQL query execution error: {e}")
            return ToolResult(
                success=False,
                error=f"SQL查询执行失败: {str(e)}",
                metadata={"query": query}
            )

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
