"""
语音知识库处理策略
"""
import logging
from typing import Optional, Callable, Any

from config import Config
from .base import ProcessingStrategy

logger = logging.getLogger(__name__)

class VoiceKnowledgeStrategy(ProcessingStrategy):
    """语音知识库处理策略"""

    def __init__(self, tools_enabled=True):
        self._tools_enabled = tools_enabled
        self._voice_workflow = None

    @property
    def voice_workflow(self):
        if self._voice_workflow is None and self._tools_enabled:
            try:
                from core.tools.voice_kb.voice_workflow import get_voice_workflow
                self._voice_workflow = get_voice_workflow()
            except Exception as e:
                logger.error(f"Voice workflow init error: {e}")
        return self._voice_workflow

    async def can_handle(self, user_message: str) -> bool:
        if not user_message or not user_message.strip():
            return False

        try:
            from core.chat.tool_manager import get_tool_manager
            tool_manager = get_tool_manager()
            return tool_manager.is_voice_kb_question(user_message) if tool_manager else False
        except Exception:
            return False

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        try:
            if not Config.ANY4DH_VOICE_KB_ENABLED or not self.voice_workflow:
                return None

            result = await self.voice_workflow.process_voice_query(user_message)

            if result["success"] and result["should_use_voice"]:
                voice_info = result["voice_info"]
                if voice_info:
                    return f"[VOICE_KB_RESPONSE:{voice_info['audio_file']}:{voice_info['response_text']}]"
                else:
                    logger.warning("Voice info is empty, falling back to text")
                    return None
            else:
                logger.info(f"Voice KB not suitable: confidence={result.get('confidence', 0):.3f}")
                return None

        except Exception as e:
            logger.error(f"Voice KB processing failed: {e}")
            return None