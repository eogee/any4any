"""
NL2SQL处理策略
"""
import logging
from typing import Optional, Callable, Any

from .base import ProcessingStrategy

logger = logging.getLogger(__name__)

class NL2SQLStrategy(ProcessingStrategy):
    """NL2SQL处理策略"""

    def __init__(self, tools_enabled=True):
        self._tools_enabled = tools_enabled
        self._nl2sql_workflow = None

    @property
    def nl2sql_workflow(self):
        if self._nl2sql_workflow is None and self._tools_enabled:
            try:
                from core.tools.nl2sql.workflow import get_nl2sql_workflow
                self._nl2sql_workflow = get_nl2sql_workflow()
            except Exception as e:
                logger.error(f"NL2SQL workflow init error: {e}")
        return self._nl2sql_workflow

    async def can_handle(self, user_message: str) -> bool:
        if not user_message or not user_message.strip():
            return False

        try:
            from core.chat.tool_manager import get_tool_manager
            tool_manager = get_tool_manager()
            return tool_manager.is_sql_question(user_message) if tool_manager else False
        except Exception:
            return False

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        try:
            if not self.nl2sql_workflow:
                logger.warning("NL2SQL workflow not available")
                return None

            workflow_result = await self.nl2sql_workflow.process_sql_question(
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
                    logger.info(f"NL2SQL: {error_msg}, falling back to normal LLM response")
                else:
                    logger.warning(f"NL2SQL workflow failed: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"NL2SQL processing failed: {e}")
            return None