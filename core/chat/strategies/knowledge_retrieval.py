"""
知识库检索策略
"""
import logging
from typing import Optional, Callable, Any

from config import Config
from .base import ProcessingStrategy

logger = logging.getLogger(__name__)

class KnowledgeRetrievalStrategy(ProcessingStrategy):
    """知识库检索策略"""

    def __init__(self):
        self._kb_manager = None

    @property
    def kb_manager(self):
        if self._kb_manager is None:
            from core.chat.llm import get_kb_manager
            self._kb_manager = get_kb_manager()
        return self._kb_manager

    async def can_handle(self, user_message: str) -> bool:
        return Config.KNOWLEDGE_BASE_ENABLED

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        try:
            if not Config.KNOWLEDGE_BASE_ENABLED:
                return None

            logger.info(f"Knowledge base retrieval for: {user_message}")
            retrieval_result = await self.kb_manager.retrieve_documents(user_message)

            if retrieval_result and retrieval_result.get('success') and retrieval_result.get('has_results'):
                documents = retrieval_result.get('documents', [])
                from core.chat.llm import format_knowledge_content
                kb_content = format_knowledge_content(documents, "retrieval strategy")

                enhanced_prompt = f"{user_message}\n{kb_content}\n\n请基于以上资料回答问题。"
                return await generate_response_func(enhanced_prompt)
            else:
                logger.info(f"No knowledge base results for: {user_message}")
                return None

        except Exception as e:
            logger.error(f"Knowledge base retrieval failed: {e}")
            return None