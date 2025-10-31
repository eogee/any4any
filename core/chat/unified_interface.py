import time
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

class UnifiedLLMInterface:

    @staticmethod
    async def generate_response_sync(
        content: str,
        sender: str = "user",
        user_nick: str = "用户",
        platform: str = "default",
        **kwargs
    ):
        try:
            from .conversation_manager import get_conversation_manager
            conversation_manager = get_conversation_manager()

            response, conversation_id = await conversation_manager.process_message(
                sender=sender,
                user_nick=user_nick,
                platform=platform,
                content=content,
                **kwargs
            )
            return response

        except Exception as e:
            logger.error(f"Unified LLM interface error: {e}")
            return f"抱歉，处理您的请求时出现错误: {str(e)}"

    @staticmethod
    async def generate_response_stream(
        content: str,
        sender: str = "user",
        user_nick: str = "用户",
        platform: str = "default",
        generation_id: Optional[str] = None,
        **kwargs
    ):
        try:
            from .conversation_manager import get_conversation_manager
            conversation_manager = get_conversation_manager()

            async for chunk in conversation_manager.process_message_stream(
                sender=sender,
                user_nick=user_nick,
                platform=platform,
                content=content,
                generation_id=generation_id or f"unified_{int(time.time())}",
                **kwargs
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Unified LLM interface error: {e}")
            yield f"[错误: {str(e)}]"

    @staticmethod
    async def generate_with_tools(
        content: str,
        sender: str = "user",
        user_nick: str = "用户",
        platform: str = "default",
        **kwargs
    ) -> str:
        return await UnifiedLLMInterface.generate_response_sync(
            content=content,
            sender=sender,
            user_nick=user_nick,
            platform=platform,
            **kwargs
        )