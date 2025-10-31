"""
流式TTS处理工具模块
提供文本断句、流式TTS等功能
"""

import re
import asyncio
import logging
import time
import os
from typing import List, AsyncGenerator, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

def split_text_by_punctuation(text: str) -> List[str]:
    """
    根据标点符号智能断句

    Args:
        text: 输入文本

    Returns:
        断句后的文本列表
    """
    if not text or not text.strip():
        return []

    # 预处理：过滤特殊字符，确保文本干净
    try:
        from core.tts.filter import filter_special_chars
        text = filter_special_chars(text)
    except ImportError:
        pass  # 如果导入失败，继续处理原文本

    sentence_endings = r'[。！？.!?；;]'
    sentences = []
    current_sentence = ""

    for char in text:
        current_sentence += char

        if re.match(sentence_endings, char):
            sentence = current_sentence.strip()
            if sentence:
                sentences.append(sentence)
            current_sentence = ""

    if current_sentence.strip():
        sentences.append(current_sentence.strip())

    # 智能合并短句，确保句子不会太碎片化
    from config import Config
    filtered_sentences = []
    min_sentence_chars = Config.INDEX_TTS_STREAMING_MIN_SENTENCE_CHARS

    i = 0
    while i < len(sentences):
        sentence = sentences[i].strip()
        if len(sentence) < min_sentence_chars and i + 1 < len(sentences):
            next_sentence = sentences[i + 1].strip()
            merged_sentence = sentence + next_sentence
            if len(merged_sentence) <= min_sentence_chars * 2:
                filtered_sentences.append(merged_sentence)
                i += 2
            else:
                if len(sentence) >= 2:
                    filtered_sentences.append(sentence)
                i += 1
        else:
            if len(sentence) >= 2:
                filtered_sentences.append(sentence)
            i += 1

    return filtered_sentences

# 全局TTS引擎实例
_tts_engine = None

async def synthesize_speech_segment(text: str, sessionid: str, any4dh_reals: Dict) -> Dict[str, Any]:
    """
    为单个文本段合成语音并同步到数字人

    Args:
        text: 文本段
        sessionid: 会话ID
        any4dh_reals: 数字人实例字典

    Returns:
        音频段信息字典
    """
    global _tts_engine
    try:
        from core.tts.index_tts_engine import IndexTTSEngine
        from config import Config
        from core.tts.filter import filter_special_chars

        # 过滤特殊字符，确保TTS不会读出不合适的符号
        text = filter_special_chars(text)

        # 使用统一临时文件管理器
        from core.tts.temp_file_manager import create_temp_stream_file
        output_path = create_temp_stream_file()
        filename = os.path.basename(output_path)

        # 使用IndexTTS生成音频
        if Config.INDEX_TTS_MODEL_ENABLED:
            def tts_call():
                global _tts_engine
                # 只在第一次调用时创建TTS引擎实例
                if _tts_engine is None:
                    # 使用配置文件中的优化参数
                    optimized_config = {
                        'model_path': Config.INDEX_TTS_MODEL_DIR,
                        'device': Config.INDEX_TTS_DEVICE,
                        'min_request_interval': 0.001,

                        # 使用配置文件中的快速模式参数
                        'max_tokens': Config.INDEX_TTS_FAST_MAX_TOKENS,
                        'bucket_size': Config.INDEX_TTS_FAST_BATCH_SIZE,

                        # 流式模式专用优化
                        'fast_mode': Config.INDEX_TTS_FAST_ENABLED,
                        'timeout': Config.INDEX_TTS_TIMEOUT
                    }
                    _tts_engine = IndexTTSEngine.get_instance(optimized_config)

                return _tts_engine.generate_speech(
                    text=text,
                    output_path=str(output_path),
                    voice="default"
                )

            start_time = time.time()
            success = await asyncio.get_event_loop().run_in_executor(None, tts_call)
            generation_time = time.time() - start_time

            if success and os.path.exists(output_path):
                # 同步到数字人
                audio_synced = False
                if sessionid and sessionid in any4dh_reals:
                    try:
                        # 直接读取音频字节并传递，减少中间步骤
                        with open(output_path, 'rb') as f:
                            audio_bytes = f.read()

                        # 立即同步到数字人
                        any4dh_reals[sessionid].put_audio_file(audio_bytes)
                        audio_synced = True

                        sync_time = time.time() - start_time

                        # 清理临时文件
                        try:
                            os.remove(output_path)
                        except Exception as e:
                            logger.warning(f"Failed to cleanup temporary file: {e}")
                    except Exception as e:
                        logger.warning(f"Audio segment sync failed: {e}")

                # 临时文件访问URL（如果没有同步到数字人，才提供URL访问）
                audio_url = f"/temp_audio/{filename}" if not audio_synced else None

                return {
                    'success': True,
                    'text': text,
                    'audio_url': audio_url,
                    'audio_synced': audio_synced,
                    'generation_time': generation_time
                }
            else:
                logger.warning(f"TTS synthesis failed: {text[:20]}... (time: {generation_time:.2f}s)")
                # 清理失败的文件
                try:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                except Exception as e:
                    logger.warning(f"Error cleaning up failed file: {e}")

                return {
                    'success': False,
                    'text': text,
                    'error': 'TTS合成失败',
                    'generation_time': generation_time
                }
        else:
            logger.warning("IndexTTS not enabled, unable to synthesize speech")
            return {
                'success': False,
                'text': text,
                'error': 'IndexTTS not enabled'
            }

    except Exception as e:
        logger.error(f"Speech segment processing failed: {str(e)}")
        return {
            'success': False,
            'text': text,
            'error': str(e)
        }

async def process_llm_stream(text: str) -> AsyncGenerator[str, None]:
    """
    流式LLM处理

    Args:
        text: 输入文本

    Yields:
        LLM响应文本片段
    """
    try:
        from config import Config

        if getattr(Config, 'ANY4DH_USE_UNIFIED_INTERFACE', True):
            from core.chat.unified_interface import UnifiedLLMInterface

            async for chunk in UnifiedLLMInterface.generate_response_stream(
                content=text,
                sender="any4dh_user",
                user_nick="数字人用户",
                platform="any4dh",
                generation_id=f"any4dh_{int(time.time())}"
            ):
                if chunk and chunk.strip():
                    yield chunk
        else:
            from core.chat.llm import get_llm_service
            llm_service = get_llm_service()

            async for chunk in llm_service.generate_stream(text):
                if chunk and chunk.strip():
                    yield chunk

    except Exception as e:
        logger.error(f"LLM streaming processing failed: {str(e)}")
        yield "抱歉，我现在无法回答这个问题。"

class StreamingTTSProcessor:
    """流式TTS处理器"""

    def __init__(self, sessionid: str, any4dh_reals: Dict):
        self.sessionid = sessionid
        self.any4dh_reals = any4dh_reals
        self.accumulated_text = ""
        self.processed_segments = 0
        self.semaphore = asyncio.Semaphore(6)

    async def process_streaming_response(self, user_input: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理流式响应

        Args:
            initial_text: ASR识别的初始文本

        Yields:
            处理结果字典
        """
        try:
            # 发送初始状态
            yield {
                'type': 'status',
                'message': '正在生成回复...',
                'recognized_text': user_input
            }

            # 流式处理LLM响应
            accumulated_text = ""

            async for chunk in process_llm_stream(user_input):
                accumulated_text += chunk

                # 检查是否有完整句子
                sentences = split_text_by_punctuation(accumulated_text)

                if len(sentences) > 1:
                    # 有完整句子，处理前面的句子
                    for sentence in sentences[:-1]:
                        try:
                            # 使用信号量控制并发
                            async with self.semaphore:
                                result = await synthesize_speech_segment(
                                    sentence,
                                    self.sessionid,
                                    self.any4dh_reals
                                )

                            yield {
                                'type': 'audio_segment',
                                'data': result,
                                'partial_text': accumulated_text,
                                'segment_index': self.processed_segments
                            }

                            self.processed_segments += 1

                            delay_time = 0.001
                            await asyncio.sleep(delay_time)

                        except Exception as e:
                            logger.error(f"Audio segment processing failed: {e}")
                            continue

                    # 保留最后的不完整句子
                    accumulated_text = sentences[-1] if sentences else accumulated_text

            # 处理最后的文本
            if accumulated_text.strip():
                try:
                    result = await synthesize_speech_segment(
                        accumulated_text,
                        self.sessionid,
                        self.any4dh_reals
                    )

                    yield {
                        'type': 'final_segment',
                        'data': result,
                        'complete_text': accumulated_text,
                        'segment_index': self.processed_segments,
                        'is_final': True
                    }

                except Exception as e:
                    logger.error(f"Final audio segment processing failed: {e}")

            # 发送完成状态
            yield {
                'type': 'completed',
                'message': '回复完成',
                'total_segments': self.processed_segments
            }

        except Exception as e:
            logger.error(f"Streaming processing failed: {str(e)}")
            yield {
                'type': 'error',
                'message': f'处理失败: {str(e)}'
            }