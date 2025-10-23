import os
import logging
import re
from typing import Optional, Dict, Any, Tuple
from core.chat.sql_agent.sql_agent import SQLAgent  # 修正导入路径
from core.database.sql_manager import sql_db_manager
from core.chat.llm import get_llm_service
from config import Config

logger = logging.getLogger(__name__)

class SQLIntegrator:
    """SQL查询集成器"""

    def __init__(self):
        self.enabled = Config.SQL_AGENT_ENABLED
        self.agent_cache = {}
        self.llm_service = get_llm_service()  # 使用项目的LLM服务
        self._initialize_sample_db()

    def _initialize_sample_db(self):
        """初始化MySQL示例数据"""
        try:
            sql_db_manager.create_sample_tables()
        except Exception as e:
            logger.warning(f"Failed to initialize sample MySQL tables: {e}")

    def _get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置 - 直接使用现有LLM实例"""
        return {
            "llm_service": self.llm_service,  # 直接使用项目的LLM服务
            "temperature": Config.SQL_AGENT_TEMPERATURE,
            "max_tokens": Config.SQL_AGENT_MAX_TOKENS
        }

    def _get_sql_agent(self, db_name: str = None) -> Optional[SQLAgent]:
        """获取SQL Agent实例"""
        if not self.enabled:
            return None

        if db_name is None:
            db_name = Config.SQL_DB_DATABASE

        cache_key = f"{db_name}_{Config.SQL_AGENT_TEMPERATURE}"

        if cache_key not in self.agent_cache:
            try:
                connection_string = sql_db_manager.get_database_connection(db_name)
                db_schema = sql_db_manager.get_database_schema(db_name)

                agent = SQLAgent(
                    db=connection_string,
                    max_turns=Config.SQL_AGENT_MAX_TURNS,
                    debug=Config.SQL_AGENT_DEBUG,
                    db_schema=db_schema,
                    llm_service=self.llm_service,  # 直接传入项目的LLM服务
                    table_info_truncate=Config.SQL_AGENT_TABLE_INFO_TRUNCATE,
                    execution_truncate=Config.SQL_AGENT_EXECUTION_TRUNCATE
                )

                self.agent_cache[cache_key] = agent
                logger.info(f"Created SQL Agent for database: {db_name}")

            except Exception as e:
                logger.error(f"Failed to create SQL Agent: {e}")
                return None

        return self.agent_cache.get(cache_key)

    def is_sql_query_needed(self, user_message: str) -> Tuple[bool, str]:
        """判断用户消息是否需要SQL查询"""
        sql_keywords = [
            '查询', '统计', '计算', '显示', '列出', '多少', '几个', '总数', '平均',
            '最高', '最低', '最大', '最小', '排序', '分组', '汇总', '数据', '记录',
            '表', '字段', '数据库', 'SELECT', 'FROM', 'WHERE', 'COUNT', 'SUM', 'AVG',
            'MAX', 'MIN', 'ORDER BY', 'GROUP BY'
        ]

        # 检查是否包含SQL相关关键词
        has_sql_keywords = any(keyword.lower() in user_message.lower() for keyword in sql_keywords)

        # 检查是否是数据相关问题
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

        has_data_question = any(re.search(pattern, user_message, re.IGNORECASE)
                              for pattern in data_question_patterns)

        needs_sql = has_sql_keywords or has_data_question

        if needs_sql:
            confidence = "high" if (has_sql_keywords and has_data_question) else "medium"
            return True, confidence
        else:
            return False, "low"

    def execute_sql_query(self, question: str, db_name: str = None) -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            if db_name is None:
                db_name = Config.SQL_DB_DATABASE

            agent = self._get_sql_agent(db_name)
            if not agent:
                return {
                    "success": False,
                    "error": "SQL Agent not available",
                    "query": None,
                    "result": None
                }

            # 执行查询
            graph = agent.graph()
            result = graph.invoke({"question": question})

            return {
                "success": True,
                "query": result.get("query", ""),
                "result": result.get("execution", ""),
                "num_turns": result.get("num_turns", 0),
                "messages": result.get("messages", [])
            }

        except Exception as e:
            logger.error(f"SQL query execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": None,
                "result": None
            }

    def format_sql_result(self, sql_result: Dict[str, Any]) -> str:
        """格式化SQL查询结果"""
        if not sql_result["success"]:
            return f"查询失败: {sql_result['error']}"

        query = sql_result["query"]
        result = sql_result["result"]
        turns = sql_result["num_turns"]

        formatted_result = f"数据查询结果:\n\n"
        formatted_result += f"执行的查询:\n```sql\n{query}\n```\n\n"

        if result:
            formatted_result += f"查询结果:\n```\n{result}\n```\n\n"
        else:
            formatted_result += f"查询结果: 无数据返回\n\n"

        formatted_result += f"查询优化次数: {turns}"

        return formatted_result

# 全局实例
sql_integrator = SQLIntegrator()