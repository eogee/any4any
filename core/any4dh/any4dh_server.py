# any4dh FastAPI 服务器
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
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

    logger.info(f'Starting FastAPI server: http://<serverip>:{opt.listenport}/dashboard.html')

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