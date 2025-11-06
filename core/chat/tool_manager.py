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
        tools = []

        # 检查是否启用NL2SQL工具
        try:
            from config import Config
            if getattr(Config, 'NL2SQL_ENABLED', True):
                tools.append({
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
                })
        except Exception as e:
            self.logger.warning(f"Failed to check NL2SQL_ENABLED setting: {e}")

        # 检查工具系统总开关
        try:
            from config import Config
            if not getattr(Config, 'TOOLS_ENABLED', True):
                self.logger.info("Tools system is disabled globally")
                return tools
        except Exception as e:
            self.logger.warning(f"Failed to check TOOLS_ENABLED setting: {e}")

        # 检查是否启用时间工具
        try:
            from config import Config
            if getattr(Config, 'TIME_TOOLS_ENABLED', True):
                tools.extend([
                    # 获取当前时间工具
                    {
                        "name": "get_current_time",
                        "description": "获取当前系统时间，用于时间相关查询",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "format": {
                                    "type": "string",
                                    "description": "时间格式，如'%Y-%m-%d'、'%Y-%m-%d %H:%M:%S'等",
                                    "default": "%Y-%m-%d %H:%M:%S"
                                }
                            },
                            "required": []
                        }
                    },
                    # 解析时间表达式工具
                    {
                        "name": "parse_time_expression",
                        "description": "解析自然语言时间表达式为具体时间范围，支持'本月'、'最近7天'、'2024年1月'等",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "时间表达式，如'本月'、'最近7天'、'2024年1月'等"
                                },
                                "base_date": {
                                    "type": "string",
                                    "description": "基准日期，格式为YYYY-MM-DD，默认为当前日期",
                                    "default": ""
                                }
                            },
                            "required": ["expression"]
                        }
                    },
                    # 生成SQL时间条件工具
                    {
                        "name": "generate_sql_time_condition",
                        "description": "为SQL查询生成时间范围条件",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "time_range": {
                                    "type": "string",
                                    "description": "时间范围信息，来自parse_time_expression的结果（JSON格式字符串）"
                                },
                                "column_name": {
                                    "type": "string",
                                    "description": "时间字段名称，如'create_time'、'order_date'等"
                                },
                                "date_format": {
                                    "type": "string",
                                    "description": "数据库中日期字段的格式，如'YYYY-MM-DD'、'DATETIME'等",
                                    "default": "YYYY-MM-DD"
                                }
                            },
                            "required": ["time_range", "column_name"]
                        }
                    }
                ])
        except Exception as e:
            self.logger.warning(f"Failed to check TIME_TOOLS_ENABLED setting: {e}")

        # 检查是否启用ADB工具
        try:
            from config import Config
            if getattr(Config, 'ADB_TOOLS_ENABLED', False):
                tools.extend([
                    {
                        "name": "adb_login",
                        "description": "通过ADB自动化登录App，需要先确保设备已连接并打开App",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "adb_logout",
                        "description": "通过ADB自动化登出App",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "adb_query_bill",
                        "description": "通过ADB自动化查询电费账单",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "adb_pay_bill",
                        "description": "通过ADB自动化缴纳电费",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "amount": {
                                    "type": "integer",
                                    "description": "缴费金额（元），必须大于0"
                                }
                            },
                            "required": ["amount"]
                        }
                    },
                    {
                        "name": "get_adb_status",
                        "description": "获取ADB工具状态信息，包括连接状态和登录状态",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                ])
        except Exception as e:
            self.logger.warning(f"Failed to check ADB_TOOLS_ENABLED setting: {e}")

        return tools

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
                self.logger.info(f"Using tool:sql_query")
                return await self._execute_sql_query(parameters.get("query", ""))
            elif tool_name == "get_current_time":
                self.logger.info(f"Using tool:get_current_time")
                return await self._get_current_time(parameters)
            elif tool_name == "parse_time_expression":
                self.logger.info(f"Using tool:parse_time_expression")
                return await self._parse_time_expression(parameters)
            elif tool_name == "generate_sql_time_condition":
                self.logger.info(f"Using tool:generate_sql_time_condition")
                return await self._generate_sql_time_condition(parameters)
            # ADB工具执行
            elif tool_name == "adb_login":
                self.logger.info(f"Using tool:adb_login")
                return await self._execute_adb_login(parameters)
            elif tool_name == "adb_logout":
                self.logger.info(f"Using tool:adb_logout")
                return await self._execute_adb_logout(parameters)
            elif tool_name == "adb_query_bill":
                self.logger.info(f"Using tool:adb_query_bill")
                return await self._execute_adb_query_bill(parameters)
            elif tool_name == "adb_pay_bill":
                self.logger.info(f"Using tool:adb_pay_bill")
                return await self._execute_adb_pay_bill(parameters)
            elif tool_name == "get_adb_status":
                self.logger.info(f"Using tool:get_adb_status")
                return await self._get_adb_status(parameters)
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
        # 首先检查NL2SQL是否启用
        try:
            from config import Config
            if not getattr(Config, 'NL2SQL_ENABLED', True):
                return False
        except Exception as e:
            self.logger.warning(f"Failed to check NL2SQL_ENABLED: {e}")
            return False
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

        # 如果有追问关键词，且有数据相关的上下文
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

    # ========== 时间工具执行方法 ==========

    async def _get_current_time(self, parameters: Dict[str, Any]) -> ToolResult:
        """获取当前时间"""
        try:
            from core.tools.nl2sql.time_utils import get_time_utils
            time_utils = get_time_utils()

            time_format = parameters.get("format", "%Y-%m-%d %H:%M:%S")
            result = time_utils.get_current_time(time_format)

            return ToolResult(
                success=result.get("success", False),
                data=result,
                metadata={"tool_name": "get_current_time", "format": time_format}
            )
        except Exception as e:
            self.logger.error(f"Get current time failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _parse_time_expression(self, parameters: Dict[str, Any]) -> ToolResult:
        """解析时间表达式"""
        try:
            from core.tools.nl2sql.time_utils import get_time_utils
            time_utils = get_time_utils()

            expression = parameters.get("expression", "")
            base_date = parameters.get("base_date", "")

            if not expression:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: expression",
                    metadata={"tool_name": "parse_time_expression"}
                )

            result = time_utils.parse_time_expression(expression, base_date)

            return ToolResult(
                success=result.get("success", False),
                data=result,
                metadata={
                    "tool_name": "parse_time_expression",
                    "expression": expression,
                    "base_date": base_date
                }
            )
        except Exception as e:
            self.logger.error(f"Parse time expression failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _generate_sql_time_condition(self, parameters: Dict[str, Any]) -> ToolResult:
        """生成SQL时间条件"""
        try:
            from core.tools.nl2sql.time_utils import get_time_utils
            import json

            time_utils = get_time_utils()

            time_range = parameters.get("time_range", "")
            column_name = parameters.get("column_name", "")
            date_format = parameters.get("date_format", "YYYY-MM-DD")

            if not time_range:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: time_range",
                    metadata={"tool_name": "generate_sql_time_condition"}
                )

            if not column_name:
                return ToolResult(
                    success=False,
                    error="缺少必需参数: column_name",
                    metadata={"tool_name": "generate_sql_time_condition"}
                )

            # 解析时间范围信息
            if isinstance(time_range, str):
                try:
                    time_range_info = json.loads(time_range)
                except json.JSONDecodeError:
                    return ToolResult(
                        success=False,
                        error="time_range 参数格式错误，应为有效的JSON字符串",
                        metadata={"tool_name": "generate_sql_time_condition"}
                    )
            else:
                time_range_info = time_range

            sql_condition = time_utils.generate_sql_time_range(time_range_info, column_name, date_format)

            return ToolResult(
                success=True,
                data={
                    "sql_condition": sql_condition,
                    "column_name": column_name,
                    "date_format": date_format,
                    "time_range_info": time_range_info
                },
                metadata={
                    "tool_name": "generate_sql_time_condition",
                    "column_name": column_name
                }
            )
        except Exception as e:
            self.logger.error(f"Generate SQL time condition failed: {e}")
            return ToolResult(success=False, error=str(e))

    # ========== ADB工具执行方法 ==========

    async def _execute_adb_login(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行ADB登录"""
        try:
            from core.tools.adb.llm_interface import adb_login_for_llm
            result = await adb_login_for_llm()

            return ToolResult(
                success=result.get("success", False),
                data=result,
                metadata={"tool_name": "adb_login"}
            )
        except Exception as e:
            self.logger.error(f"ADB login failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _execute_adb_logout(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行ADB登出"""
        try:
            from core.tools.adb.llm_interface import adb_logout_for_llm
            result = await adb_logout_for_llm()

            return ToolResult(
                success=result.get("success", False),
                data=result,
                metadata={"tool_name": "adb_logout"}
            )
        except Exception as e:
            self.logger.error(f"ADB logout failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _execute_adb_query_bill(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行ADB账单查询"""
        try:
            from core.tools.adb.llm_interface import adb_query_bill_for_llm
            result = await adb_query_bill_for_llm()

            return ToolResult(
                success=result.get("success", False),
                data=result,
                metadata={"tool_name": "adb_query_bill"}
            )
        except Exception as e:
            self.logger.error(f"ADB query bill failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _execute_adb_pay_bill(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行ADB缴费"""
        try:
            amount = parameters.get("amount", 10)

            # 验证参数
            if not isinstance(amount, (int, float)) or amount <= 0:
                return ToolResult(
                    success=False,
                    error=f"缴费金额无效: {amount}，金额必须是大于0的数字",
                    metadata={"tool_name": "adb_pay_bill"}
                )

            from core.tools.adb.llm_interface import adb_pay_bill_for_llm
            result = await adb_pay_bill_for_llm(amount)

            return ToolResult(
                success=result.get("success", False),
                data=result,
                metadata={"tool_name": "adb_pay_bill", "amount": amount}
            )
        except Exception as e:
            self.logger.error(f"ADB pay bill failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _get_adb_status(self, parameters: Dict[str, Any]) -> ToolResult:
        """获取ADB状态"""
        try:
            from core.tools.adb.llm_interface import get_adb_status_for_llm
            result = await get_adb_status_for_llm()

            return ToolResult(
                success=True,
                data=result,
                metadata={"tool_name": "get_adb_status"}
            )
        except Exception as e:
            self.logger.error(f"Get ADB status failed: {e}")
            return ToolResult(success=False, error=str(e))

# 全局工具管理器实例
_tool_manager_instance = None

def get_tool_manager() -> ToolManager:
    """获取工具管理器单例实例"""
    global _tool_manager_instance
    if _tool_manager_instance is None:
        _tool_manager_instance = ToolManager()
    return _tool_manager_instance
