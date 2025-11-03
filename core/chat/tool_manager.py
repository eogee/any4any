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

class ToolManager:
    """工具管理器 - 用于SQL问题识别"""

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
            '表', '字段', '数据库', 'SELECT', 'FROM', 'WHERE', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'ORDER BY', 'GROUP BY', '产品', '商品', '订单', '库存', '车', '辆'
        ]

        # 增加追问相关的关键词
        follow_up_keywords = [
            '分别', '都', '谁', '什么', '哪个', '哪些', '详情', '具体',
            '分别都', '都是谁', '是什么', '有什么', '有哪些'
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
            r'查询.*?信息',
            r'分别.*?是',
            r'都.*?是',
            r'谁.*?是',
            r'有哪些',
            r'什么.*?是'
        ]

        import re

        question_lower = question.lower()
        has_sql_keywords = any(keyword.lower() in question_lower for keyword in sql_keywords)
        has_follow_up_keywords = any(keyword.lower() in question_lower for keyword in follow_up_keywords)
        has_data_question = any(re.search(pattern, question, re.IGNORECASE) for pattern in data_question_patterns)

        # 如果有追问关键词，且有数据相关的上下文（简化的判断）
        # 这里可以通过检查对话历史来增强判断
        has_context_related = any(word in question_lower for word in ['谁', '什么', '哪个', '详情', '具体'])

        return has_sql_keywords or has_data_question or (has_follow_up_keywords and has_context_related)

    def is_voice_kb_question(self, question: str) -> bool:
        """
        判断问题是否适合使用语音知识库回复

        基于问题类型和内容特征进行判断
        """
        try:
            from config import Config
            if not Config.ANY4DH_VOICE_KB_ENABLED:
                return False

            from core.tools.voice_kb.voice_workflow import get_voice_workflow
            workflow = get_voice_workflow()
            return workflow.is_voice_kb_question(question)
        except Exception as e:
            logger.error(f"Voice KB question detection failed: {e}")
            return False

    async def _process_voice_kb_query(self, question: str) -> str:
        """
        处理voice_kb查询并返回标准格式响应

        Returns:
            str: 格式为 "[VOICE_KB_RESPONSE:filename:text]" 的字符串
        """
        try:
            from core.tools.voice_kb.voice_workflow import get_voice_workflow
            workflow = get_voice_workflow()

            result = await workflow.process_voice_query(question)

            if result.get("success") and result.get("should_use_voice"):
                voice_info = result.get("voice_info")
                if voice_info:
                    filename = voice_info.get('audio_file', '')
                    text = voice_info.get('response_text', '')
                    return f"[VOICE_KB_RESPONSE:{filename}:{text}]"
                else:
                    logger.warning("Voice info is empty")
                    return None
            else:
                logger.info(f"Voice KB not suitable: confidence={result.get('confidence', 0):.3f}")
                return None

        except Exception as e:
            logger.error(f"Voice KB processing failed: {e}")
            return None

# 全局工具管理器实例
_tool_manager_instance = None

def get_tool_manager() -> ToolManager:
    """获取工具管理器单例实例"""
    global _tool_manager_instance
    if _tool_manager_instance is None:
        _tool_manager_instance = ToolManager()
    return _tool_manager_instance
