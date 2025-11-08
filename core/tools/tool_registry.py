"""
工具注册器
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from .base_tool import BaseTool
from .result import ToolResult

logger = logging.getLogger(__name__)

class ToolRegistry:
    """工具注册器 - 管理所有工具的注册、检测和执行"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._tools: List[BaseTool] = []
        self._tool_schemas: List[Dict[str, Any]] = []
        self._load_tools()

    def _load_tools(self):
        """加载所有工具"""
        try:
            # 导入并注册NL2SQL工具
            try:
                from .nl2sql.workflow import NL2SQLTool
                self.register_tool(NL2SQLTool())
                logger.debug("NL2SQL tool loaded")
            except Exception as e:
                logger.warning(f"Failed to load NL2SQL tool: {e}")

            # 导入并注册语音知识库工具
            try:
                from .voice_kb.voice_workflow import VoiceKBTool
                self.register_tool(VoiceKBTool())
                logger.debug("Voice KB tool loaded")
            except Exception as e:
                logger.warning(f"Failed to load Voice KB tool: {e}")

            # 导入并注册时间工具
            try:
                from .time.workflow import TimeTool
                self.register_tool(TimeTool())
                logger.debug("Time tool loaded")
            except Exception as e:
                logger.warning(f"Failed to load Time tool: {e}")

            # 导入并注册ADB工具
            try:
                from .adb.workflow import ADBTool
                self.register_tool(ADBTool())
                logger.debug("ADB tool loaded")
            except Exception as e:
                logger.warning(f"Failed to load ADB tool: {e}")

            # 导入并注册Web搜索工具
            try:
                from .web_search.workflow import WebSearchTool
                self.register_tool(WebSearchTool())
                logger.debug("Web search tool loaded")
            except Exception as e:
                logger.warning(f"Failed to load Web search tool: {e}")

            # 按优先级排序
            self._tools.sort(key=lambda tool: tool.priority)

            logger.info(f"Loaded {len(self._tools)} tools: {[tool.name for tool in self._tools]}")

        except Exception as e:
            logger.error(f"Failed to load tools: {e}")

    def register_tool(self, tool: BaseTool):
        """注册工具"""
        if tool.is_enabled():
            self._tools.append(tool)
            self._tool_schemas.append(tool.get_tool_schema())
            logger.debug(f"Registered tool: {tool.name}")

    def get_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """根据名称获取工具实例"""
        for tool in self._tools:
            if tool.name == tool_name:
                return tool
        return None

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取所有可用工具的Schema"""
        return self._tool_schemas.copy()

    async def process_with_tools(self, user_message: str, generate_response_func: Callable,
                               conversation_manager=None, user_id: str = None,
                               platform: str = None) -> Optional[str]:
        """使用工具处理用户消息 - 支持多步骤执行"""
        if not user_message or not user_message.strip():
            return None

        try:
            # 首先检查是否为多步骤操作
            multi_step_plan = await self._analyze_multi_step_request(
                user_message, generate_response_func,
                conversation_manager, user_id, platform
            )

            if multi_step_plan:
                # 执行多步骤计划
                self.logger.info(f"Executing multi-step plan with {len(multi_step_plan)} steps")
                return await self._execute_multi_step_plan(
                    multi_step_plan, generate_response_func,
                    conversation_manager, user_id, platform
                )

            # 单步骤操作 - 使用LLM选择的工具
            selected_tool = await self._select_tool_with_llm(
                user_message, generate_response_func,
                conversation_manager, user_id, platform
            )

            if selected_tool:
                self.logger.info(f"LLM selected tool: {selected_tool.name}")
                # 首先检查工具是否能处理该消息
                can_handle = await selected_tool.can_handle(user_message)
                if not can_handle:
                    self.logger.info(f"Tool '{selected_tool.name}' cannot handle this message")
                    return None

                try:
                    result = await selected_tool.process(
                        user_message, generate_response_func,
                        conversation_manager, user_id, platform
                    )
                    if result:
                        return result
                except Exception as e:
                    self.logger.error(f"Tool '{selected_tool.name}' execution failed: {e}")
                    return None
            else:
                self.logger.info("No tool was selected by LLM")
                return None

        except Exception as e:
            logger.error(f"Tool processing error: {e}")
            return None

    async def _select_tool_with_llm(self, user_message: str, generate_response_func: Callable,
                                  conversation_manager=None, user_id: str = None,
                                  platform: str = None) -> Optional['BaseTool']:
        """使用LLM选择最合适的工具"""
        try:
            # 构建工具描述列表
            tool_descriptions = []
            for tool in self._tools:
                tool_descriptions.append({
                    "name": tool.name,
                    "description": tool.description,
                    "priority": tool.priority
                })

            # 构建LLM提示词
            prompt = self._build_llm_selection_prompt(
                user_message, tool_descriptions,
                conversation_manager, user_id, platform
            )

            # 直接调用现有的LLM服务进行工具选择
            response = await generate_response_func(prompt)

            # 解析LLM响应
            return self._parse_llm_selection(response)

        except Exception as e:
            self.logger.error(f"LLM tool selection failed: {e}")
            return None

    def _build_llm_selection_prompt(self, user_message: str, tool_descriptions: List[Dict[str, Any]],
                                  conversation_manager=None, user_id: str = None,
                                  platform: str = None) -> str:
        """构建LLM工具选择提示词"""

        # 格式化工具描述
        tools_text = ""
        for i, tool in enumerate(tool_descriptions, 1):
            tools_text += f"{i}. **{tool['name']}** (优先级: {tool['priority']})\n"
            tools_text += f"   描述: {tool['description']}\n\n"

        # 获取上下文信息
        context_info = ""
        if conversation_manager and user_id:
            try:
                recent_messages = conversation_manager.get_recent_messages(
                    user_id=user_id, platform=platform, limit=2
                )
                if recent_messages:
                    context_info = "\n最近对话:\n"
                    for msg in recent_messages:
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')[:100]  # 限制长度
                        context_info += f"{role}: {content}...\n"
            except Exception:
                pass  # 忽略错误

        prompt = f"""你是一个智能工具选择器。请根据用户的需求和意图，选择最合适的工具来处理。

用户消息: {user_message}
{context_info}

可用工具:
{tools_text}

选择标准:
**优先级规则**: 当用户明确使用"搜索"关键词时，优先选择Web搜索工具

1. **Web搜索工具**: 用户需要搜索网络信息、最新资讯或实时内容时使用
   - **优先关键词**: 搜索、查找、搜、查一下、找一找、检索
   - 其他关键词: 最新、新闻、当前、实时、网页、网站等
   - 示例: "搜索Python最新版本"、"查找今天新闻"、"搜索 eogee"、"实时信息查询"
   - **注意**: 只要包含"搜索"相关词汇，就优先使用Web搜索工具

2. **NL2SQL工具**: 用户需要查询、统计、分析数据库中的数据时使用（不包含"搜索"关键词）
   - 关键词: 查询、统计、多少、几个、总数、平均、最高、最低、列表等
   - 示例: "查询所有用户信息"、"统计产品数量"、"销售额最高的产品"
   - **排除**: 如果同时有"搜索"关键词，则优先选择Web搜索工具

3. **语音知识库工具**: 用户输入英文内容时使用，通过embedding模型快速匹配语音知识库
   - 主要用于英文内容的快速响应
   - 示例: "Hello", "How are you", "What's the weather"等英文输入

4. **时间工具**: 用户需要时间相关信息或生成时间条件时使用
   - 关键词: 时间、日期、现在、今天、昨天、明天、时间范围等
   - 示例: "现在几点了"、"解析时间表达式"、"生成时间条件"

5. **ADB工具**: 用户需要自动化操作App时使用
   - 关键词: 登录、登出、自动化等
   - 示例: "自动登录应用"

**重要**: 只选择完全匹配用户需求的工具，不要试图选择"差不多"的工具。如果没有工具能够准确处理用户的请求，请回答"无工具"。

请直接回答工具名称（nl2sql、voice_kb、time、adb、web_search）或"无工具"，不要添加其他解释:
"""
        return prompt

    def _parse_llm_selection(self, response: str) -> Optional['BaseTool']:
        """解析LLM选择结果"""
        try:
            response = response.strip()

            # 提取工具名称
            if response.lower() == "无工具" or response.lower() == "none":
                return None

            # 查找匹配的工具
            for tool in self._tools:
                if tool.name.lower() == response.lower() or tool.name.lower() in response.lower():
                    return tool

            # 模糊匹配
            for tool in self._tools:
                if any(keyword in response.lower() for keyword in tool.description.lower().split()):
                    return tool

            return None

        except Exception as e:
            self.logger.error(f"Failed to parse LLM selection: {e}")
            return None

    
    async def execute_tool_by_name(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """根据工具名称执行工具（兼容原ToolManager.execute_tool接口）"""
        try:
            # 查找工具
            tool = None
            for t in self._tools:
                if t.name == tool_name:
                    tool = t
                    break

            if not tool:
                return ToolResult.error_result(
                    f"未知工具: {tool_name}",
                    tool_name=tool_name
                )

            # 执行工具
            if hasattr(tool, 'execute'):
                result = await tool.execute(parameters)
                return result
            else:
                return ToolResult.error_result(
                    f"工具 '{tool_name}' 不支持直接执行",
                    tool_name=tool_name
                )

        except Exception as e:
            logger.error(f"Tool execution error '{tool_name}': {e}")
            return ToolResult.error_result(
                f"工具执行失败: {str(e)}",
                tool_name=tool_name
            )

    async def _analyze_multi_step_request(self, user_message: str, generate_response_func: Callable,
                                        conversation_manager=None, user_id: str = None,
                                        platform: str = None) -> Optional[List[Dict[str, Any]]]:
        """分析用户请求，判断是否为多步骤操作并返回执行计划"""
        try:
            # 使用LLM分析用户意图，识别多步骤操作
            analysis_prompt = f"""你是一个工作流分析助手，请分析用户的请求，判断是否需要多步骤操作。

用户请求: {user_message}

可用工具和操作:
1. ADB工具:
   - login: 登录应用（关键词：登录、进入、打开）
   - logout: 登出/退出应用（关键词：退出、登出、关闭、离开）
   - get_status: 获取状态（关键词：状态、情况、当前状况）

2. NL2SQL工具: 数据库查询操作
3. 时间工具: 时间相关操作
4. 语音知识库工具: 语音检索操作
5. Web搜索工具: 网络搜索操作

请分析用户请求，确定：
1. 是否需要多步骤执行（是/否）
2. 如果需要，请列出具体的执行步骤（按顺序）

如果是多步骤操作，请按以下JSON格式回答，不要包含其他文字：
```json
{{
  "multi_step": true,
  "steps": [
    {{"tool": "adb", "operation": "login", "description": "登录账号"}},
    {{"tool": "adb", "operation": "logout", "description": "退出账号"}}
  ]
}}
```

如果是单步骤操作，请回答：
```json
{{
  "multi_step": false
}}
```

请严格按照JSON格式回答:"""

            response = await generate_response_func(analysis_prompt)
            response = response.strip()

            # 尝试解析JSON响应
            try:
                import json
                analysis_result = json.loads(response)

                if analysis_result.get("multi_step", False):
                    steps = analysis_result.get("steps", [])
                    if steps and len(steps) > 1:
                        self.logger.info(f"Detected multi-step operation with {len(steps)} steps")
                        return steps

                return None  # 单步骤操作或无效的多步骤计划

            except json.JSONDecodeError:
                # JSON解析失败，可能是文本响应
                if any(keyword in response.lower() for keyword in ['是', '步骤', '然后', '接着', '再']):
                    # 尝试从文本中提取步骤信息
                    return self._extract_steps_from_text(response)

                return None

        except Exception as e:
            logger.error(f"Multi-step analysis failed: {e}")
            return None

    def _extract_steps_from_text(self, text_response: str) -> Optional[List[Dict[str, Any]]]:
        """从文本响应中提取步骤信息"""
        try:
            steps = []
            lines = text_response.strip().split('\n')

            for line in lines:
                line = line.strip()
                if not line or not any(keyword in line for keyword in ['步骤', 'step', '然后', '接着']):
                    continue

                # 尝试识别工具和操作
                tool_found = None
                operation_found = None

                # 识别ADB操作
                if any(keyword in line for keyword in ['登录', 'login']):
                    tool_found = 'adb'
                    operation_found = 'login'
                elif any(keyword in line for keyword in ['退出', '登出', 'logout']):
                    tool_found = 'adb'
                    operation_found = 'logout'
                elif any(keyword in line for keyword in ['状态', 'status']):
                    tool_found = 'adb'
                    operation_found = 'get_status'

                if tool_found and operation_found:
                    steps.append({
                        "tool": tool_found,
                        "operation": operation_found,
                        "description": line
                    })

            return steps if len(steps) > 1 else None

        except Exception as e:
            logger.error(f"Failed to extract steps from text: {e}")
            return None

    async def _execute_multi_step_plan(self, steps: List[Dict[str, Any]], generate_response_func: Callable,
                                     conversation_manager=None, user_id: str = None,
                                     platform: str = None) -> str:
        """执行多步骤计划"""
        try:
            execution_results = []

            for i, step in enumerate(steps):
                tool_name = step.get("tool")
                operation = step.get("operation")
                description = step.get("description", f"步骤{i+1}")

                self.logger.info(f"Executing step {i+1}: {tool_name}.{operation}")

                try:
                    # 获取工具实例
                    tool = self.get_tool_by_name(tool_name)
                    if not tool:
                        result = f"步骤{i+1}失败: 工具 {tool_name} 不存在"
                        execution_results.append(result)
                        break

                    # 执行步骤
                    if tool_name == 'adb':
                        # ADB工具特殊处理
                        result = await self._execute_adb_operation(tool, operation, description)
                    else:
                        # 其他工具的通用处理
                        result = await tool.process(
                            description, generate_response_func,
                            conversation_manager, user_id, platform
                        )

                    if result:
                        execution_results.append(f"步骤{i+1}完成: {result}")
                    else:
                        execution_results.append(f"步骤{i+1}完成，但无返回结果")

                except Exception as e:
                    error_msg = f"步骤{i+1}执行失败: {str(e)}"
                    execution_results.append(error_msg)
                    logger.error(f"Step {i+1} execution failed: {e}")
                    break

            # 生成执行报告
            return self._generate_execution_summary(execution_results)

        except Exception as e:
            logger.error(f"Multi-step execution failed: {e}")
            return f"多步骤执行失败: {str(e)}"

    async def _execute_adb_operation(self, tool: 'BaseTool', operation: str, description: str) -> Optional[str]:
        """执行ADB操作"""
        try:
            if operation == 'login':
                result = await tool._execute_adb_login({})
            elif operation == 'logout':
                result = await tool._execute_adb_logout({})
            elif operation == 'get_status':
                result = await tool._get_adb_status({})
            else:
                # 使用智能处理
                result = await tool._process_with_llm(description, lambda x: x)

            if result and hasattr(result, 'success') and result.success:
                return f"{description}已完成"
            elif isinstance(result, str):
                return result
            else:
                return f"{description}已完成"

        except Exception as e:
            logger.error(f"ADB operation failed: {e}")
            raise

    def _generate_execution_summary(self, execution_results: List[str]) -> str:
        """生成执行摘要"""
        if not execution_results:
            return "执行完成，但无结果返回"

        # 统计成功和失败的步骤
        success_count = sum(1 for result in execution_results if "完成" in result and "失败" not in result)
        failed_count = len(execution_results) - success_count

        summary = f"执行报告 ({success_count + failed_count}个步骤):\n"

        for i, result in enumerate(execution_results, 1):
            status_icon = "[成功]" if "完成" in result and "失败" not in result else "[失败]"
            summary += f"{status_icon} {result}\n"

        # 添加总结
        if failed_count == 0:
            summary += f"\n所有{success_count}个步骤已成功完成！"
        else:
            summary += f"\n{success_count}个步骤成功，{failed_count}个步骤失败"

        return summary

    def get_tool_status(self) -> Dict[str, Any]:
        """获取工具状态信息"""
        return {
            "total_tools": len(self._tools),
            "enabled_tools": len([t for t in self._tools if t.is_enabled()]),
            "tools": [
                {
                    "name": tool.name,
                    "priority": tool.priority,
                    "enabled": tool.is_enabled(),
                    "description": tool.description
                }
                for tool in self._tools
            ]
        }

    # 兼容原tool_manager的接口方法
    def get_tool_list(self) -> List[Dict[str, Any]]:
        """兼容原get_tool_list接口"""
        return self.get_available_tools()

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """兼容原execute_tool接口"""
        return await self.execute_tool_by_name(tool_name, parameters)

    def is_sql_question(self, question: str) -> bool:
        """兼容原is_sql_question接口"""
        try:
            # 查找NL2SQL工具
            for tool in self._tools:
                if tool.name == "nl2sql":
                    # 这里我们需要检查该工具是否实现了is_sql_question方法
                    # 如果没有，使用can_handle作为替代
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            task = asyncio.create_task(tool.can_handle(question))
                            return task
                        else:
                            return asyncio.run(tool.can_handle(question))
                    except Exception:
                        return False
            return False
        except Exception as e:
            logger.error(f"SQL question detection failed: {e}")
            return False

    def is_voice_kb_question(self, question: str) -> bool:
        """兼容原is_voice_kb_question接口"""
        try:
            # 查找语音知识库工具
            for tool in self._tools:
                if tool.name == "voice_kb":
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            task = asyncio.create_task(tool.can_handle(question))
                            return task
                        else:
                            return asyncio.run(tool.can_handle(question))
                    except Exception:
                        return False
            return False
        except Exception as e:
            logger.error(f"Voice KB question detection failed: {e}")
            return False

# 全局注册器实例
_registry_instance: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    """获取工具注册器单例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ToolRegistry()
    return _registry_instance

# 兼容原接口的函数
def get_tool_manager():
    """兼容原get_tool_manager接口"""
    return get_tool_registry()

async def process_with_tools(user_message: str, generate_response_func: Callable,
                           conversation_manager=None, user_id: str = None,
                           platform: str = None) -> Optional[str]:
    """兼容原process_with_tools接口"""
    registry = get_tool_registry()
    return await registry.process_with_tools(
        user_message, generate_response_func,
        conversation_manager, user_id, platform
    )