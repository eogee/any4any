import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import create_engine, text
from config import Config

logger = logging.getLogger(__name__)

class DatabaseTableManager:
    """数据库表信息管理器"""

    def __init__(self):
        self.engine = None
        self.connection_pool = None
        self.db_type = getattr(Config, 'SQL_DB_TYPE', 'mysql').lower()
        self._initialize_connection()

    def _initialize_connection(self):
        """初始化数据库连接"""
        try:
            # 优先使用统一连接池
            if Config.DB_POOL_ENABLED:
                try:
                    from core.database.connection_pool import get_connection_pool
                    self.connection_pool = get_connection_pool()
                    return
                except ImportError:
                    logger.warning("Unified connection pool not available for TableInfo, falling back to SQLAlchemy")

            # 回退到SQLAlchemy连接
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

            self.engine = create_engine(connection_string)
            logger.info("TableInfo manager using SQLAlchemy connection.")

        except Exception as e:
            logger.error(f"TableInfo database connection initialization failed: {e}")
            self.engine = None

    def _execute_query(self, query: str, params: Optional[List] = None) -> List[Tuple]:
        """执行数据库查询并返回结果"""
        def _execute_with_pool():
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor()

            try:
                # 连接池模式：直接使用位置参数
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                rows = cursor.fetchall()
                return [tuple(row) for row in rows]

            finally:
                cursor.close()
                self.connection_pool.return_connection(connection)

        # 优先使用统一连接池
        if self.connection_pool:
            try:
                # 使用熔断器和重试机制
                circuit_breaker = self.connection_pool.get_circuit_breaker()
                retry_manager = self.connection_pool.get_retry_manager()

                if Config.DB_RETRY_ENABLED:
                    return retry_manager.retry_with_backoff(_execute_with_pool)
                else:
                    return circuit_breaker.call(_execute_with_pool)

            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise

        # 回退到SQLAlchemy连接
        if not self.engine:
            raise Exception("数据库连接未初始化")

        try:
            with self.engine.connect() as conn:
                # SQLAlchemy支持位置参数
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))

                # 确保返回的是元组列表
                rows = result.fetchall()
                return [tuple(row) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def get_all_tables_with_comments(self) -> Dict[str, Any]:
        """获取所有表及其注释"""
        try:
            if self.db_type == 'mysql':
                query = """
                SELECT
                    TABLE_NAME,
                    TABLE_COMMENT,
                    TABLE_ROWS
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
                """
                params = [getattr(Config, 'SQL_DB_DATABASE', 'any4any')]

                results = self._execute_query(query, params)

                tables = []
                for row in results:
                    table_name, comment, row_count = row
                    tables.append({
                        'table_name': table_name,
                        'comment': comment or '无注释',
                        'estimated_rows': row_count or 0
                    })

                return {
                    'success': True,
                    'tables': tables,
                    'total_count': len(tables)
                }

        except Exception as e:
            logger.error(f"Failed to get table comments: {e}")
            return {
                'success': False,
                'error': str(e),
                'tables': []
            }

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """获取指定表的详细结构"""
        try:
            if self.db_type == 'mysql':
                # 获取列信息
                column_query = """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_DEFAULT,
                    COLUMN_KEY,
                    EXTRA,
                    COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """
                params = [
                    getattr(Config, 'SQL_DB_DATABASE', 'any4any'),
                    table_name
                ]

                columns = self._execute_query(column_query, params)

                # 获取表注释
                table_comment_query = """
                SELECT TABLE_COMMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
                """
                table_comment_result = self._execute_query(table_comment_query, params)
                table_comment = table_comment_result[0][0] if table_comment_result else ''

                # 格式化列信息
                column_info = []
                for col in columns:
                    column_name, data_type, is_nullable, default_val, key, extra, comment = col
                    column_info.append({
                        'name': column_name,
                        'type': data_type,
                        'nullable': is_nullable == 'YES',
                        'default': default_val,
                        'key': key,
                        'extra': extra,
                        'comment': comment or ''
                    })

                return {
                    'success': True,
                    'table_name': table_name,
                    'table_comment': table_comment or '',
                    'columns': column_info,
                    'column_count': len(column_info)
                }

        except Exception as e:
            logger.error(f"Failed to get table structure {table_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'table_name': table_name,
                'columns': []
            }

    def get_multiple_table_schemas(self, table_names: List[str]) -> Dict[str, Any]:
        """批量获取表结构"""
        schemas = {}
        errors = []

        for table_name in table_names:
            schema = self.get_table_schema(table_name)
            if schema['success']:
                schemas[table_name] = schema
            else:
                errors.append(f"Failed to get {table_name} structure: {schema['error']}")

        return {
            'success': len(schemas) > 0,
            'schemas': schemas,
            'errors': errors,
            'requested_count': len(table_names),
            'successful_count': len(schemas)
        }

def get_table_manager() -> DatabaseTableManager:
    """获取表管理器实例"""
    return DatabaseTableManager()

def get_all_tables() -> Dict[str, Any]:
    """
    工具函数：获取数据库中所有表的信息，包括表名、注释和基本信息

    返回:
        包含表信息的字典或错误详情
    """
    try:
        manager = get_table_manager()
        result = manager.get_all_tables_with_comments()

        if result['success']:
            # 格式化输出以提高可读性
            tables_info = []
            for table in result['tables']:
                tables_info.append(
                    f"表名: {table['table_name']}\n"
                    f"注释: {table['comment']}\n"
                    f"预估行数: {table['estimated_rows']}"
                )

            formatted_output = "数据库中的所有表:\n\n" + "\n\n".join(tables_info)

            return {
                'success': True,
                'data': result,
                'formatted_output': formatted_output
            }
        else:
            return {
                'success': False,
                'error': result['error'],
                'formatted_output': f"获取表信息失败: {result['error']}"
            }

    except Exception as e:
        logger.error(f"Error in get all tables tool: {e}")
        return {
            'success': False,
            'error': str(e),
            'formatted_output': f"Error occurred while getting table information: {str(e)}"
        }

def get_relevant_tables(question: str) -> Dict[str, Any]:
    """
    工具函数：根据用户问题获取相关的数据库表结构信息

    参数:
        question: 用户的自然语言问题

    返回:
        包含相关表结构的字典或错误详情
    """
    try:
        manager = get_table_manager()

        # 首先获取所有表
        all_tables_result = manager.get_all_tables_with_comments()
        if not all_tables_result['success']:
            return {
                'success': False,
                'error': all_tables_result['error'],
                'formatted_output': f"Unable to get table list: {all_tables_result['error']}"
            }

        all_tables = all_tables_result['tables']

        # 简单的关键词匹配来查找相关表
        # 这是一个基本方法 - 可以用NLP来增强
        question_lower = question.lower()

        # 常见关键词及其可能的表关联
        keyword_table_mapping = {
            '订单': ['orders', 'order'],
            '产品': ['products', 'product'],
            '商品': ['products', 'product', 'goods'],
            '客户': ['customers', 'customer', 'users'],
            '用户': ['users', 'user', 'customers'],
            '库存': ['inventory', 'stock', 'products'],
            '分类': ['categories', 'category'],
            '员工': ['employees', 'employee', 'staff'],
            '部门': ['departments', 'department'],
            '销售': ['sales', 'orders'],
            '购买': ['orders', 'purchases'],
            '支付': ['payments', 'orders'],
            '地址': ['addresses', 'address'],
            '联系': ['contacts', 'contact']
        }

        # 基于关键词查找相关表
        relevant_table_names = set()

        # 检查表名和注释的匹配
        for table in all_tables:
            table_name = table['table_name'].lower()
            table_comment = table['comment'].lower()

            # 直接名称匹配
            if any(keyword in table_name for keyword in keyword_table_mapping.keys()):
                relevant_table_names.add(table['table_name'])
                continue

            # 注释匹配
            if any(keyword in table_comment for keyword in keyword_table_mapping.keys()):
                relevant_table_names.add(table['table_name'])
                continue

        # 如果没有找到特定表，包含所有表进行综合搜索
        if not relevant_table_names:
            relevant_table_names = {table['table_name'] for table in all_tables[:5]}  # 限制为前5个表

        # 获取相关表的结构
        schemas_result = manager.get_multiple_table_schemas(list(relevant_table_names))

        if schemas_result['success']:
            # 格式化输出
            formatted_schemas = []
            for table_name, schema in schemas_result['schemas'].items():
                schema_info = f"表名: {table_name}\n"
                schema_info += f"表注释: {schema['table_comment']}\n"
                schema_info += "字段信息:\n"

                for col in schema['columns']:
                    col_info = f"  - {col['name']} ({col['type']}"
                    if not col['nullable']:
                        col_info += ", NOT NULL"
                    if col['key']:
                        col_info += f", {col['key']}"
                    if col['comment']:
                        col_info += f", {col['comment']}"
                    col_info += ")"
                    schema_info += col_info + "\n"

                formatted_schemas.append(schema_info)

            formatted_output = f"根据问题'{question}'找到的相关表结构:\n\n"
            formatted_output += "\n\n".join(formatted_schemas)

            return {
                'success': True,
                'data': schemas_result,
                'question': question,
                'relevant_tables': list(relevant_table_names),
                'formatted_output': formatted_output
            }
        else:
            return {
                'success': False,
                'error': schemas_result['errors'][0] if schemas_result['errors'] else '未知错误',
                'formatted_output': f"Failed to get relevant table structures: {schemas_result['errors'][0] if schemas_result['errors'] else 'Unknown error'}"
            }

    except Exception as e:
        logger.error(f"Error in get relevant tables tool: {e}")
        return {
            'success': False,
            'error': str(e),
            'formatted_output': f"Error occurred while getting relevant table structures: {str(e)}"
        }