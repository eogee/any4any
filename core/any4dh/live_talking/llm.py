"""
LLM能力调用
源自于open-webSearch项目(https://github.com/lipku/LiveTalking)，针对any4any进行适当调整优化
"""

import time
import os
import asyncio
from .basereal import BaseReal
import logging

logger = logging.getLogger(__name__)

async def llm_response_async(message: str, any4dh_real: BaseReal):
    start = time.perf_counter()

    try:
        from config import Config

        if getattr(Config, 'ANY4DH_USE_UNIFIED_INTERFACE', True):
            from core.chat.unified_interface import UnifiedLLMInterface

            result = ""
            first = True

            async for chunk in UnifiedLLMInterface.generate_response_stream(
                content=message,
                sender="any4dh_user",
                user_nick="数字人用户",
                platform="any4dh",
                generation_id=f"any4dh_live_{int(time.time())}"
            ):
                if first:
                    end = time.perf_counter()
                    logger.info(f"llm Time to first chunk: {end-start}s")
                    first = False

                if chunk and chunk.strip():
                    msg = chunk
                    lastpos = 0

                    for i, char in enumerate(msg):
                        if char in ",.!;:，。！？：；":
                            result = result + msg[lastpos:i+1]
                            lastpos = i+1
                            if len(result) > 10:
                                logger.info(result)
                                any4dh_real.put_msg_txt(result)
                                result = ""

                    result = result + msg[lastpos:]

            if result:
                logger.info(result)
                any4dh_real.put_msg_txt(result)
        else:
            await _llm_response_legacy(message, any4dh_real)

    except Exception as e:
        logger.error(f"LLM response processing failed: {e}")
        any4dh_real.put_msg_txt("抱歉，我现在无法回答这个问题。")

    end = time.perf_counter()
    logger.info(f"llm Time to complete: {end-start}s")

def llm_response(message, any4dh_real: BaseReal):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(llm_response_async(message, any4dh_real))

async def _llm_response_legacy(message: str, any4dh_real: BaseReal):
    start = time.perf_counter()
    from openai import OpenAI

    client = OpenAI(
        api_key="EMPTY",
        base_url="http://localhost:8888/v1",
    )
    end = time.perf_counter()
    logger.info(f"llm Time init: {end-start}s")

    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=[{'role': 'system', 'content': 'You are a helpful assistant.'},
                  {'role': 'user', 'content': message}],
        stream=True,
        stream_options={"include_usage": True}
    )

    result = ""
    first = True
    for chunk in completion:
        if len(chunk.choices) > 0:
            if first:
                end = time.perf_counter()
                logger.info(f"llm Time to first chunk: {end-start}s")
                first = False
            msg = chunk.choices[0].delta.content
            if msg:
                lastpos = 0
                for i, char in enumerate(msg):
                    if char in ",.!;:，。！？：；":
                        result = result + msg[lastpos:i+1]
                        lastpos = i+1
                        if len(result) > 10:
                            logger.info(result)
                            any4dh_real.put_msg_txt(result)
                            result = ""
                result = result + msg[lastpos:]

    end = time.perf_counter()
    logger.info(f"llm Time to last chunk: {end-start}s")
    if result:
        any4dh_real.put_msg_txt(result)    