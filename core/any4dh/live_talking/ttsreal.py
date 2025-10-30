# TTS Real - Text-to-Speech Services Integration (Simplified)
from __future__ import annotations
import time
import numpy as np
import soundfile as sf
import resampy
import asyncio
import logging
from typing import Iterator
import queue
from io import BytesIO
from threading import Thread, Event
from enum import Enum
from typing import TYPE_CHECKING
import os

if TYPE_CHECKING:
    from basereal import BaseReal

logger = logging.getLogger(__name__)


class State(Enum):
    RUNNING = 0
    PAUSE = 1


class BaseTTS:
    def __init__(self, opt, parent: BaseReal):
        self.opt = opt
        self.parent = parent

        self.fps = opt.fps  # 20 ms per frame
        self.sample_rate = 16000
        self.chunk = self.sample_rate // self.fps  # 320 samples per chunk (20ms * 16000 / 1000)
        self.input_stream = BytesIO()

        self.msgqueue = queue.Queue()
        self.state = State.RUNNING

    def flush_talk(self):
        self.msgqueue.queue.clear()
        self.state = State.PAUSE

    def put_msg_txt(self, msg: str, datainfo: dict = {}):
        if len(msg) > 0:
            self.msgqueue.put((msg, datainfo))

    def render(self, quit_event):
        process_thread = Thread(target=self.process_tts, args=(quit_event,))
        process_thread.start()

    def process_tts(self, quit_event):
        while not quit_event.is_set():
            try:
                msg: tuple[str, dict] = self.msgqueue.get(block=True, timeout=1)
                self.state = State.RUNNING
            except queue.Empty:
                continue
            self.txt_to_audio(msg)
        logger.info('ttsreal thread stop')

    def txt_to_audio(self, msg: tuple[str, dict]):
        pass

class IndexTTS(BaseTTS):
    def txt_to_audio(self, msg: tuple[str, dict]):
        text, textevent = msg
        t = time.time()

        try:
            from core.tts.index_tts_engine import IndexTTSEngine
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                engine = IndexTTSEngine.get_instance({
                    'model_path': getattr(self.opt, 'index_tts_model_dir', '/mnt/c/models/IndexTTS-1.5'),
                    'device': getattr(self.opt, 'index_tts_device', 'cpu')
                })

                # IndexTTS只支持"default"声音，系统会自动转换为default.wav文件路径
                success = engine.generate_speech(text, tmp_file.name, "default")

                if success and os.path.exists(tmp_file.name):
                    stream, sample_rate = sf.read(tmp_file.name)
                    os.unlink(tmp_file.name)
                else:
                    logger.warning('IndexTTS generation failed, falling back to edge-tts')
                    return self._fallback_to_edge_tts(text, textevent)

        except Exception as e:
            logger.warning(f'IndexTTS error: {e}, falling back to edge-tts')
            return self._fallback_to_edge_tts(text, textevent)

        logger.info(f'Index tts time:{time.time() - t:.4f}s')
        self._process_audio_stream(stream, sample_rate, text, textevent)

    def _fallback_to_edge_tts(self, text, textevent):
        voicename = getattr(self.opt, 'REF_FILE', 'zh-CN-YunxiaNeural')
        t = time.time()

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voicename)

            # 直接生成到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                asyncio.new_event_loop().run_until_complete(communicate.save(tmp_file.name))

                if os.path.exists(tmp_file.name):
                    stream, sample_rate = sf.read(tmp_file.name)
                    os.unlink(tmp_file.name)
                    self._process_audio_stream(stream, sample_rate, text, textevent)
                else:
                    logger.error('edge-tts fallback failed!')

        except Exception as e:
            logger.error(f'edge-tts fallback error: {e}')

    def _process_audio_stream(self, stream, sample_rate, text, textevent):
        if sample_rate != self.sample_rate and stream.shape[0] > 0:
            stream = resampy.resample(x=stream, sr_orig=sample_rate, sr_new=self.sample_rate)

        streamlen = stream.shape[0]
        idx = 0
        while streamlen >= self.chunk and self.state == State.RUNNING:
            eventpoint = {}
            streamlen -= self.chunk
            if idx == 0:
                eventpoint = {'status': 'start', 'text': text}
                eventpoint.update(**textevent)
            elif streamlen < self.chunk:
                eventpoint = {'status': 'end', 'text': text}
                eventpoint.update(**textevent)
            self.parent.put_audio_frame(stream[idx:idx + self.chunk], eventpoint)
            idx += self.chunk

class EdgeTTS(BaseTTS):
    def txt_to_audio(self, msg: tuple[str, dict]):
        voicename = getattr(self.opt, 'REF_FILE', 'zh-CN-YunxiaNeural')
        text, textevent = msg
        t = time.time()
        asyncio.new_event_loop().run_until_complete(self.__main(voicename, text))
        logger.info(f'-------edge tts time:{time.time() - t:.4f}s')
        if self.input_stream.getbuffer().nbytes <= 0:
            logger.error('edgetts error!')
            return

        self.input_stream.seek(0)
        stream = self.__create_bytes_stream(self.input_stream)
        streamlen = stream.shape[0]
        idx = 0
        while streamlen >= self.chunk and self.state == State.RUNNING:
            eventpoint = {}
            streamlen -= self.chunk
            if idx == 0:
                eventpoint = {'status': 'start', 'text': text}
                eventpoint.update(**textevent)
            elif streamlen < self.chunk:
                eventpoint = {'status': 'end', 'text': text}
                eventpoint.update(**textevent)
            self.parent.put_audio_frame(stream[idx:idx + self.chunk], eventpoint)
            idx += self.chunk
        self.input_stream.seek(0)
        self.input_stream.truncate()

    def __create_bytes_stream(self, byte_stream):
        # byte_stream=BytesIO(buffer)
        stream, sample_rate = sf.read(byte_stream)  # [T*sample_rate,] float64
        logger.info(f'[INFO]tts audio stream {sample_rate}: {stream.shape}')
        stream = stream.astype(np.float32)

        if stream.ndim > 1:
            logger.info(f'[WARN] audio has {stream.shape[1]} channels, only use the first.')
            stream = stream[:, 0]

        if sample_rate != self.sample_rate and stream.shape[0] > 0:
            stream = resampy.resample(x=stream, sr_orig=sample_rate, sr_new=self.sample_rate)

        return stream

    async def __main(self, voicename: str, text: str):
        max_retries = 3
        retry_delay = 1  # seconds

        # 过滤特殊字符，确保TTS不会读出不合适的符号
        try:
            from utils.content_handle.filter import filter_special_chars
            text = filter_special_chars(text)
        except ImportError:
            pass  # 如果导入失败，继续处理原文本

        for attempt in range(max_retries):
            try:
                # 尝试不同的 voice 配置来提高成功率
                voice_options = [
                    voicename,
                    "zh-CN-XiaoxiaoNeural",
                    "zh-CN-YunxiNeural",
                    "zh-CN-YunjianNeural",
                    "zh-CN-XiaoyiNeural"
                ]

                current_voice = voice_options[attempt % len(voice_options)]

                communicate = edge_tts.Communicate(text, current_voice)

                first = True
                async for chunk in communicate.stream():
                    if first:
                        first = False
                    if chunk["type"] == "audio" and self.state == State.RUNNING:
                        self.input_stream.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        pass

                # 如果成功完成，跳出重试循环
                if self.input_stream.getbuffer().nbytes > 0:
                    break

            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.exception('EdgeTTS failed after all retries')
                    # 可以选择抛出异常或者返回空结果
                    # raise e