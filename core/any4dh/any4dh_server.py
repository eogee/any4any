# any4dh FastAPI 服务器
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import base64
import json
import re
import numpy as np
from threading import Thread, Event
import torch.multiprocessing as mp

import asyncio
import torch
from typing import Dict, Optional
import logging
logger = logging.getLogger(__name__)
import gc
import os

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceServer, RTCConfiguration
from aiortc.rtcrtpsender import RTCRtpSender
from .live_talking.webrtc import HumanPlayer
from .live_talking.basereal import BaseReal
from .live_talking.llm import llm_response

import argparse
import random
import shutil
import time
import tempfile
from pathlib import Path

# 全局变量
any4dh_reals: Dict[int, BaseReal] = {}
pcs = set()
opt = None
model = None
avatar = None

def randN(N) -> int:
    """生成指定位数的随机数"""
    min_val = pow(10, N - 1)
    max_val = pow(10, N)
    return random.randint(min_val, max_val - 1)

def build_any4dh_real(sessionid: int) -> BaseReal:
    opt.sessionid = sessionid
    from .live_talking.lipreal import LipReal
    any4dh_real = LipReal(opt, model, avatar)
    return any4dh_real

# 请求数据模型
class OfferRequest(BaseModel):
    sdp: str
    type: str

class HumanRequest(BaseModel):
    sessionid: int
    type: str
    text: Optional[str] = None
    interrupt: Optional[bool] = False

class InterruptRequest(BaseModel):
    sessionid: int

class SetAudioTypeRequest(BaseModel):
    sessionid: int
    audiotype: int
    reinit: bool

class RecordRequest(BaseModel):
    sessionid: int
    type: str  # 开始录音或结束录音

class IsSpeakingRequest(BaseModel):
    sessionid: int

class PlayAudioRequest(BaseModel):
    sessionid: int
    audio_url: str
    text: Optional[str] = None
    segment_index: Optional[int] = None

def register_any4dh_routes(app: FastAPI):
    """注册 any4dh 数字人相关路由"""

    @app.post("/any4dh/offer")
    async def offer(request: OfferRequest):
        """处理 WebRTC offer 请求"""
        params = request.model_dump()

        # 验证 offer 数据
        if not params.get("sdp") or not params.get("type"):
            logger.error(f"Invalid offer data: sdp={bool(params.get('sdp'))}, type={params.get('type')}")
            raise HTTPException(status_code=400, detail="Invalid offer data: missing sdp or type")

        sdp_content = params["sdp"]

        # 验证 SDP 有效性
        if len(sdp_content) < 100:
            logger.error(f"SDP content too short: {sdp_content}")
            raise HTTPException(status_code=400, detail=f"Invalid SDP: content too short ({len(sdp_content)} chars)")

        if not sdp_content.startswith('v=0'):
            logger.error(f"Invalid SDP format - doesn't start with v=0: {sdp_content[:100]}...")
            raise HTTPException(status_code=400, detail="Invalid SDP: doesn't start with 'v=0'")

        if "m=" not in sdp_content:
            logger.error(f"Invalid SDP format - no media description found: {sdp_content[:100]}...")
            raise HTTPException(status_code=400, detail="Invalid SDP: no media description (m=) found")

        try:
            offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        except Exception as e:
            logger.error(f"Failed to create RTCSessionDescription: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid offer format: {str(e)}")

        sessionid = randN(6)
        any4dh_reals[sessionid] = None
        logger.info('sessionid=%d, session num=%d', sessionid, len(any4dh_reals))

        any4dh_real = await asyncio.get_event_loop().run_in_executor(None, build_any4dh_real, sessionid)
        any4dh_reals[sessionid] = any4dh_real

        ice_server = RTCIceServer(urls='stun:stun.miwifi.com:3478')

        pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[ice_server]))
        pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info("Connection state is %s" % pc.connectionState)
            if pc.connectionState == "failed":
                await pc.close()
                pcs.discard(pc)
                del any4dh_reals[sessionid]
            if pc.connectionState == "closed":
                pcs.discard(pc)
                del any4dh_reals[sessionid]

        player = HumanPlayer(any4dh_reals[sessionid])
        audio_sender = pc.addTrack(player.audio)
        video_sender = pc.addTrack(player.video)

        # 设置视频编解码器偏好
        capabilities = RTCRtpSender.getCapabilities("video")
        if capabilities and capabilities.codecs:
            h264_codecs = [codec for codec in capabilities.codecs if codec.name == "H264"]
            vp8_codecs = [codec for codec in capabilities.codecs if codec.name == "VP8"]
            rtx_codecs = [codec for codec in capabilities.codecs if codec.name == "rtx"]

            preferences = h264_codecs + vp8_codecs + rtx_codecs

            if not preferences:
                preferences = list(capabilities.codecs)
                logger.warning("No preferred codecs found, using all available codecs")

            if len(pc.getTransceivers()) > 1:
                transceiver = pc.getTransceivers()[1]
                try:
                    transceiver.setCodecPreferences(preferences)
                except Exception as e:
                    logger.warning(f"Failed to set codec preferences: {e}, using default codecs")

        await pc.setRemoteDescription(offer)
        await asyncio.sleep(0.1)

        try:
            answer = await pc.createAnswer()

            if answer is None:
                raise ValueError("Created answer is None")

            if pc.connectionState == "closed":
                raise ValueError("PeerConnection is closed")

            await pc.setLocalDescription(answer)
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to set local description: {e}")
            logger.error(f"Offer details - type: {offer.type}, sdp length: {len(offer.sdp) if offer.sdp else 'None'}")
            logger.error(f"Connection state: {pc.connectionState}")
            logger.error(f"ICE connection state: {pc.iceConnectionState}")
            logger.error(f"ICE gathering state: {pc.iceGatheringState}")

            try:
                transceivers = pc.getTransceivers()
                logger.error(f"Number of transceivers: {len(transceivers)}")
                for i, transceiver in enumerate(transceivers):
                    sender_info = "None" if transceiver.sender is None else f"track={transceiver.sender.track is not None}"
                    receiver_info = "None" if transceiver.receiver is None else f"track={transceiver.receiver.track is not None}"
                    logger.error(f"Transceiver {i}: {transceiver.direction}, sender: {sender_info}, receiver: {receiver_info}")
            except Exception as te:
                logger.error(f"Failed to get transceiver info: {te}")

            raise HTTPException(status_code=500, detail=f"WebRTC setup failed: {str(e)}")

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "sessionid": sessionid
        }

    @app.post("/any4dh/human")
    async def human(request: HumanRequest):
        """处理人机交互请求"""
        try:
            sessionid = request.sessionid

            if sessionid not in any4dh_reals:
                raise HTTPException(status_code=404, detail="Session not found")

            if request.interrupt:
                any4dh_reals[sessionid].flush_talk()

            if request.type == 'echo':
                any4dh_reals[sessionid].put_msg_txt(request.text)
            elif request.type == 'chat':
                asyncio.get_event_loop().run_in_executor(None, llm_response, request.text, any4dh_reals[sessionid])

            return {"code": 0, "msg": "ok"}
        except Exception as e:
            logger.exception('exception:')
            return {"code": -1, "msg": str(e)}

    @app.post("/any4dh/interrupt_talk")
    async def interrupt_talk(request: InterruptRequest):
        """中断当前语音"""
        try:
            sessionid = request.sessionid

            if sessionid not in any4dh_reals:
                raise HTTPException(status_code=404, detail="Session not found")

            any4dh_reals[sessionid].flush_talk()
            return {"code": 0, "msg": "ok"}
        except Exception as e:
            logger.exception('exception:')
            return {"code": -1, "msg": str(e)}

    @app.post("/any4dh/humanaudio")
    async def humanaudio(
        sessionid: int = Form(...),
        file: UploadFile = File(...)
    ):
        """上传音频文件进行处理"""
        try:
            if sessionid not in any4dh_reals:
                raise HTTPException(status_code=404, detail="Session not found")

            filebytes = await file.read()
            any4dh_reals[sessionid].put_audio_file(filebytes)
            return {"code": 0, "msg": "ok"}
        except Exception as e:
            logger.exception('exception:')
            return {"code": -1, "msg": str(e)}

    
    @app.post("/any4dh/set_audiotype")
    async def set_audiotype(request: SetAudioTypeRequest):
        """设置会话音频类型"""
        try:
            sessionid = request.sessionid

            if sessionid not in any4dh_reals:
                raise HTTPException(status_code=404, detail="Session not found")

            any4dh_reals[sessionid].set_custom_state(request.audiotype, request.reinit)
            return {"code": 0, "msg": "ok"}
        except Exception as e:
            logger.exception('exception:')
            return {"code": -1, "msg": str(e)}

    @app.post("/any4dh/record")
    async def record(request: RecordRequest):
        """开始或停止录音"""
        try:
            sessionid = request.sessionid

            if sessionid not in any4dh_reals:
                raise HTTPException(status_code=404, detail="Session not found")

            if request.type == 'start_record':
                any4dh_reals[sessionid].start_recording()
            elif request.type == 'end_record':
                any4dh_reals[sessionid].stop_recording()
            return {"code": 0, "msg": "ok"}
        except Exception as e:
            logger.exception('exception:')
            return {"code": -1, "msg": str(e)}

    @app.post("/any4dh/is_speaking")
    async def is_speaking(request: IsSpeakingRequest):
        """检查数字人是否正在说话"""
        sessionid = request.sessionid

        if sessionid not in any4dh_reals:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"code": 0, "data": any4dh_reals[sessionid].is_speaking()}

    @app.post("/any4dh/voice-chat")
    async def voice_chat(
        file: UploadFile = File(...),
        sessionid: Optional[str] = Form(None)
    ):
        """
        语音对话接口：录音 -> ASR -> LLM -> TTS
        """
        try:
            logger.info(f"收到语音对话请求: file={file.filename if file else 'None'}, sessionid={sessionid}")
            # 检查文件大小限制 (10MB)
            max_file_size = 10 * 1024 * 1024  # 10MB
            file_content = await file.read()

            if len(file_content) > max_file_size:
                return {
                    "success": False,
                    "error": "音频文件过大，请限制在10MB以内"
                }

            if len(file_content) == 0:
                return {
                    "success": False,
                    "error": "音频文件为空"
                }

            logger.info(f"收到语音对话请求，文件大小: {len(file_content)} bytes")

            # 1. ASR语音识别
            recognized_text = await transcribe_audio(file_content)

            if not recognized_text or not recognized_text.strip():
                return {
                    "success": False,
                    "error": "语音识别结果为空，请说话清晰一些"
                }

            logger.info(f"ASR识别结果: {recognized_text}")

            # 2. LLM对话处理
            response_text = await process_llm_chat(recognized_text)

            if not response_text or not response_text.strip():
                response_text = "抱歉，我现在无法回答这个问题。"

            logger.info(f"LLM响应结果: {response_text}")

            # 3. TTS语音合成
            audio_url = await synthesize_speech(response_text)

            logger.info(f"TTS合成完成: {audio_url}")

            # 4. 如果有活动的数字人会话，将音频传递给数字人进行嘴唇同步
            audio_synced = False
            if sessionid and sessionid in any4dh_reals:
                try:
                    # 读取生成的音频文件
                    audio_file_path = audio_url.replace('/static/', 'static/')
                    if os.path.exists(audio_file_path):
                        with open(audio_file_path, 'rb') as f:
                            audio_bytes = f.read()
                        any4dh_reals[sessionid].put_audio_file(audio_bytes)
                        audio_synced = True
                        logger.info(f"音频已同步到数字人session {sessionid}")
                except Exception as e:
                    logger.warning(f"音频同步到数字人失败: {e}")
            else:
                # 添加调试信息
                active_sessions = list(any4dh_reals.keys())
                logger.warning(f"无法同步音频: sessionid={sessionid}, 活动会话={active_sessions}")

                # 尝试使用最新的活动会话
                if active_sessions and len(active_sessions) > 0:
                    latest_session = active_sessions[-1]
                    try:
                        audio_file_path = audio_url.replace('/static/', 'static/')
                        if os.path.exists(audio_file_path):
                            with open(audio_file_path, 'rb') as f:
                                audio_bytes = f.read()
                            any4dh_reals[latest_session].put_audio_file(audio_bytes)
                            audio_synced = True
                            logger.info(f"音频已同步到最新的数字人session {latest_session}")
                    except Exception as e:
                        logger.warning(f"音频同步到最新数字人失败: {e}")

            # 5. 获取音频时长信息
            audio_duration = 0
            if audio_synced:
                try:
                    import librosa
                    audio_file_path = audio_url.replace('/static/', 'static/')
                    if os.path.exists(audio_file_path):
                        # 使用librosa获取音频时长
                        y, sr = librosa.load(audio_file_path)
                        audio_duration = int(librosa.get_duration(y=y, sr=sr) * 1000)  # 转换为毫秒
                except ImportError:
                    # 如果没有librosa，使用文件大小估算（假设平均比特率32kbps）
                    audio_file_path = audio_url.replace('/static/', 'static/')
                    if os.path.exists(audio_file_path):
                        file_size = os.path.getsize(audio_file_path)
                        audio_duration = (file_size * 8) // (32 * 1000) * 1000  # 估算毫秒
                except Exception as e:
                    logger.warning(f"获取音频时长失败: {e}")
                    audio_duration = 15000  # 默认15秒

            # 6. 返回完整结果 - 始终不返回前端音频URL，强制使用数字人播放
            return {
                "success": True,
                "recognized_text": recognized_text,
                "response_text": response_text,
                "audio_url": None,  # 始终不返回前端音频URL
                "audio_synced": audio_synced,
                "audio_file": audio_url.split('/')[-1] if audio_synced else None,  # 返回文件名用于状态显示
                "audio_duration": audio_duration,  # 音频时长（毫秒）
                "session_id": sessionid or "voice_chat_session",
                "timestamp": int(time.time())
            }

        except HTTPException as he:
            logger.error(f"HTTP异常: {he.status_code} - {he.detail}")
            return {
                "success": False,
                "error": f"HTTP错误 {he.status_code}: {he.detail}"
            }
        except Exception as e:
            logger.exception('语音对话处理异常:')
            return {
                "success": False,
                "error": f"语音处理失败: {str(e)}"
            }

    @app.post("/any4dh/voice-chat-stream")
    async def voice_chat_stream(
        file: UploadFile = File(...),
        sessionid: Optional[str] = Form(None)
    ):
        """
        流式语音对话接口：录音 -> ASR -> 流式LLM -> 分段TTS -> 数字人播放
        支持实时音频流输出，用户可以更快听到AI回复
        """
        try:
            # 检查文件大小限制 (10MB)
            max_file_size = 10 * 1024 * 1024  # 10MB
            file_content = await file.read()

            if len(file_content) > max_file_size:
                async def error_response():
                    yield f"data: {json.dumps({'type': 'error', 'message': '音频文件过大，请限制在10MB以内'})}\n\n"
                return StreamingResponse(error_response(), media_type="text/plain")

            if len(file_content) == 0:
                async def error_response():
                    yield f"data: {json.dumps({'type': 'error', 'message': '音频文件为空'})}\n\n"
                return StreamingResponse(error_response(), media_type="text/plain")

            logger.info(f"收到流式语音对话请求: file={file.filename if file else 'None'}, sessionid={sessionid}")
            logger.info(f"收到流式语音对话请求，文件大小: {len(file_content)} bytes")

            # 1. ASR语音识别
            recognized_text = await transcribe_audio(file_content)

            if not recognized_text or not recognized_text.strip():
                async def error_response():
                    yield f"data: {json.dumps({'type': 'error', 'message': '语音识别结果为空，请说话清晰一些'})}\n\n"
                return StreamingResponse(error_response(), media_type="text/plain")

            logger.info(f"ASR识别结果: {recognized_text}")

            # 2. 创建流式处理器
            from .streaming_utils import StreamingTTSProcessor
            processor = StreamingTTSProcessor(sessionid, any4dh_reals)

            async def generate_stream():
                try:
                    async for result in processor.process_streaming_response(recognized_text):
                        # 使用SSE格式发送数据
                        yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.error(f"流式处理异常: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'处理异常: {str(e)}'})}\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*"
                }
            )

        except HTTPException as he:
            logger.error(f"HTTP异常: {he.status_code} - {he.detail}")

            async def error_response():
                yield f"data: {json.dumps({'type': 'error', 'message': f'HTTP错误 {he.status_code}: {he.detail}'})}\n\n"
            return StreamingResponse(error_response(), media_type="text/plain")

        except Exception as e:
            logger.exception('流式语音对话处理异常:')

            async def error_response():
                yield f"data: {json.dumps({'type': 'error', 'message': f'语音处理失败: {str(e)}'})}\n\n"
            return StreamingResponse(error_response(), media_type="text/plain")

    @app.post("/any4dh/play-audio")
    async def play_audio(request: PlayAudioRequest):
        """
        播放音频段到数字人
        用于流式模式下的音频播放
        """
        try:
            sessionid = request.sessionid

            if sessionid not in any4dh_reals:
                logger.warning(f"Session {sessionid} not found for audio playback")
                return {"code": -1, "msg": "Session not found"}

            # 获取音频文件路径
            audio_url = request.audio_url
            if not audio_url:
                return {"code": -1, "msg": "Audio URL is required"}

            # 构建完整的音频文件路径
            if audio_url.startswith('/static/'):
                audio_path = audio_url[1:]  # 移除开头的 /
            else:
                audio_path = audio_url

            full_audio_path = os.path.join(os.getcwd(), audio_path)

            if not os.path.exists(full_audio_path):
                logger.error(f"Audio file not found: {full_audio_path}")
                return {"code": -1, "msg": f"Audio file not found: {audio_url}"}

            # 读取音频文件并传给数字人
            try:
                with open(full_audio_path, 'rb') as f:
                    audio_bytes = f.read()

                # 传递音频到数字人实例
                any4dh_reals[sessionid].put_audio_file(audio_bytes)

                logger.info(f"音频段已发送到数字人 sessionid={sessionid}, text={request.text[:20] if request.text else 'N/A'}...")
                return {"code": 0, "msg": "Audio playback started successfully"}

            except Exception as audio_error:
                logger.error(f"Failed to process audio file: {str(audio_error)}")
                return {"code": -1, "msg": f"Failed to process audio: {str(audio_error)}"}

        except Exception as e:
            logger.exception('Audio playback exception:')
            return {"code": -1, "msg": f"Audio playback failed: {str(e)}"}

# 语音对话辅助函数
async def transcribe_audio(file_content: bytes) -> str:
    """ASR语音识别"""
    try:
        import torchaudio
        from io import BytesIO
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
        from core.model_manager import ModelManager

        # 直接加载音频数据
        data, fs = torchaudio.load(BytesIO(file_content))
        data = data.mean(0)  # 转换为单声道

        # 获取ASR模型并进行推理
        m, kwargs = ModelManager.get_asr_model()
        res = m.inference(
            data_in=[data],
            language="auto",
            use_itn=False,
            ban_emo_unk=False,
            key=["voice_chat"],
            fs=fs,
            **kwargs,
        )

        if not res or not res[0]:
            logger.warning("ASR返回空结果")
            return ""

        # 处理识别结果
        raw_text = res[0][0]["text"]
        final_text = rich_transcription_postprocess(raw_text.replace("<|startoftranscript|>", "").replace("<|endofttranscript|>", ""))

        return final_text.strip()

    except Exception as e:
        logger.error(f"ASR处理失败: {str(e)}")
        return ""

async def process_llm_chat(text: str) -> str:
    """LLM对话处理"""
    try:
        # 调用LLM服务
        from core.chat.llm import get_llm_service

        def llm_call():
            llm_service = get_llm_service()
            # 使用同步方式调用异步方法
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(llm_service.generate_response(text))
                return result
            finally:
                loop.close()

        response = await asyncio.get_event_loop().run_in_executor(None, llm_call)
        return response if response else "抱歉，我现在无法回答这个问题。"

    except Exception as e:
        logger.error(f"LLM处理失败: {str(e)}")
        return "抱歉，我现在无法回答这个问题。"

async def synthesize_speech(text: str) -> str:
    """TTS语音合成"""
    try:
        from core.tts.speech import create_speech
        from core.tts.index_tts_engine import IndexTTSEngine
        from fastapi import Request
        from io import BytesIO
        import uuid
        from config import Config

        # 创建输出目录
        voice_dir = Path("static/voice")
        voice_dir.mkdir(exist_ok=True)

        # 生成唯一文件名
        filename = f"voice_output_{int(time.time() * 1000)}.mp3"
        output_path = voice_dir / filename

        # 首先尝试使用IndexTTS
        if Config.INDEX_TTS_MODEL_ENABLED:
            try:
                def tts_call():
                    index_tts_engine = IndexTTSEngine.get_instance({
                        'model_path': Config.INDEX_TTS_MODEL_DIR,
                        'device': Config.INDEX_TTS_DEVICE
                    })
                    return index_tts_engine.generate_speech(
                        text=text,
                        output_path=str(output_path),
                        voice="default"
                    )

                success = await asyncio.get_event_loop().run_in_executor(None, tts_call)

                if success and output_path.exists():
                    logger.info(f"IndexTTS语音合成成功: {filename}")
                    return f"/static/voice/{filename}"
                else:
                    logger.warning("IndexTTS合成失败，尝试使用edge-tts")

            except Exception as e:
                logger.warning(f"IndexTTS合成失败: {e}，尝试使用edge-tts")

        # 备选方案：使用edge-tts
        def edge_tts_call():
            import asyncio
            from edge_tts import Communicate

            # 创建新的事件循环来运行异步edge-tts
            loop = asyncio.new_event_loop()
            try:
                communicate = Communicate(text, Config.EDGE_DEFAULT_VOICE)
                loop.run_until_complete(communicate.save(str(output_path)))
                return True
            finally:
                loop.close()

        success = await asyncio.get_event_loop().run_in_executor(None, edge_tts_call)

        if success and output_path.exists():
            logger.info(f"edge-tts语音合成成功: {filename}")
            return f"/static/voice/{filename}"
        else:
            logger.error("TTS语音合成失败")
            raise Exception("TTS语音合成失败")

    except Exception as e:
        logger.error(f"TTS处理失败: {str(e)}")
        raise Exception(f"语音合成失败: {str(e)}")

# 全局初始化状态
_any4dh_initialized = False

def initialize_any4dh(config=None):
    """初始化 any4dh 数字人系统"""
    global opt, model, avatar, _any4dh_initialized

    if _any4dh_initialized:
        logger.info("any4dh already initialized, skipping")
        return opt, model, avatar

    if config is None:
        # 从环境变量或配置文件读取配置
        import sys
        # 获取项目根目录（any4any/）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from config import Config

        config = Config()

    # 创建配置对象
    class OptConfig:
        def __init__(self, cfg):
            self.fps = cfg.ANY4DH_FPS
            self.W = 450
            self.H = 450
            self.avatar_id = cfg.ANY4DH_AVATAR_ID
            self.batch_size = cfg.ANY4DH_BATCH_SIZE
            self.customvideo_config = ''
            self.tts = cfg.ANY4DH_TTS
            self.REF_FILE = cfg.ANY4DH_REF_FILE
            self.REF_TEXT = cfg.ANY4DH_REF_TEXT
            self.TTS_SERVER = cfg.ANY4DH_TTS_SERVER
            self.model = cfg.ANY4DH_MODEL
            self.transport = cfg.ANY4DH_TRANSPORT
            self.customopt = []
            # 滑动窗口参数（ASR需要）
            self.l = 10  # 左步长
            self.m = 8   # 中间步长
            self.r = 10  # 右步长

            # TTS引擎配置
            self.tts_engine = cfg.ANY4DH_TTS
            self.index_tts_model_dir = cfg.INDEX_TTS_MODEL_DIR
            self.index_tts_device = cfg.INDEX_TTS_DEVICE

    opt = OptConfig(config)

    # 多进程启动方法由主应用设置，这里不再重复设置
    # mp.set_start_method('spawn')  # 由主应用的 app.py 统一设置

    # Wav2Lip 模型初始化
    from .live_talking.lipreal import LipReal, load_model, load_avatar, warm_up
    logger.info(f"Initializing any4dh with avatar_id: {opt.avatar_id}")

    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 使用绝对路径
    model_path = config.ANY4DH_WAV2LIP_MODEL_DIR
    if not os.path.isabs(model_path):
        model_path = os.path.join(project_root, model_path)

    avatar_path = os.path.join(config.ANY4DH_AVATARS_DIR, opt.avatar_id)
    if not os.path.isabs(avatar_path):
        avatar_path = os.path.join(project_root, avatar_path)

    model = load_model(model_path)
    avatar = load_avatar(avatar_path)
    warm_up(opt.batch_size, model, 256)

    _any4dh_initialized = True
    return opt, model, avatar

# RTMP 推流模式辅助函数
async def post(url, data):
    """向 URL 发送数据"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                return await response.text()
    except Exception as e:
        logger.info(f'Error: {e}')

async def run_push(push_url, sessionid):
    """运行 RTMP 推流模式"""
    any4dh_real = await asyncio.get_event_loop().run_in_executor(None, build_any4dh_real, sessionid)
    any4dh_reals[sessionid] = any4dh_real

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    player = HumanPlayer(any4dh_reals[sessionid])
    audio_sender = pc.addTrack(player.audio)
    video_sender = pc.addTrack(player.video)

    await pc.setLocalDescription(await pc.createOffer())
    answer = await post(push_url, pc.localDescription.sdp)
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type='answer'))

# 独立运行模式（用于测试）
if __name__ == '__main__':
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期管理器"""
        yield  # 应用运行在此处

        # 关闭时清理
        coros = [pc.close() for pc in pcs]
        await asyncio.gather(*coros)
        pcs.clear()

    # 创建 FastAPI 应用
    app = FastAPI(
        title="any4dh API",
        description="基于 Wav2Lip 的实时交互数字人平台",
        version="1.0.0",
        lifespan=lifespan
    )

    # 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 静态文件服务
    app.mount("/static", StaticFiles(directory="static"), name="static")
    templates = Jinja2Templates(directory="static")

    # 注册路由
    register_any4dh_routes(app)

    parser = argparse.ArgumentParser()

    # 音频帧率
    parser.add_argument('--fps', type=int, default=50, help="音频帧率，必须为50")
    # 滑动窗口参数
    parser.add_argument('-l', type=int, default=10)
    parser.add_argument('-m', type=int, default=8)
    parser.add_argument('-r', type=int, default=10)

    # GUI 界面尺寸
    parser.add_argument('--W', type=int, default=450, help="GUI宽度")
    parser.add_argument('--H', type=int, default=450, help="GUI高度")

    # Wav2Lip 参数
    parser.add_argument('--avatar_id', type=str, default='001', help="指定data/avatars中的数字人")
    parser.add_argument('--batch_size', type=int, default=16, help="推理批量大小")

    parser.add_argument('--customvideo_config', type=str, default='', help="自定义动作JSON配置")

    parser.add_argument('--tts', type=str, default='edgetts', help="TTS服务类型")
    parser.add_argument('--REF_FILE', type=str, default="zh-CN-YunxiaNeural",help="参考文件名或语音模型ID")
    parser.add_argument('--REF_TEXT', type=str, default=None)
    parser.add_argument('--TTS_SERVER', type=str, default='http://127.0.0.1:9880')

    parser.add_argument('--model', type=str, default='wav2lip')

    parser.add_argument('--transport', type=str, default='webrtc')
    parser.add_argument('--push_url', type=str, default='http://localhost:1985/rtc/v1/whip/?app=live&stream=livestream')

    parser.add_argument('--max_session', type=int, default=1)  # 多会话数量
    parser.add_argument('--listenport', type=int, default=8888, help="Web监听端口（集成模式使用8888，独立模式可指定其他端口）")
    parser.add_argument('--host', type=str, default='0.0.0.0', help="绑定的主机地址")

    opt = parser.parse_args()

    # 全局存储配置
    globals()['opt'] = opt

    opt.customopt = []
    if opt.customvideo_config != '':
        with open(opt.customvideo_config, 'r') as file:
            opt.customopt = json.load(file)

    # 初始化 any4dh
    initialize_any4dh()

    logger.info(f'Starting FastAPI server: http://<serverip>:{opt.listenport}/dh/dashboard')

    # 启动服务器
    import uvicorn

    # 处理 rtcpush 模式启动任务
    if opt.transport == 'rtcpush':
        @asynccontextmanager
        async def rtcpush_lifespan(app: FastAPI):
            """rtcpush 模式的自定义生命周期"""
            async def start_push_tasks():
                for k in range(opt.max_session):
                    push_url = opt.push_url
                    if k != 0:
                        push_url = opt.push_url + str(k)
                    await run_push(push_url, k)

            asyncio.create_task(start_push_tasks())
            yield
            coros = [pc.close() for pc in pcs]
            await asyncio.gather(*coros)
            pcs.clear()

        app.router.lifespan_context = rtcpush_lifespan

    uvicorn.run(
        app,
        host=opt.host,
        port=opt.listenport,
        log_level="info"
    )