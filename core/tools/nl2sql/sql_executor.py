import logging
import re
from typing import Dict, Any, List, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from config import Config

logger = logging.getLogger(__name__)

class SQLExecutor:
    """SQL查询生成器和执行器"""

    def __init__(self):
        self.engine = None
        self.connection_pool = None
        self.db_type = getattr(Config, 'SQL_DB_TYPE', 'mysql').lower()
        self._initialize_connection()

    def _initialize_connection(self):
        """初始化数据库连接池"""
        try:
            # 优先使用统一连接池
            if Config.DB_POOL_ENABLED:
                try:
                    from core.database.connection_pool import get_connection_pool
                    self.connection_pool = get_connection_pool()
                    return
                except ImportError:
                    logger.warning("Unified connection pool not available, falling back to SQLAlchemy pool")

            # 回退到SQLAlchemy连接池
            if self.db_type == 'mysql':
                connection_string = (
                    f"mysql+mysqlconnector://"
                    f"{getattr(Config, 'SQL_DB_USERNAME', 'root')}:"
                    f"{getattr(Config, 'SQL_DB_PASSWORD', 'root')}@"
                    f"{getattr(Config, 'SQL_DB_HOST', 'localhost')}:"
                    f"{getattr(Config, 'SQL_DB_PORT', '3306')}/"
                    f"{getattr(Config, 'SQL_DB_DATABASE', 'any4any')}"
                )
            else:
                raise ValueError(f"不支持的数据库类型: {self.db_type}")

            # 使用配置的连接池参数
            self.engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=Config.DB_POOL_SIZE,
                pool_pre_ping=Config.DB_POOL_PRE_PING,
                pool_recycle=Config.DB_POOL_RECYCLE,
                echo=False
            )
            logger.info("SQL Executor initialized successfully with SQLAlchemy connection pool.")

        except Exception as e:
            logger.error(f"SQL Executor database connection initialization failed: {e}")
            self.engine = None

    def _ensure_connection(self):
        """确保数据库连接可用"""
        try:
            if self.engine is None:
                logger.warning("Database engine is None, reinitializing...")
                self._initialize_connection()

            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        except Exception as e:
            logger.error(f"Database connection test failed, reinitializing: {e}")
            self._initialize_connection()
            if self.engine:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

    def _validate_sql_safety(self, sql_query: str) -> Tuple[bool, str]:
        """
        验证SQL查询的安全性

        参数:
            sql_query: 要验证的SQL查询

        返回:
            (是否安全, 错误信息) 元组
        """
        try:
            # 转换为大写进行检查
            sql_upper = sql_query.strip().upper()

            # 只允许SELECT语句
            if not sql_upper.startswith('SELECT'):
                return False, "出于安全考虑，仅允许SELECT查询"

            # 检查危险关键词
            dangerous_keywords = [
                'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
                'TRUNCATE', 'EXEC', 'EXECUTE', 'UNION', 'MERGE', 'GRANT',
                'REVOKE', 'COMMIT', 'ROLLBACK', 'SAVEPOINT'
            ]

            for keyword in dangerous_keywords:
                if re.search(r'\b' + keyword + r'\b', sql_upper):
                    return False, f"发现危险关键词 '{keyword}'"

            # 检查注释技巧
            if '--' in sql_query or '/*' in sql_query or '*/' in sql_query:
                return False, "不允许在SQL查询中使用注释"

            # 检查多语句
            if ';' in sql_query.rstrip():
                return False, "不允许执行多个SQL语句"

            return True, ""

        except Exception as e:
            return False, f"SQL验证错误: {str(e)}"

    def _format_query_results(self, results, columns: List[str]) -> Dict[str, Any]:
        """
        格式化查询结果以便更好地展示

        参数:
            results: 原始查询结果
            columns: 列名

        返回:
            格式化的结果字典
        """
        if not results:
            return {
                'success': True,
                'data': [],
                'columns': columns,
                'row_count': 0,
                'formatted_table': '查询执行成功，但没有返回数据。'
            }

        # 处理不同格式的结果
        data = []
        if results and isinstance(results[0], dict):
            data = results
            if not columns:
                columns = list(results[0].keys())
        else:
            for row in results:
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        row_dict[columns[i]] = value
                data.append(row_dict)

        # 创建格式化表格
        if columns and data:
            col_widths = {}
            for col in columns:
                if data:
                    max_data_length = max(len(str(row.get(col, ''))) for row in data)
                    col_widths[col] = max(len(str(col)), max_data_length)
                else:
                    col_widths[col] = len(str(col))

            # 构建表格字符串
            table_lines = []

            # 表头
            header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
            table_lines.append(header)
            table_lines.append("-" * len(header))

            # 数据行
            for row in data:
                row_line = " | ".join(str(row.get(col, '')).ljust(col_widths[col]) for col in columns)
                table_lines.append(row_line)

            formatted_table = "\n".join(table_lines)
            logger.debug(f"Formatted table: {formatted_table}")
        else:
            formatted_table = "查询执行成功，但没有返回数据。"
            logger.debug("No data to format in table")

        return {
            'success': True,
            'data': data,
            'columns': columns,
            'row_count': len(data),
            'formatted_table': formatted_table
        }

    def execute_sql_query(self, sql_query: str) -> Dict[str, Any]:
        """
        执行已验证的SQL查询

        参数:
            sql_query: 要执行的SQL查询

        返回:
            查询执行结果
        """
        try:
            # 验证SQL安全性
            is_safe, error_msg = self._validate_sql_safety(sql_query)
            if not is_safe:
                return {
                    'success': False,
                    'error': error_msg,
                    'formatted_output': f'SQL安全验证失败: {error_msg}'
                }

            # 优先使用统一连接池
            if self.connection_pool:
                return self._execute_with_unified_pool(sql_query)

            # 回退到SQLAlchemy连接池
            if not self.engine:
                return {
                    'success': False,
                    'error': '数据库连接不可用',
                    'formatted_output': '数据库连接不可用'
                }

            # 执行查询
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_query))

                if result.returns_rows:
                    rows = result.fetchall()
                    columns = list(result.keys())
                    formatted_results = self._format_query_results(rows, columns)

                    return {
                        'success': True,
                        'sql_query': sql_query,
                        'execution_time': '暂无',  # 如需要可以添加计时
                        **formatted_results
                    }
                else:
                    return {
                        'success': True,
                        'sql_query': sql_query,
                        'execution_time': '暂无',
                        'data': [],
                        'columns': [],
                        'row_count': result.rowcount if hasattr(result, 'rowcount') else 0,
                        'formatted_table': f'查询执行成功。{result.rowcount} 行受影响。' if hasattr(result, 'rowcount') else '查询执行成功。'
                    }

        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'sql_query': sql_query,
                'formatted_output': f'SQL执行失败: {str(e)}'
            }

    def _execute_with_unified_pool(self, sql_query: str) -> Dict[str, Any]:
        """使用统一连接池执行SQL查询"""
        def _execute():
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(sql_query)
                result = cursor.fetchall()
                # 获取列信息用于后续处理
                columns = [desc[0] for desc in cursor.description] if hasattr(cursor, 'description') else []
                return result, columns
            finally:
                cursor.close()
                self.connection_pool.return_connection(connection)

        try:
            # 使用熔断器和重试机制
            circuit_breaker = self.connection_pool.get_circuit_breaker()
            retry_manager = self.connection_pool.get_retry_manager()

            if Config.DB_RETRY_ENABLED:
                rows, columns = retry_manager.retry_with_backoff(_execute)
            else:
                rows, columns = circuit_breaker.call(_execute)

            # 格式化结果
            if rows:
                logger.debug(f"Query result type: {type(rows)}")
                logger.debug(f"First row type: {type(rows[0])}")
                logger.debug(f"First row content: {rows[0]}")
                logger.debug(f"Columns: {columns}")

                # 确保rows是字典列表格式
                if rows and isinstance(rows[0], tuple):
                    rows = [{columns[i] if i < len(columns) else f'col_{i}': row[i] for i in range(len(row))} for row in rows]
                elif rows and not isinstance(rows[0], dict):
                    logger.warning(f"Unexpected result type: {type(rows[0])}")
                    columns = []
            else:
                logger.debug("No rows returned from query")
                columns = columns or []  # 确保columns不为None

            formatted_results = self._format_query_results(rows, columns)

            self.connection_pool.record_operation_success('sql_query', 0)

            return {
                'success': True,
                'sql_query': sql_query,
                'execution_time': 'N/A',
                **formatted_results
            }

        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            self.connection_pool.record_operation_error('sql_query', str(e))
            return {
                'success': False,
                'error': str(e),
                'sql_query': sql_query,
                'formatted_output': f'SQL执行失败: {str(e)}'
            }

# 全局单例实例
_sql_executor_instance = None

def get_sql_executor() -> SQLExecutor:
    """获取SQL执行器单例实例"""
    global _sql_executor_instance
    if _sql_executor_instance is None:
        _sql_executor_instance = SQLExecutor()
    return _sql_executor_instance

async def generate_and_execute_sql(question: str, table_schemas: str, context: str = "") -> Dict[str, Any]:
    """
    工具函数：从自然语言生成SQL并执行

    参数:
        question: 用户的自然语言问题
        table_schemas: 数据库表结构信息
        context: 额外的对话上下文

    返回:
        包含查询结果或错误详情的字典
    """
    try:
        from core.chat.llm import get_llm_service

        # 获取用于SQL生成的LLM服务
        llm_service = get_llm_service()
        if not llm_service:
            return {
                'success': False,
                'error': 'LLM服务不可用',
                'formatted_output': 'LLM服务不可用，无法生成SQL'
            }

        # 构建SQL生成提示词
        sql_generation_prompt = f"""你是一个专业的SQL查询生成器。请根据用户的问题和数据库表结构，生成准确的SQL查询语句。

用户问题: {question}

数据库表结构信息:
{table_schemas}

对话上下文:
{context if context else '无'}

请遵循以下规则:
1. 只生成SELECT查询语句，不要生成修改数据的语句
2. 确保SQL语法正确，符合MySQL语法规范
3. 使用适当的WHERE条件来过滤数据
4. 如果需要聚合，使用合适的聚合函数(COUNT, SUM, AVG, MAX, MIN等)
5. 只返回SQL语句，不要包含任何解释文字
6. 确保表名和字段名与提供的信息完全匹配

SQL查询语句:"""

        # 使用LLM生成SQL
        sql_response = await llm_service.generate_response(sql_generation_prompt)

        # 从响应中提取SQL（移除任何额外文本）
        sql_query = sql_response.strip()

        # 移除LLM可能添加的常见前缀/后缀
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'SQL查询语句:\s*(.*?)\s*$',
            r'SQL:\s*(.*?)\s*$'
        ]

        for pattern in sql_patterns:
            match = re.search(pattern, sql_query, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query = match.group(1).strip()
                break

        # 清理SQL
        sql_query = re.sub(r'^.*?(SELECT\b)', r'\1', sql_query, flags=re.IGNORECASE | re.DOTALL)
        sql_query = sql_query.rstrip(';').strip()

        if not sql_query.upper().startswith('SELECT'):
            return {
                'success': False,
                'error': '生成的SQL看起来不是SELECT查询',
                'formatted_output': f'生成的SQL不是有效的SELECT查询: {sql_query}',
                'generated_sql': sql_query
            }

        # 执行生成的SQL
        executor = get_sql_executor()
        result = executor.execute_sql_query(sql_query)

        # 格式化输出
        if result['success']:
            formatted_output = f"""根据问题"{question}"生成的SQL查询已成功执行。

生成的SQL语句:
```sql
{sql_query}
```

查询结果:
```
{result['formatted_table']}
```

返回行数: {result['row_count']}

请基于以上查询结果回答用户的原始问题。"""

            return {
                'success': True,
                'question': question,
                'generated_sql': sql_query,
                'execution_result': result,
                'formatted_output': formatted_output
            }
        else:
            formatted_output = f"""根据问题"{question}"生成了SQL查询，但执行时出现错误。

生成的SQL语句:
```sql
{sql_query}
```

执行错误: {result['error']}

请检查SQL语法或数据库结构，然后重新生成查询。"""

            return {
                'success': False,
                'question': question,
                'generated_sql': sql_query,
                'error': result['error'],
                'formatted_output': formatted_output
            }

    except Exception as e:
        logger.error(f"生成和执行SQL工具错误: {e}")
        return {
            'success': False,
            'error': str(e),
            'formatted_output': f'生成和执行SQL时发生错误: {str(e)}'
        }