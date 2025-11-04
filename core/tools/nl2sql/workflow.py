import logging
from typing import Dict, Any, List, Optional
from .table_info import get_table_manager, get_all_tables
from .sql_executor import get_sql_executor
from .context_manager import SQLContextManager
from .user_context_enhancer import get_user_context_enhancer

logger = logging.getLogger(__name__)

class NL2SQLWorkflow:
    """NL2SQL工作流程管理器"""

    def __init__(self):
        self.table_manager = get_table_manager()
        self.sql_executor = get_sql_executor()
        self.context_manager = SQLContextManager()
        self.user_context_enhancer = get_user_context_enhancer()

    async def process_sql_question(
        self,
        question: str,
        context: str = "",
        conversation_manager=None,
        user_id: str = None,
        platform: str = None
    ) -> Dict[str, Any]:
        """
        处理SQL相关问题的完整工作流程

        工作流程（支持用户上下文）：
        0. 获取用户上下文信息（用户名、公司、ID等元数据）
        0.5. 自动获取相关会话历史记录
        1. 调用get_relevant_tables()获取初步表信息
        2. LLM分析问题并确定需要的表结构（基于用户上下文+历史上下文）
        3. 调用get_table_schemas()获取详细表结构
        4. LLM基于表结构、用户上下文和历史上下文生成SQL语句
        5. 执行SQL查询
        6. LLM基于结果和完整上下文生成最终回答

        参数:
            question: 用户问题
            context: 手动提供的对话上下文
            conversation_manager: 会话管理器实例（用于自动获取历史记录）
            user_id: 用户ID（用于获取历史记录和用户信息）
            platform: 平台标识（用于获取历史记录）

        返回:
            包含处理结果或错误信息的字典
        """
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

    async def _analyze_time_requirements(self, question: str, table_schemas: str) -> Dict[str, Any]:
        """分析问题中的时间需求并调用时间工具"""
        try:
            # 检查是否启用时间工具
            try:
                from config import Config
                if not getattr(Config, 'TIME_TOOLS_ENABLED', True):
                    return {"has_time_requirement": False}
            except Exception as e:
                logger.warning(f"Failed to check TIME_TOOLS_ENABLED: {e}")
                return {"has_time_requirement": False}

            # 检查是否包含时间关键词
            time_keywords = ['本月', '最近', '今天', '昨天', '本年', '上月', '本周', '上周', '季度', '年', '月', '天',
                           '今日', '昨日', '明日', '当月', '今年', '当年', '过去', '未来', '接下来', '上个', '下个']
            has_time_keywords = any(keyword in question for keyword in time_keywords)

            if not has_time_keywords:
                return {"has_time_requirement": False}

            # 获取工具管理器
            from core.chat.tool_manager import get_tool_manager
            tool_manager = get_tool_manager()

            if not tool_manager:
                logger.warning("Tool manager not available for time analysis")
                return {"has_time_requirement": False}

            # 1. 获取当前时间
            current_time_result = await tool_manager.execute_tool("get_current_time", {})

            # 2. 提取并解析时间表达式
            from core.tools.nl2sql.time_utils import get_time_utils
            time_utils = get_time_utils()
            time_expressions = time_utils.extract_time_expressions(question)
            logger.info(f"Extracted time expressions from '{question}': {time_expressions}")
            time_analysis_results = []

            for expression in time_expressions:
                try:
                    parse_result = await tool_manager.execute_tool("parse_time_expression", {
                        "expression": expression
                    })

                    if parse_result.success:
                        time_analysis_results.append({
                            "expression": expression,
                            "time_range": parse_result.data
                        })
                        logger.info(f"Time expression '{expression}' parsed successfully: {parse_result.data}")
                    else:
                        logger.warning(f"Failed to parse time expression '{expression}': {parse_result.error}")
                except Exception as e:
                    logger.error(f"Error parsing time expression '{expression}': {e}")

            # 3. 识别可能的时间字段
            time_columns = time_utils.identify_time_columns(table_schemas)

            # 4. 为每个时间表达式生成SQL条件（用于提供给LLM参考）
            sql_conditions = []
            valid_time_analysis_results = []

            for result in time_analysis_results:
                time_range = result["time_range"]
                expression = result["expression"]

                # 验证时间解析结果的有效性
                if not time_range.get("success"):
                    logger.warning(f"Time expression '{expression}' parsing failed: {time_range.get('error')}")
                    continue

                # 检查必要字段是否存在且有效
                start_date = time_range.get("start_date_only")
                end_date = time_range.get("end_date_only")

                if not start_date or not end_date:
                    logger.warning(f"Time expression '{expression}' has invalid date range")
                    continue

                # 验证日期格式
                try:
                    from datetime import datetime
                    datetime.strptime(start_date, "%Y-%m-%d")
                    datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    logger.warning(f"Time expression '{expression}' has invalid date format")
                    continue

                valid_time_analysis_results.append(result)

                # 为每个时间字段生成SQL条件
                for column in time_columns:
                    try:
                        sql_result = await tool_manager.execute_tool("generate_sql_time_condition", {
                            "time_range": str(time_range),  # 转换为字符串
                            "column_name": column
                        })
                        if sql_result.success and sql_result.data.get("sql_condition"):
                            sql_conditions.append({
                                "expression": expression,
                                "column": column,
                                "condition": sql_result.data["sql_condition"]
                            })
                    except Exception as e:
                        logger.error(f"Error generating SQL condition for {expression} on {column}: {e}")

            # 如果没有有效的时间分析结果，关闭时间需求标志
            if not valid_time_analysis_results:
                logger.info("No valid time expressions found, disabling time analysis")
                return {"has_time_requirement": False}

            return {
                "has_time_requirement": True,
                "time_expressions": time_expressions,
                "time_analysis_results": valid_time_analysis_results,  # 只使用有效结果
                "suggested_columns": time_columns,
                "current_time": current_time_result.data if current_time_result.success else None,
                "sql_conditions": sql_conditions
            }

        except Exception as e:
            logger.error(f"Time requirements analysis failed: {e}")
            return {"has_time_requirement": False}

    async def _generate_sql(self, question: str, table_schemas: str, context: str) -> Dict[str, Any]:
        """LLM生成SQL语句 - 增强时间信息支持"""
        try:
            from core.chat.llm import get_llm_service

            llm_service = get_llm_service()
            if not llm_service:
                return {
                    'success': False,
                    'error': 'LLM服务不可用'
                }

            # 分析时间需求
            time_analysis = await self._analyze_time_requirements(question, table_schemas)

            # 构建基础提示词
            prompt = f"""你是一个专业的SQL查询生成器。请根据用户问题和表结构信息，生成准确的SQL查询语句。

用户问题: {question}

表结构信息:
{table_schemas}

对话上下文:
{context if context else '无'}"""

            # 添加时间相关信息
            if time_analysis.get("has_time_requirement"):
                time_info = "\n\n## 时间相关信息\n\n"
                time_info += f"检测到时间相关需求，识别到的时间表达式: {', '.join(time_analysis.get('time_expressions', []))}\n\n"

                # 添加时间分析结果
                for result in time_analysis.get("time_analysis_results", []):
                    expr = result["expression"]
                    time_range = result["time_range"]
                    if time_range.get("success"):
                        start_date = time_range.get("start_date_only", "")
                        end_date = time_range.get("end_date_only", "")
                        time_info += f"时间表达式 '{expr}' 解析为: {start_date} 到 {end_date}\n"
                    else:
                        time_info += f"时间表达式 '{expr}' 解析失败: {time_range.get('error', '未知错误')}\n"

                # 建议的时间字段
                if time_analysis.get("suggested_columns"):
                    time_info += f"建议的时间字段: {', '.join(time_analysis['suggested_columns'])}\n\n"

                # 生成的SQL条件示例（提供给LLM参考）
                if time_analysis.get("sql_conditions"):
                    time_info += "可参考的时间条件示例:\n"
                    for condition in time_analysis["sql_conditions"][:3]:  # 只显示前3个示例
                        time_info += f"  - {condition['expression']} 使用 {condition['column']}: {condition['condition']}\n"
                    time_info += "\n"

                # 当前时间
                if time_analysis.get("current_time"):
                    current_time = time_analysis["current_time"]
                    if current_time.get("success"):
                        time_info += f"当前时间: {current_time.get('current_time')} (日期: {current_time.get('date')})\n"

                prompt += time_info

            # 添加通用规则
            prompt += f"""

请遵循以下规则:
1. 只生成SELECT查询语句
2. 确保SQL语法正确，符合MySQL规范
3. 使用适当的WHERE条件"""

            # 添加时间相关的规则
            if time_analysis.get("has_time_requirement"):
                prompt += """
4. 如果问题包含时间需求，请使用时间范围条件过滤数据
5. 优先使用建议的时间字段（如包含time、date、created等字段的字段名）
6. 使用BETWEEN或者>=和<=来构建时间范围条件，确保时间格式匹配
7. 如果有多个时间表达式，请根据问题意图选择最合适的，或者都包含在WHERE条件中
8. 可以使用聚合函数如COUNT、SUM、AVG、MAX、MIN"""
            else:
                prompt += """
4. 可以使用聚合函数如COUNT、SUM、AVG、MAX、MIN"""

            prompt += """
9. 确保表名和字段名与提供的信息完全匹配
10. 只返回SQL语句，不要包含其他解释文字

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

            # 检查是否有过长的内容（可能是自然语言）
            if len(sql_query) > 500:
                logger.warning(f"Generated SQL too long ({len(sql_query)} chars): {sql_query[:100]}...")
                return {
                    'success': False,
                    'error': f"生成的SQL过长，可能不是有效的SQL语句"
                }

            # 检查常见的自然语言模式
            natural_language_patterns = [
                r'好的|我帮您|请问|还有其他|需要帮忙吗|您的是|根据您的',
                r'以下是|以下是您|让我为您|我来帮您|很抱歉|对不起',
                r'查询一下|统计一下|计算一下|显示一下'
            ]

            for pattern in natural_language_patterns:
                if re.search(pattern, sql_query):
                    logger.warning(f"Generated SQL contains natural language patterns: {sql_query}")
                    return {
                        'success': False,
                        'error': f"生成的SQL包含自然语言内容，请重新生成纯SQL语句"
                    }

            logger.info(f"Successfully generated SQL: {sql_query}")
            return {
                'success': True,
                'generated_sql': sql_query,
                'time_analysis': time_analysis
            }

        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            return {
                'success': False,
                'error': str(e),
                'time_analysis': time_analysis
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

    def should_use_enhanced_context(self, question: str, user_id: str = None) -> bool:
        """
        判断是否应该使用增强的上下文功能

        Args:
            question: 当前问题
            user_id: 用户ID

        Returns:
            是否启用增强上下文
        """
        return self.context_manager.should_use_enhanced_context(question, user_id)

    async def process_sql_question_legacy(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        处理SQL相关问题的传统工作流程（向后兼容）

        Args:
            question: 用户问题
            context: 对话上下文

        Returns:
            包含处理结果或错误信息的字典
        """
        return await self.process_sql_question(question, context)

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

# 全局实例
_workflow = None

def get_nl2sql_workflow() -> NL2SQLWorkflow:
    """获取NL2SQL工作流程实例"""
    global _workflow
    if _workflow is None:
        _workflow = NL2SQLWorkflow()
    return _workflow