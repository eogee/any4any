import logging
from typing import Optional, Callable, Any

from .strategies import (
    VoiceKnowledgeStrategy,
    NL2SQLStrategy,
    GeneralToolsStrategy,
    KnowledgeRetrievalStrategy
)

logger = logging.getLogger(__name__)

class ToolProcessor:
    """工具处理器协调器"""

    def __init__(self, tools_enabled=True):
        self._tools_enabled = tools_enabled
        self._strategies = self._initialize_strategies()

    def _initialize_strategies(self):
        """初始化所有处理策略"""
        return [
            VoiceKnowledgeStrategy(self._tools_enabled),
            NL2SQLStrategy(self._tools_enabled),
            GeneralToolsStrategy(self._tools_enabled),
            KnowledgeRetrievalStrategy()
        ]

    async def process_with_tools(
        self,
        user_message: str,
        generate_response_func: Callable,
        conversation_manager=None,
        user_id: str = None,
        platform: str = None
    ) -> str:
        """使用工具处理用户消息 - 协调各个策略"""
        if not self._tools_enabled:
            return await self._fallback_to_kb(user_message, generate_response_func)

        try:
            # 按优先级尝试各个策略
            for strategy in self._strategies:
                if await strategy.can_handle(user_message):
                    result = await strategy.process(
                        user_message, generate_response_func,
                        conversation_manager, user_id, platform
                    )
                    if result:
                        return result

            # 如果所有策略都无法处理，回退到知识库
            return await self._fallback_to_kb(user_message, generate_response_func)

        except Exception as e:
            logger.error(f"Tool processing error: {e}")
            return await self._fallback_to_kb(user_message, generate_response_func)

    async def _fallback_to_kb(self, user_message: str, generate_response_func: Callable) -> str:
        """回退到知识库处理"""
        try:
            kb_strategy = KnowledgeRetrievalStrategy()
            if await kb_strategy.can_handle(user_message):
                result = await kb_strategy.process(user_message, generate_response_func)
                return result if result else await generate_response_func(user_message)
            else:
                return await generate_response_func(user_message)
        except Exception as e:
            logger.error(f"Knowledge base processing failed: {e}")
            return await generate_response_func(user_message)

    def is_tool_supported(self) -> bool:
        """检查是否支持工具功能"""
        return self._tools_enabled