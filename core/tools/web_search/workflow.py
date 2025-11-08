"""
Web搜索工具主要工作流
实现BaseTool接口，提供智能搜索功能
"""
import asyncio
import time
import re
import json
from typing import Dict, Any, Optional, Callable, List
import os

from ..base_tool import BaseTool
from ..result import ToolResult
from .bing_search import BingSearchEngine
from .search_types import (
    SearchResult, SearchResponse,
    SEARCH_INTENT_KEYWORDS,
    SQL_EXCLUDE_KEYWORDS,
    VOICE_EXCLUDE_PATTERNS
)
from .exceptions import WebSearchError


class WebSearchTool(BaseTool):
    """智能Web搜索工具 - 使用LLM解析问题并生成增强回答"""

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self.search_engine = None
        self._init_search_engine()

    def _init_search_engine(self):
        """初始化搜索引擎"""
        try:
            # 从环境变量读取配置
            proxy_url = os.getenv("WEB_SEARCH_PROXY_URL")
            use_proxy = os.getenv("WEB_SEARCH_USE_PROXY", "false").lower() == "true"
            timeout = int(os.getenv("WEB_SEARCH_TIMEOUT", "30"))

            # 配置代理
            final_proxy_url = proxy_url if use_proxy and proxy_url else None

            self.search_engine = BingSearchEngine(
                proxy_url=final_proxy_url,
                timeout=timeout
            )

        except Exception as e:
            self.logger.error(f"Web search tool initialization failed: {str(e)}")
            self.enabled = False

    @property
    def priority(self) -> int:
        """工具优先级"""
        return 50  # 中等优先级

    @property
    def name(self) -> str:
        """工具名称"""
        return "web_search"

    @property
    def description(self) -> str:
        """工具描述"""
        return "智能网络搜索工具，使用AI解析您的问题并生成增强回答"

    async def can_handle(self, user_message: str) -> bool:
        """
        判断是否能处理该消息
        基于用户请求意图判断是否需要网络搜索
        """
        if not user_message or not user_message.strip():
            return False

        message = user_message.strip()

        # 排除明显的SQL查询意图
        has_sql_intent = any(keyword in message.lower() for keyword in SQL_EXCLUDE_KEYWORDS)
        if has_sql_intent:
            return False

        # 排除纯英文的语音知识库意图
        message_lower = message.lower()
        is_english_only = bool(re.match(r'^[a-zA-Z\s0-9\.,!?]+$', message))
        is_simple_english = any(pattern in message_lower for pattern in VOICE_EXCLUDE_PATTERNS)
        if is_english_only and is_simple_english:
            return False

        # 基于意图判断 - 检测用户是否在询问需要外部信息的问题
        return self._detect_search_intent(message)

    def _detect_search_intent(self, message: str) -> bool:
        """
        检测用户的搜索意图
        不依赖关键词，而是分析问题的性质
        """
        message_lower = message.lower()

        # 意图类型1：明确的搜索请求
        search_patterns = [
            r".*(搜索|查找|搜|查一下|找一找|检索|search|find).*",  # 搜索动词
            r".*(帮我找|请找|能否找|可以找).*",  # 请求搜索
        ]

        for pattern in search_patterns:
            if re.search(pattern, message_lower):
                return True

        # 意图类型2：询问具体事物的信息
        entity_patterns = [
            r".*(是什么|who is|what is).*",  # 询问定义或身份
            r".*(怎么样|how about|what about).*",  # 询问状况或评价
            r".*(在哪里|where is).*",  # 询问位置
            r".*(什么时候|when).*",  # 询问时间
            r".*(为什么|why).*",  # 询问原因
            r".*(如何|怎么|how to).*",  # 询问方法
        ]

        for pattern in entity_patterns:
            if re.search(pattern, message_lower):
                return True

        # 意图类型2：询问最新或当前信息
        temporal_patterns = [
            r".*(最新|当前|现在|今天|最近|近日|本周|本月|今年).*",
            r".*(latest|current|now|today|recent|recently).*",
            r".*(新闻|news|消息|动态|发布|launch).*",
        ]

        for pattern in temporal_patterns:
            if re.search(pattern, message_lower):
                return True

        # 意图类型3：比较或选择类问题
        comparison_patterns = [
            r".*(对比|比较|哪个更好|选择|推荐).*",
            r".*(compare|comparison|better|recommend|choose).*",
            r".*(vs|versus).*",
        ]

        for pattern in comparison_patterns:
            if re.search(pattern, message_lower):
                return True

        # 意图类型4：具体名词查询（可能是需要外部信息的人、事、物）
        # 检测是否包含具体的人名、公司名、产品名、地名等
        concrete_noun_indicators = [
            # 人名相关
            r".*(总统|ceo|创始人|导演|演员|作家|科学家).*",
            r".*(president|ceo|founder|director|actor|writer|scientist).*",
            # 公司/组织相关
            r".*(公司|企业|机构|组织|品牌).*",
            r".*(company|corporation|organization|brand).*",
            # 产品相关
            r".*(手机|电脑|汽车|软件|游戏|电影|书籍).*",
            r".*(phone|computer|car|software|game|movie|book).*",
            # 地点相关
            r".*(国家|城市|餐厅|酒店|景点|学校).*",
            r".*(country|city|restaurant|hotel|attraction|school).*",
        ]

        for pattern in concrete_noun_indicators:
            if re.search(pattern, message_lower):
                return True

        # 意图类型5：寻求具体数据或事实
        factual_patterns = [
            r".*(多少|几个|数量|价格|评分|排名).*",
            r".*(how many|how much|price|rating|ranking).*",
            r".*(统计|数据|调查|报告).*",
            r".*(statistics|data|survey|report).*",
        ]

        for pattern in factual_patterns:
            if re.search(pattern, message_lower):
                return True

        # 意图类型6：求助或指导类问题
        help_patterns = [
            r".*(推荐|建议|帮助|解决|处理).*",
            r".*(recommend|suggest|help|solve|handle).*",
        ]

        for pattern in help_patterns:
            if re.search(pattern, message_lower):
                return True

        # 意图类型7：教程、指南、学习资源请求
        tutorial_patterns = [
            r".*(教程|指南|学习|入门|基础|教程).*",
            r".*(tutorial|guide|learn|intro|basics).*",
            r".*(资料|资源|文档|文档).*",
            r".*(material|resource|documentation|docs).*",
        ]

        for pattern in tutorial_patterns:
            if re.search(pattern, message_lower):
                return True

        return False

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        """
        处理用户消息，执行智能搜索并生成增强回答
        """
        if not self.enabled or not self.search_engine:
            return "智能Web搜索工具未启用或初始化失败"

        try:
            start_time = time.time()

            # 第一步：使用LLM解析用户问题
            self.logger.info(f"Start parsing user query: {user_message[:50]}...")
            parsed_query = await self._parse_user_query_with_llm(user_message, generate_response_func)

            # 第二步：执行智能搜索
            search_results = await self._perform_intelligent_search(parsed_query)

            if not search_results:
                return f"抱歉，我没有找到关于\"{parsed_query['search_keywords']}\"的相关信息。"

            # 第三步：使用LLM生成增强回答
            self.logger.info(f"Start generating enhanced answer based on {len(search_results)} search results...")
            enhanced_answer = await self._generate_enhanced_answer(
                user_message, parsed_query, search_results, generate_response_func
            )

            response_time = f"{time.time() - start_time:.1f}s"
            self.logger.info(f"Web search completed successfully, time taken: {response_time}")

            return enhanced_answer

        except Exception as e:
            error_msg = f"智能搜索过程中发生错误: {str(e)}"
            self.logger.error(error_msg)
            return f"抱歉，搜索服务暂时不可用。错误信息：{str(e)}"

    async def _parse_user_query_with_llm(self, user_message: str, generate_response_func: Callable) -> Dict[str, Any]:
        """
        使用LLM解析用户问题，提取搜索意图和关键词
        """
        parse_prompt = f"""你是一个智能搜索助手。请分析用户的问题并提取搜索关键词。

用户问题: "{user_message}"

请以JSON格式返回分析结果，包含以下字段：
1. "search_keywords": 主要搜索关键词（字符串）
2. "search_intent": 搜索意图（"fact_checking"事实核查, "latest_info"最新信息, "explanation"解释说明, "comparison"比较分析, "general_query"一般查询）
3. "question_type": 问题类型（"what"什么, "how"如何, "why"为什么, "when"何时, "where"哪里, "comparison"比较, "other"其他）
4. "key_entities": 关键实体列表（字符串列表）
5. "time_context": 时间上下文（如果有）
6. "expected_answer_type": 期望的答案类型（"factual"事实性, "opinion"观点性, "tutorial"教程类, "news"新闻类, "other"其他）

示例输出:
{{"search_keywords": "iPhone 15 Pro Max 评测", "search_intent": "latest_info", "question_type": "what", "key_entities": ["iPhone 15 Pro Max"], "time_context": "2024", "expected_answer_type": "factual"}}

请只返回JSON，不要添加其他解释："""

        try:
            response = await generate_response_func(parse_prompt)

            # 尝试解析JSON响应
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed_result = json.loads(json_match.group())

                # 验证必要字段
                if not parsed_result.get("search_keywords"):
                    # 如果LLM没有提取到关键词，使用原始消息
                    parsed_result["search_keywords"] = user_message.strip()

                self.logger.info(f"LLM parsed query: {parsed_result}")
                return parsed_result
            else:
                # 如果无法解析JSON，使用原始消息作为关键词
                self.logger.warning(f"LLM failed to parse query, using original query: {response[:100]}...")
                return {
                    "search_keywords": user_message.strip(),
                    "search_intent": "general_query",
                    "question_type": "other",
                    "key_entities": [],
                    "time_context": "",
                    "expected_answer_type": "factual"
                }

        except Exception as e:
            self.logger.error(f"LLM failed to parse user query: {str(e)}")
            # 回退到原始查询
            return {
                "search_keywords": user_message.strip(),
                "search_intent": "general_query",
                "question_type": "other",
                "key_entities": [],
                "time_context": "",
                "expected_answer_type": "factual"
            }

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        直接执行智能搜索（支持参数化调用）
        """
        try:
            if not self.enabled or not self.search_engine:
                return ToolResult.error_result(
                    "智能Web搜索工具未启用或初始化失败",
                    tool_name=self.name
                )

            # 获取参数
            query = parameters.get("query", "").strip()
            limit = int(parameters.get("limit", 8))

            if not query:
                return ToolResult.error_result(
                    "缺少搜索查询参数",
                    tool_name=self.name
                )

            # 创建模拟的解析结果
            parsed_query = {
                "search_keywords": query,
                "search_intent": "general_query",
                "question_type": "other",
                "key_entities": [],
                "time_context": "",
                "expected_answer_type": "factual"
            }

            # 执行搜索
            start_time = time.time()
            search_results = await self._perform_intelligent_search(parsed_query, limit)
            response_time = f"{time.time() - start_time:.1f}s"

            # 构建响应
            if search_results:
                results_data = [result.to_dict() for result in search_results]
                return ToolResult.success_result(
                    json.dumps({
                        "query": query,
                        "total_results": len(search_results),
                        "response_time": response_time,
                        "results": results_data
                    }, ensure_ascii=False, indent=2),
                    tool_name=self.name,
                    metadata={
                        "query": query,
                        "total_results": len(search_results),
                        "response_time": response_time
                    }
                )
            else:
                return ToolResult.success_result(
                    f"未找到相关信息: {query}",
                    tool_name=self.name,
                    metadata={
                        "query": query,
                        "total_results": 0,
                        "response_time": response_time
                    }
                )

        except Exception as e:
            return ToolResult.error_result(
                f"智能搜索执行失败: {str(e)}",
                tool_name=self.name
            )

    
    async def _perform_intelligent_search(self, parsed_query: Dict[str, Any], limit: int = 8) -> List[SearchResult]:
        """
        执行智能搜索
        """
        try:
            search_keywords = parsed_query["search_keywords"]
            search_intent = parsed_query.get("search_intent", "general_query")

            # 根据搜索意图优化查询
            optimized_query = self._optimize_search_query(search_keywords, search_intent)

            self.logger.info(f"Start intelligent search: {optimized_query} (intent: {search_intent})")

            # 执行搜索
            async with self.search_engine as engine:
                results = await engine.search(optimized_query, limit)

            # 根据搜索意图对结果进行排序和过滤
            filtered_results = self._filter_and_rank_results(results, parsed_query)

            return filtered_results

        except Exception as e:
            self.logger.error(f"Intelligent search execution failed: {str(e)}")
            raise WebSearchError(f"Intelligent search execution failed: {str(e)}")

    def _optimize_search_query(self, keywords: str, intent: str) -> str:
        """
        根据搜索意图优化查询关键词
        """
        base_query = keywords.strip()

        # 根据搜索意图添加修饰词
        intent_modifiers = {
            "latest_info": "最新",  # 查找最新信息
            "fact_checking": "事实",  # 事实核查
            "explanation": "解释",  # 解释说明
            "comparison": "对比",  # 比较分析
            "general_query": ""  # 一般查询不需要修饰
        }

        modifier = intent_modifiers.get(intent, "")
        if modifier and modifier not in base_query:
            optimized_query = f"{base_query} {modifier}"
        else:
            optimized_query = base_query

        return optimized_query

    def _filter_and_rank_results(self, results: List[SearchResult], parsed_query: Dict[str, Any]) -> List[SearchResult]:
        """
        根据查询意图过滤和排序搜索结果
        """
        if not results:
            return results

        search_intent = parsed_query.get("search_intent", "general_query")
        key_entities = parsed_query.get("key_entities", [])

        # 为每个结果计算相关性分数
        scored_results = []
        for result in results:
            score = self._calculate_result_relevance(result, parsed_query)
            scored_results.append((score, result))

        # 按相关性分数排序
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # 返回排序后的结果（只保留结果对象）
        return [result for score, result in scored_results]

    def _calculate_result_relevance(self, result: SearchResult, parsed_query: Dict[str, Any]) -> float:
        """
        计算搜索结果与查询的相关性分数
        """
        score = 0.0
        search_keywords = parsed_query.get("search_keywords", "").lower()
        key_entities = parsed_query.get("key_entities", [])
        search_intent = parsed_query.get("search_intent", "general_query")

        # 文本内容
        combined_text = (result.title + " " + result.description).lower()

        # 1. 关键词匹配分数
        if search_keywords:
            if search_keywords in combined_text:
                score += 3.0
            # 关键词分词匹配
            for word in search_keywords.split():
                if word in combined_text:
                    score += 1.0

        # 2. 关键实体匹配分数
        for entity in key_entities:
            if entity.lower() in combined_text:
                score += 2.0

        # 3. 标题匹配加权
        title_lower = result.title.lower()
        if search_keywords in title_lower:
            score += 2.0
        for entity in key_entities:
            if entity.lower() in title_lower:
                score += 1.5

        # 4. 根据搜索意图调整分数
        if search_intent == "latest_info":
            # 最新信息偏好新闻、官方网站
            news_indicators = ["新闻", "最新", "发布", "官方", "公告", "报道"]
            for indicator in news_indicators:
                if indicator in combined_text:
                    score += 1.0

        elif search_intent == "explanation":
            # 解释说明偏好教程、指南类内容
            tutorial_indicators = ["教程", "指南", "解释", "说明", "如何", "方法"]
            for indicator in tutorial_indicators:
                if indicator in combined_text:
                    score += 1.0

        elif search_intent == "comparison":
            # 比较分析偏好评测、对比类内容
            comparison_indicators = ["对比", "评测", "比较", "哪个", "选择"]
            for indicator in comparison_indicators:
                if indicator in combined_text:
                    score += 1.0

        return score

    async def _generate_enhanced_answer(self, user_message: str, parsed_query: Dict[str, Any],
                                      search_results: List[SearchResult], generate_response_func: Callable) -> str:
        """
        使用LLM基于搜索结果生成增强回答
        """
        # 准备搜索结果的摘要
        results_summary = self._prepare_search_results_summary(search_results)

        # 构建生成提示
        generation_prompt = f"""你是一个智能助手，基于网络搜索结果为用户提供准确、有用的回答。

原始问题: {user_message}

搜索意图分析:
- 关键词: {parsed_query.get('search_keywords', '')}
- 搜索意图: {parsed_query.get('search_intent', '')}
- 问题类型: {parsed_query.get('question_type', '')}
- 关键实体: {', '.join(parsed_query.get('key_entities', []))}
- 期望答案类型: {parsed_query.get('expected_answer_type', '')}

搜索结果摘要:
{results_summary}

请基于以上搜索结果，为用户提供一个全面、准确、有条理的回答。要求：

1. **准确性**: 基于搜索结果提供信息，不要编造内容
2. **完整性**: 充分回答用户的问题，涵盖相关要点
3. **条理性**: 使用清晰的逻辑结构，适当使用标题和列表
4. **实用性**: 提供用户真正需要的信息
5. **引用来源**: 在适当的地方提及信息来源
6. **客观性**: 如果有不同观点，请平衡呈现

回答格式：
- 开头直接回答核心问题
- 中间详细阐述相关信息
- 结尾提供总结或建议
- 适当引用搜索结果中的来源

请开始回答："""

        try:
            enhanced_answer = await generate_response_func(generation_prompt)
            return enhanced_answer
        except Exception as e:
            self.logger.error(f"Failed to generate enhanced answer: {str(e)}")
            # 回退到简单的结果摘要
            return self._fallback_response(user_message, search_results)

    def _prepare_search_results_summary(self, results: List[SearchResult]) -> str:
        """
        准备搜索结果的摘要文本
        """
        if not results:
            return "未找到相关搜索结果。"

        summary_lines = []
        for i, result in enumerate(results, 1):
            summary_lines.append(f"{i}. **{result.title}**")
            summary_lines.append(f"   来源: {result.source}")
            summary_lines.append(f"   链接: {result.url}")
            if result.description:
                # 限制描述长度
                desc = result.description[:200] + "..." if len(result.description) > 200 else result.description
                summary_lines.append(f"   摘要: {desc}")
            summary_lines.append("")

        return "\n".join(summary_lines)

    def _fallback_response(self, user_message: str, search_results: List[SearchResult]) -> str:
        """
        回退响应（当LLM生成失败时）
        """
        if not search_results:
            return f"抱歉，我无法找到关于「{user_message}」的相关信息。"

        response_lines = [
            f"关于「{user_message}」，我找到了以下相关信息：",
            ""
        ]

        for i, result in enumerate(search_results[:5], 1):  # 最多显示5个结果
            response_lines.append(f"{i}. {result.title}")
            if result.description:
                desc = result.description[:150] + "..." if len(result.description) > 150 else result.description
                response_lines.append(f"   {desc}")
            response_lines.append(f"   来源: {result.source}")
            response_lines.append("")

        response_lines.extend([
            "---",
            "如需更详细的信息，请访问上述链接。"
        ])

        return "\n".join(response_lines)

    
    async def cleanup(self):
        """清理资源"""
        if self.search_engine:
            await self.search_engine.close()


def get_web_search_tool() -> WebSearchTool:
    """获取Web搜索工具实例"""
    return WebSearchTool()