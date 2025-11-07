"""
NL2SQL工具 - 整合检测、处理和执行逻辑
"""
import logging
import re
from typing import Dict, Any, Optional, Callable, List

from ..base_tool import BaseTool
from ..result import ToolResult
from .table_info import get_table_manager, get_all_tables
from .sql_executor import get_sql_executor
from .context_manager import SQLContextManager
from .user_context_enhancer import get_user_context_enhancer

logger = logging.getLogger(__name__)

class NL2SQLTool(BaseTool):
    """NL2SQL工具 - 完整的SQL问题检测、处理和执行"""

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self.table_manager = get_table_manager()
        self.sql_executor = get_sql_executor()
        self.context_manager = SQLContextManager()
        self.user_context_enhancer = get_user_context_enhancer()

    @property
    def priority(self) -> int:
        return 1  # 高优先级

    @property
    def name(self) -> str:
        return "nl2sql"

    @property
    def description(self) -> str:
        return "自然语言转SQL查询工具，支持智能表选择和SQL生成"

    async def can_handle(self, user_message: str) -> bool:
        """检测是否为SQL相关问题 - 整合原tool_manager.is_sql_question逻辑"""
        if not user_message or not user_message.strip() or not self.enabled:
            return False

        # 检查配置
        try:
            from config import Config
            if not getattr(Config, 'NL2SQL_ENABLED', True):
                return False
        except Exception as e:
            self.logger.warning(f"Failed to check NL2SQL_ENABLED: {e}")
            return False

        # 现在由LLM进行功能识别，工具本身不做关键词检测
        # 只检查是否启用和基本配置
        return True

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        """处理SQL问题"""
        try:
            workflow_result = await self.process_sql_question(
                question=user_message,
                context="",
                conversation_manager=conversation_manager,
                user_id=user_id,
                platform=platform
            )

            if workflow_result['success']:
                return workflow_result['final_answer']
            else:
                error_msg = workflow_result.get('error', '')
                if any(phrase in error_msg for phrase in ['无法确定需要查询哪些表', '找不到相关表']):
                    self.logger.info(f"NL2SQL: {error_msg}, not suitable for SQL processing")
                else:
                    self.logger.warning(f"NL2SQL workflow failed: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"NL2SQL processing failed: {e}")
            return None

    # 保持原有的工作流程方法
    async def process_sql_question(self, question: str, context: str = "",
                                 conversation_manager=None, user_id: str = None,
                                 platform: str = None) -> Dict[str, Any]:
        """原有的NL2SQL工作流程 - 保持不变"""
        try:
            # 步骤0: 获取用户上下文
            user_context = ""
            if user_id:
                try:
                    user_context = await self.user_context_enhancer.get_user_context(user_id, question)
                except Exception as e:
                    logger.error(f"Failed to generate user context: {e}")
                    user_context = ""

            # 步骤0.5: 自动获取增强上下文（对话历史）
            history_context = ""
            if conversation_manager and user_id:
                try:
                    history_context = await self.context_manager.get_enhanced_context(
                        current_question=question,
                        conversation_manager=conversation_manager,
                        user_id=user_id,
                        platform=platform,
                        manual_context=context,
                        max_history=self.context_manager.max_history_items
                    )
                except Exception as e:
                    logger.error(f"Failed to generate history context: {e}")
                    history_context = context or ""
            else:
                history_context = context or ""

            # 合并所有上下文：用户上下文 + 历史上下文 + 手动上下文
            enhanced_context = "\n\n".join(filter(None, [
                user_context,     # 用户元数据上下文
                history_context,  # 对话历史上下文
                context           # 手动提供的上下文
            ]))

            # 步骤1: 获取所有表的基本信息
            all_tables_result = await self._get_all_tables_async()

            if not all_tables_result['success']:
                return {
                    'success': False,
                    'error': f"获取表信息失败: {all_tables_result['error']}",
                    'step': 'get_tables'
                }

            all_tables = all_tables_result['data']['tables']

            # 步骤2: LLM分析问题并确定需要的表（基于用户上下文+历史上下文）
            required_tables = await self._analyze_tables_needed(question, all_tables, enhanced_context)

            if not required_tables:
                return {
                    'success': False,
                    'error': "LLM无法确定需要查询哪些表",
                    'step': 'analyze_tables'
                }

            # 步骤3: 获取详细表结构
            table_schemas_result = await self._get_table_schemas_async(required_tables)

            if not table_schemas_result['success']:
                return {
                    'success': False,
                    'error': f"获取表结构失败: {table_schemas_result['error']}",
                    'step': 'get_schemas'
                }

            # 步骤4: LLM生成SQL语句（基于用户上下文+历史上下文）
            sql_result = await self._generate_sql(question, table_schemas_result['formatted_output'], enhanced_context)

            if not sql_result['success']:
                return {
                    'success': False,
                    'error': f"SQL生成失败: {sql_result['error']}",
                    'step': 'generate_sql'
                }

            # 记录生成的SQL语句
            logger.info(f"NL2SQL Question: {question} | Generated SQL: {sql_result['generated_sql']}")

            # 步骤5: 执行SQL查询
            execution_result = await self._execute_sql_async(sql_result['generated_sql'])

            if not execution_result['success']:
                return {
                    'success': False,
                    'error': f"SQL执行失败: {execution_result['error']}",
                    'step': 'execute_sql',
                    'generated_sql': sql_result['generated_sql']
                }

            # 步骤6: LLM生成最终回答（基于完整上下文）
            final_answer = await self._generate_final_answer(
                question,
                sql_result['generated_sql'],
                execution_result['formatted_table'],
                enhanced_context
            )

            # 分析上下文来源
            context_sources = []
            if user_context:
                context_sources.append('user_metadata')
            if history_context:
                context_sources.append('conversation_history')
            if context:
                context_sources.append('manual')

            return {
                'success': True,
                'question': question,
                'generated_sql': sql_result['generated_sql'],
                'query_result': execution_result['formatted_table'],
                'final_answer': final_answer,
                'row_count': execution_result['row_count'],
                'step': 'completed',
                'context_used': bool(enhanced_context),
                'context_sources': context_sources,
                'user_context_used': bool(user_context),
                'history_context_used': bool(history_context),
                'manual_context_used': bool(context),
                'enhanced_context_length': len(enhanced_context) if enhanced_context else 0,
                'user_context_length': len(user_context) if user_context else 0,
                'history_context_length': len(history_context) if history_context else 0
            }

        except Exception as e:
            logger.error(f"NL2SQL workflow processing failed: {e}")
            return {
                'success': False,
                'error': f"工作流程执行失败: {str(e)}",
                'step': 'workflow_error'
            }

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行SQL查询工具方法（兼容原接口）"""
        try:
            query = parameters.get("query", "")
            if not query:
                return ToolResult.error_result(
                    "缺少必需参数: query",
                    tool_name=self.name
                )

            # 安全检查：只允许SELECT查询
            if not query.strip().upper().startswith('SELECT'):
                return ToolResult.error_result(
                    "出于安全考虑，只允许执行SELECT查询",
                    tool_name=self.name,
                    metadata={"query": query}
                )

            # 执行查询
            result = self.sql_executor.execute_sql_query(query)

            return ToolResult.success_result(
                data=result,
                tool_name=self.name,
                metadata={"query": query, "type": "sql_query"}
            )

        except Exception as e:
            self.logger.error(f"SQL query execution error: {e}")
            return ToolResult.error_result(
                f"SQL查询执行失败: {str(e)}",
                tool_name=self.name,
                metadata={"query": parameters.get("query", "")}
            )

    # 保持原有的私有辅助方法
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
            from core.chat.llm import llm_service
            if not llm_service:
                return None

            # 获取更详细的表信息
            tables_summary = []
            for table in all_tables:
                try:
                    # 先获取表的详细结构
                    schema_result = self.table_manager.get_table_schema(table['table_name'])
                    if schema_result.get('success'):
                        columns_info = []
                        for col in schema_result['columns']:
                            col_desc = f"{col['name']} ({col['type']})"
                            if col.get('comment'):
                                col_desc += f" -- {col['comment']}"
                            columns_info.append(f"  - {col_desc}")

                        tables_summary.append(
                            f"表名: {table['table_name']}\n注释: {schema_result.get('table_comment', table['comment'])}\n字段:\n" + "\n".join(columns_info)
                        )
                    else:
                        # 回退到基本信息
                        logger.warning(f"Failed to get schema for table {table['table_name']}: {schema_result.get('error', 'Unknown error')}")
                        tables_summary.append(
                            f"表名: {table['table_name']}, 注释: {table['comment']}"
                        )
                except Exception as e:
                    logger.error(f"Error processing table {table['table_name']}: {e}")
                    # 回退到基本信息
                    tables_summary.append(
                        f"表名: {table['table_name']}, 注释: {table['comment']}"
                    )

            tables_text = "\n\n".join(tables_summary)

            prompt = f"""请分析用户问题，确定需要查询哪些数据库表。

用户问题: {question}

可用表列表:
{tables_text}

对话上下文:
{context if context else '无'}

分析指导:
1. 如果用户提到"订单号"、"订单"，请优先考虑"orders"表
2. 如果用户提到"配送"、"车辆"等物流相关信息，虽然可能没有直接的配送表，但orders表可能包含配送相关信息
3. 请仔细阅读表的字段信息，判断哪个表最可能包含相关数据
4. 即使没有完全匹配的表，也请选择最可能相关的表

请根据用户问题，从上面的表列表中选择需要查询的表名。只返回表名列表，用逗号分隔。如果实在找不到任何相关表，请返回"无"。

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

            return table_names

        except Exception as e:
            logger.error(f"Failed to analyze tables needed for the question: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
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
            from core.chat.llm import llm_service
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

            # 强化的SQL验证
            if not sql_query.upper().startswith('SELECT'):
                return {
                    'success': False,
                    'error': f"生成的SQL不是有效的SELECT查询: {sql_query}"
                }

            # 检查SQL的基本结构
            if not re.search(r'\bFROM\b', sql_query, re.IGNORECASE):
                logger.warning(f"Generated SQL missing FROM clause: {sql_query}")
                return {
                    'success': False,
                    'error': f"生成的SQL缺少FROM子句: {sql_query}"
                }

            logger.info(f"Successfully generated SQL: {sql_query}")
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
            result = self.sql_executor.execute_sql_query(sql_query)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _generate_final_answer(self, question: str, sql_query: str, query_result: str, context: str) -> str:
        """LLM生成最终回答"""
        try:
            from core.chat.llm import llm_service
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

请基于查询结果，用自然语言直接回答用户的问题。重要要求：
1. 直接使用查询结果中的具体数值来回答，不要使用字段名
2. 回答要简洁明了，例如：如果查询结果是 "follower: 张三"，要回答"张三"而不是"follower"
3. 如果查询无结果，说明原因
4. 不要在回答中重复技术细节或字段名

回答:"""

            # 调用LLM生成回答
            response = await llm_service.generate_response(prompt)
            return response.strip()

        except Exception as e:
            logger.error(f"Failed to generate final answer: {e}")
            return f"根据查询结果回答您的问题，但处理时出现错误: {str(e)}"

# 保持向后兼容的类和函数
class NL2SQLWorkflow(NL2SQLTool):
    """向后兼容的NL2SQL工作流程类"""
    pass

# 工厂函数
def get_nl2sql_tool() -> NL2SQLTool:
    """获取NL2SQL工具实例"""
    return NL2SQLTool()

def get_nl2sql_workflow() -> NL2SQLWorkflow:
    """获取NL2SQL工作流程实例（向后兼容）"""
    return NL2SQLWorkflow()