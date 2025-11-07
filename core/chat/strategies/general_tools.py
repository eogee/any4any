"""
通用工具处理策略
"""
import asyncio
import json
import logging
from typing import Optional, Callable, Any, List, Dict

from .base import ProcessingStrategy

logger = logging.getLogger(__name__)

class GeneralToolsStrategy(ProcessingStrategy):
    """通用工具处理策略"""

    def __init__(self, tools_enabled=True):
        self._tools_enabled = tools_enabled
        self._tool_manager = None

    @property
    def tool_manager(self):
        if self._tool_manager is None and self._tools_enabled:
            try:
                from core.chat.tool_manager import get_tool_manager
                self._tool_manager = get_tool_manager()
            except Exception as e:
                logger.error(f"Tool manager init error: {e}")
        return self._tool_manager

    async def can_handle(self, user_message: str) -> bool:
        return self._tools_enabled and self.tool_manager is not None

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        try:
            tool_decision = await self._analyze_tool_needs(user_message, generate_response_func)

            if tool_decision["needs_tools"]:
                tool_results = await self._execute_tools(tool_decision["tool_calls"], user_message)
                response = await self._generate_response_with_tools(
                    user_message, tool_results, generate_response_func
                )
                return response
            else:
                return None

        except Exception as e:
            logger.error(f"General tool processing error: {e}")
            return None

    async def _analyze_tool_needs(self, user_message: str, generate_response_func: Callable) -> Dict[str, Any]:
        try:
            available_tools = self.get_available_tools()

            if not available_tools:
                return {"needs_tools": False, "tool_calls": []}

            tools_schema = self._build_tools_schema(available_tools)

            system_prompt = "智能助手：判断问题是否需要工具调用。数据查询/计算/外部访问时使用工具，一般对话不需要。"
            user_prompt = f"""问题: {user_message}

可用工具:
-{tools_schema}

需要工具时返回：
{{"needs_tools": true, "tool_calls": ["工具名"], "reason": "原因"}}

不需要时返回：
{{"needs_tools": false, "reason": "原因"}}

只返回JSON。"""

            analysis_prompt = f"{system_prompt}\n\n{user_prompt}"
            analysis_result = await generate_response_func(analysis_prompt)

            return self._parse_json_decision(analysis_result, available_tools)

        except Exception as e:
            logger.error(f"Tool analysis error: {e}")
            return {"needs_tools": False, "tool_calls": [], "reason": "工具分析失败"}

    def _build_tools_schema(self, available_tools: List[Dict]) -> str:
        schema_lines = []

        for tool in available_tools:
            schema_lines.append(f"{tool['name']}:")
            schema_lines.append(f"  描述: {tool['description']}")

            if tool.get('parameters'):
                parameters = tool['parameters']
                if isinstance(parameters, dict) and 'properties' in parameters:
                    schema_lines.append("  参数:")
                    for param_name, param_info in parameters['properties'].items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', '无描述')
                        required_list = parameters.get('required', [])
                        required = "必需" if param_name in required_list else "可选"
                        schema_lines.append(f"    - {param_name} ({param_type}, {required}): {param_desc}")
                else:
                    schema_lines.append(f"    参数格式: {parameters}")

            schema_lines.append("")

        return "\n".join(schema_lines)

    def _parse_json_decision(self, analysis_result: str, available_tools: List[Dict]) -> Dict[str, Any]:
        try:
            cleaned_result = analysis_result.strip()
            if cleaned_result.startswith("```json"):
                cleaned_result = cleaned_result[7:]
            elif cleaned_result.startswith("```"):
                cleaned_result = cleaned_result[3:]
            if cleaned_result.endswith("```"):
                cleaned_result = cleaned_result[:-3].strip()

            if not cleaned_result:
                return {"needs_tools": False, "tool_calls": [], "reason": "返回了空的结果"}

            decision = json.loads(cleaned_result)

            if not isinstance(decision, dict):
                raise ValueError("Invalid JSON object")

            if 'needs_tools' not in decision:
                raise ValueError("Missing 'needs_tools' field")

            if decision.get('needs_tools') and 'tool_calls' not in decision:
                raise ValueError("Missing 'tool_calls' field")

            valid_tools = []
            available_tool_names = [tool['name'] for tool in available_tools]

            if decision.get('needs_tools') and decision.get('tool_calls'):
                for tool_name in decision['tool_calls']:
                    if tool_name in available_tool_names:
                        valid_tools.append(tool_name)

            return {
                "needs_tools": decision.get('needs_tools', False) and len(valid_tools) > 0,
                "tool_calls": valid_tools,
                "reason": decision.get('reason', '无原因说明')
            }

        except json.JSONDecodeError:
            logger.warning(f"JSON decode error for: {analysis_result}")
            return {"needs_tools": False, "tool_calls": [], "reason": "返回了无效的JSON格式"}
        except Exception as e:
            logger.error(f"Decision parsing error: {e}")
            return {"needs_tools": False, "tool_calls": [], "reason": f"决策解析失败: {str(e)}"}

    async def _execute_tools(self, tool_names: List[str], user_message: str) -> List[Dict[str, Any]]:
        if not self.tool_manager:
            return []

        async def execute_single_tool(tool_name: str) -> Dict[str, Any]:
            try:
                result = await asyncio.wait_for(
                    self.tool_manager.execute_tool(tool_name, {}),
                    timeout=30.0
                )
                return {
                    "tool": tool_name,
                    "result": result.to_dict()
                }
            except asyncio.TimeoutError:
                logger.error(f"Tool execution timeout '{tool_name}'")
                return {
                    "tool": tool_name,
                    "result": {"success": False, "error": "Execution timeout"}
                }
            except Exception as e:
                logger.error(f"Tool execution error '{tool_name}': {e}")
                return {
                    "tool": tool_name,
                    "result": {"success": False, "error": str(e)}
                }

        tasks = [execute_single_tool(tool_name) for tool_name in tool_names]
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for result in tool_results:
            if isinstance(result, Exception):
                logger.error(f"Unexpected error in tool execution: {result}")
                processed_results.append({
                    "tool": "unknown",
                    "result": {"success": False, "error": "Unexpected error"}
                })
            else:
                processed_results.append(result)

        return processed_results

    async def _generate_response_with_tools(
        self,
        user_message: str,
        tool_results: List[Dict[str, Any]],
        generate_response_func: Callable
    ) -> str:
        try:
            tool_context = self._build_tool_context(tool_results)
            response_prompt = f"""问题: {user_message}

-{tool_context}

基于工具结果回答问题。成功则回答，失败则解释原因。回答自然简洁。"""

            return await generate_response_func(response_prompt)

        except Exception as e:
            logger.error(f"Error generating response with tools: {e}")
            return "获取信息时遇到困难，请稍后再试。"

    def _build_tool_context(self, tool_results: List[Dict[str, Any]]) -> str:
        if not tool_results:
            return ""

        context_lines = ["\n## 工具执行结果\n"]
        max_display_rows = 10

        for i, tool_result in enumerate(tool_results, 1):
            tool_name = tool_result["tool"]
            result_data = tool_result["result"]

            if result_data.get("success"):
                if tool_name == "sql_query":
                    data = result_data.get("data", {})
                    context_lines.append(f"**数据库查询结果**:")

                    if 'formatted_result' in data:
                        formatted = data['formatted_result']
                        if '查询结果:' in formatted:
                            lines = formatted.split('\n')
                            data_start = False
                            table_data = []

                            for line in lines:
                                if '查询结果:' in line:
                                    data_start = True
                                elif data_start and line.strip():
                                    table_data.append(line.strip())

                            if table_data:
                                context_lines.extend(table_data[:max_display_rows])
                                if len(table_data) > max_display_rows:
                                    context_lines.append(f"... (共{len(table_data)}行数据)")
                            else:
                                context_lines.append(formatted)
                        else:
                            context_lines.append(formatted)
                    else:
                        context_lines.append("查询完成，但没有返回具体数据。")
                else:
                    context_lines.append(f"**{tool_name} 执行结果**:")
                    context_lines.append(f"{result_data.get('data', '操作完成')}")
            else:
                context_lines.append(f"**工具执行失败** ({tool_name}):")
                context_lines.append(f"错误信息: {result_data.get('error', '未知错误')}")

            if i < len(tool_results):
                context_lines.append("")

        return "\n".join(context_lines)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        if not self._tools_enabled or not self.tool_manager:
            return []

        try:
            return self.tool_manager.get_tool_list()
        except Exception as e:
            logger.error(f"Get available tools error: {e}")
            return []