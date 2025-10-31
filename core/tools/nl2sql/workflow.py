import logging
from typing import Dict, Any, List, Optional
from .table_info import get_table_manager, get_all_tables
from .sql_executor import get_sql_executor

logger = logging.getLogger(__name__)

class NL2SQLWorkflow:
    """NL2SQL工作流程管理器"""

    def __init__(self):
        self.table_manager = get_table_manager()
        self.sql_executor = get_sql_executor()

    async def process_sql_question(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        处理SQL相关问题的完整工作流程

        工作流程：
        1. 判断为SQL问题 → 进入NL2SQL流程
        2. 调用get_relevant_tables()获取初步表信息
        3. LLM分析问题并确定需要的表结构
        4. 调用get_table_schemas()获取详细表结构
        5. LLM基于表结构生成SQL语句
        6. 执行SQL查询
        7. LLM基于结果生成最终回答

        参数:
            question: 用户问题
            context: 对话上下文

        返回:
            包含处理结果或错误信息的字典
        """
        try:
            logger.info(f"Start processing SQL question: {question}")

            # 步骤1: 获取所有表的基本信息
            logger.info("Step 1: Get all tables' basic information")
            all_tables_result = await self._get_all_tables_async()

            if not all_tables_result['success']:
                return {
                    'success': False,
                    'error': f"获取表信息失败: {all_tables_result['error']}",
                    'step': 'get_tables'
                }

            all_tables = all_tables_result['data']['tables']

            # 步骤2: LLM分析问题并确定需要的表
            logger.info("Step 2: Analyze tables needed for the question")
            required_tables = await self._analyze_tables_needed(question, all_tables, context)

            if not required_tables:
                return {
                    'success': False,
                    'error': "LLM无法确定需要查询哪些表",
                    'step': 'analyze_tables'
                }

            # 步骤3: 获取详细表结构
            logger.info(f"Step 3: Get table schemas: {required_tables}")
            table_schemas_result = await self._get_table_schemas_async(required_tables)

            if not table_schemas_result['success']:
                return {
                    'success': False,
                    'error': f"获取表结构失败: {table_schemas_result['error']}",
                    'step': 'get_schemas'
                }

            # 步骤4: LLM生成SQL语句
            logger.info("Step 4: Generate SQL statement")
            sql_result = await self._generate_sql(question, table_schemas_result['formatted_output'], context)

            if not sql_result['success']:
                return {
                    'success': False,
                    'error': f"SQL生成失败: {sql_result['error']}",
                    'step': 'generate_sql'
                }

            # 步骤5: 执行SQL查询
            logger.info("Step 5: Execute SQL query")
            execution_result = await self._execute_sql_async(sql_result['generated_sql'])

            if not execution_result['success']:
                return {
                    'success': False,
                    'error': f"SQL执行失败: {execution_result['error']}",
                    'step': 'execute_sql',
                    'generated_sql': sql_result['generated_sql']
                }

            # 步骤6: LLM生成最终回答
            logger.info("Step 6: Generate final answer")
            final_answer = await self._generate_final_answer(
                question,
                sql_result['generated_sql'],
                execution_result['formatted_table'],
                context
            )

            return {
                'success': True,
                'question': question,
                'generated_sql': sql_result['generated_sql'],
                'query_result': execution_result['formatted_table'],
                'final_answer': final_answer,
                'row_count': execution_result['row_count'],
                'step': 'completed'
            }

        except Exception as e:
            logger.error(f"NL2SQL workflow processing failed: {e}")
            return {
                'success': False,
                'error': f"工作流程执行失败: {str(e)}",
                'step': 'workflow_error'
            }

    async def _get_all_tables_async(self) -> Dict[str, Any]:
        """异步获取所有表信息"""
        try:
            result = get_all_tables()
            return result
        except Exception as e:
            logger.error(f"Failed to get all tables' information: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _analyze_tables_needed(self, question: str, all_tables: List[Dict], context: str) -> Optional[List[str]]:
        """LLM分析问题并确定需要的表"""
        try:
            from core.chat.llm import get_llm_service

            llm_service = get_llm_service()
            if not llm_service:
                return None

            # 构建表信息摘要
            tables_summary = []
            for table in all_tables:
                tables_summary.append(
                    f"表名: {table['table_name']}, 注释: {table['comment']}"
                )

            tables_text = "\n".join(tables_summary)

            prompt = f"""请分析用户问题，确定需要查询哪些数据库表。

用户问题: {question}

可用表列表:
{tables_text}

对话上下文:
{context if context else '无'}

请根据用户问题，从上面的表列表中选择需要查询的表名。只返回表名列表，用逗号分隔。如果没有找到相关的表，请返回"无"。

回答示例格式:
orders,products
orders
无

请直接回答表名:"""

            # 调用LLM
            response = await llm_service.generate_response(prompt)
            response = response.strip()

            if response == "无" or not response:
                return None

            # 解析表名
            table_names = [name.strip() for name in response.split(',') if name.strip()]

            logger.info(f"LLM确定的表: {table_names}")
            return table_names

        except Exception as e:
            logger.error(f"Failed to analyze tables needed for the question: {e}")
            return None

    async def _get_table_schemas_async(self, table_names: List[str]) -> Dict[str, Any]:
        """异步获取表结构信息"""
        try:
            schemas_result = self.table_manager.get_multiple_table_schemas(table_names)

            if not schemas_result['success']:
                return {
                    'success': False,
                    'error': "; ".join(schemas_result['errors'])
                }

            # 格式化表结构信息
            formatted_schemas = []
            for table_name, schema in schemas_result['schemas'].items():
                schema_info = f"表名: {table_name}\n"
                schema_info += f"表注释: {schema['table_comment']}\n"
                schema_info += "字段:\n"

                for col in schema['columns']:
                    col_info = f"  {col['name']} ({col['type']}"
                    if not col['nullable']:
                        col_info += " NOT NULL"
                    if col['key']:
                        col_info += f" {col['key']}"
                    if col['comment']:
                        col_info += f" -- {col['comment']}"
                    schema_info += col_info + "\n"

                formatted_schemas.append(schema_info)

            return {
                'success': True,
                'formatted_output': "\n\n".join(formatted_schemas),
                'schemas': schemas_result['schemas']
            }

        except Exception as e:
            logger.error(f"Failed to get table schemas: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _generate_sql(self, question: str, table_schemas: str, context: str) -> Dict[str, Any]:
        """LLM生成SQL语句"""
        try:
            from core.chat.llm import get_llm_service

            llm_service = get_llm_service()
            if not llm_service:
                return {
                    'success': False,
                    'error': 'LLM服务不可用'
                }

            prompt = f"""你是一个专业的SQL查询生成器。请根据用户问题和表结构信息，生成准确的SQL查询语句。

用户问题: {question}

表结构信息:
{table_schemas}

对话上下文:
{context if context else '无'}

请遵循以下规则:
1. 只生成SELECT查询语句
2. 确保SQL语法正确，符合MySQL规范
3. 使用适当的WHERE条件
4. 可以使用聚合函数如COUNT、SUM、AVG、MAX、MIN
5. 确保表名和字段名与提供的信息完全匹配
6. 只返回SQL语句，不要包含其他解释文字

SQL语句:"""

            # 调用LLM生成SQL
            response = await llm_service.generate_response(prompt)
            sql_query = response.strip()

            # 清理SQL语句
            import re
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

            sql_query = re.sub(r'^.*?(SELECT\b)', r'\1', sql_query, flags=re.IGNORECASE | re.DOTALL)
            sql_query = sql_query.rstrip(';').strip()

            # 转义包含特殊字符的表名和列名
            def quote_identifiers(text):
                # 匹配FROM, JOIN, INTO等子句后的表名
                def quote_table_name(match):
                    prefix = match.group(1)
                    table_name = match.group(2)
                    # 如果已经包含反引号，跳过
                    if table_name.startswith('`') and table_name.endswith('`'):
                        return match.group(0)
                    # 如果包含特殊字符，添加反引号
                    if '-' in table_name or ' ' in table_name:
                        return f"{prefix}`{table_name}`"
                    return match.group(0)

                pattern = r'(\b(?:FROM|JOIN|INTO|UPDATE)\s+)([a-zA-Z_][a-zA-Z0-9_-]*)'
                return re.sub(pattern, quote_table_name, text, flags=re.IGNORECASE)

            sql_query = quote_identifiers(sql_query)

            if not sql_query.upper().startswith('SELECT'):
                return {
                    'success': False,
                    'error': f"生成的SQL不是有效的SELECT查询: {sql_query}"
                }

            return {
                'success': True,
                'generated_sql': sql_query
            }

        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _execute_sql_async(self, sql_query: str) -> Dict[str, Any]:
        """异步执行SQL查询"""
        try:
            logger.info(f"Executing SQL query: {sql_query}")
            result = self.sql_executor.execute_sql_query(sql_query)
            return result
        except Exception as e:
            logger.error(f"Failed to execute SQL query: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _generate_final_answer(self, question: str, sql_query: str, query_result: str, context: str) -> str:
        """LLM生成最终回答"""
        try:
            from core.chat.llm import get_llm_service

            llm_service = get_llm_service()
            if not llm_service:
                return "抱歉，无法生成回答。"

            prompt = f"""请基于以下信息回答用户的问题。

用户问题: {question}

执行的SQL查询:
```sql
{sql_query}
```

查询结果:
```
{query_result}
```

对话上下文:
{context if context else '无'}

请基于查询结果，用自然语言直接回答用户的问题。要求：
1. 回答要简洁明了
2. 基于实际查询结果回答
3. 如果查询无结果，说明原因
4. 不要重复技术细节

回答:"""

            # 调用LLM生成回答
            response = await llm_service.generate_response(prompt)
            return response.strip()

        except Exception as e:
            logger.error(f"Failed to generate final answer: {e}")
            return f"根据查询结果回答您的问题，但处理时出现错误: {str(e)}"

# 全局实例
_workflow = None

def get_nl2sql_workflow() -> NL2SQLWorkflow:
    """获取NL2SQL工作流程实例"""
    global _workflow
    if _workflow is None:
        _workflow = NL2SQLWorkflow()
    return _workflow