import os
import time
import uuid
import logging
import sys
import asyncio
from fastapi import Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from edge_tts import Communicate
from core.auth.model_auth import verify_token
from core.model_manager import ModelManager
from core.tts.file import file_response_with_cleanup
from utils.content_handle.filter import filter_special_chars
from config import Config

# 确保core.tts目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

async def generate_silent_audio_stream():
    """生成静默音频流"""
    silent_mp3 = b'\xff\xfb\x90\x64\x00'  # 静默MP3帧头
    yield silent_mp3

async def generate_with_edge_tts_stream(text: str, voice: str):
    """使用edge-tts流式生成音频"""
    if not text:
        async for chunk in generate_silent_audio_stream():
            yield chunk
        return
    
    try:
        communicate = Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
                # 添加小延迟，模拟实时生成效果
                await asyncio.sleep(0.01)
                
    except Exception as e:
        logger.error(f"edge-tts stream generation failed: {str(e)}")
        # 失败时返回静默音频
        async for chunk in generate_silent_audio_stream():
            yield chunk

async def generate_with_index_tts_stream(text: str, tts):
    """使用IndexTTS流式生成音频（模拟流式）"""
    # 由于IndexTTS可能不支持真正的流式生成，我们模拟流式行为
    # 先生成完整文件，然后分块读取
    output_file = f"temp_{uuid.uuid4().hex}.mp3"
    absolute_output_path = os.path.abspath(output_file)
    
    # 获取prompt文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_wav_path = os.path.join(current_dir, "prompt.wav")
    
    if not os.path.exists(prompt_wav_path):
        logger.warning("Prompt audio file not found")
        async for chunk in generate_silent_audio_stream():
            yield chunk
        return
    
    try:
        logger.info(f"Starting IndexTTS stream inference to: {absolute_output_path}")
        
        # 调用IndexTTS生成完整文件
        tts.infer_fast(
            audio_prompt=prompt_wav_path,
            text=text,
            output_path=absolute_output_path,
            max_text_tokens_per_sentence=100,
            sentences_bucket_max_size=4,
            do_sample=True,
            top_p=0.8,
            temperature=1.0
        )
        
        # 等待文件生成完成
        max_wait_time = 30
        wait_interval = 0.5
        elapsed = 0
        
        file_ready = False
        while elapsed < max_wait_time:
            if (os.path.exists(absolute_output_path) and 
                os.path.getsize(absolute_output_path) > 100):
                file_ready = True
                break
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
        
        if file_ready:
            # 分块读取文件并流式返回
            chunk_size = 4096  # 4KB chunks
            with open(absolute_output_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    # 添加小延迟，模拟实时生成
                    await asyncio.sleep(0.01)
            
            # 清理临时文件
            try:
                os.remove(absolute_output_path)
                logger.info(f"Cleaned up temporary IndexTTS file: {absolute_output_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup IndexTTS file: {str(e)}")
                
        else:
            logger.error("IndexTTS file generation timeout")
            async for chunk in generate_silent_audio_stream():
                yield chunk
                
    except Exception as e:
        logger.error(f"IndexTTS stream inference failed: {str(e)}")
        # 清理可能生成的不完整文件
        if os.path.exists(absolute_output_path):
            try:
                os.remove(absolute_output_path)
            except:
                pass
        async for chunk in generate_silent_audio_stream():
            yield chunk

async def create_speech(
    request: Request,
    authorization: str = Header(None),
):
    """根据输入文本流式生成语音"""
    await verify_token(authorization)
    start_time = time.time()
    
    try:
        data = await request.json()
        text = data.get("input", "")
        voice = data.get("voice", str(Config.DEFAULT_VOICE))
        
        text = filter_special_chars(text)
        logger.info(f"TTS stream request - text length: {len(text)}, voice: {voice}")
        
        # 处理edge-tts的声音选择
        available_voices = ModelManager.get_voices()
        if available_voices and not any(v["ShortName"] == voice for v in available_voices):
            logger.warning(f"Voice {voice} not available, using default voice")
            voice = str(Config.DEFAULT_VOICE)
        
        async def generate_audio_stream():
            """生成音频流的协程"""
            chunks_generated = 0
            total_size = 0
            
            try:
                # 检查是否使用IndexTTS
                if Config.INDEX_TTS_ENABLED:
                    try:
                        index_tts = ModelManager.get_index_tts()
                        if index_tts is not None:
                            logger.info("Using IndexTTS for stream speech generation")
                            async for chunk in generate_with_index_tts_stream(text, index_tts):
                                chunks_generated += 1
                                total_size += len(chunk)
                                yield chunk
                            return
                    except Exception as e:
                        logger.error(f"IndexTTS stream failed, falling back to edge-tts: {str(e)}")
                
                # 使用edge-tts回退
                logger.info("Using edge-tts for stream speech generation")
                async for chunk in generate_with_edge_tts_stream(text, voice):
                    chunks_generated += 1
                    total_size += len(chunk)
                    yield chunk
                    
            except Exception as e:
                logger.error(f"Audio stream generation failed: {str(e)}")
                # 返回静默音频作为最后手段
                async for chunk in generate_silent_audio_stream():
                    yield chunk
            finally:
                processing_time = time.time() - start_time
                logger.info(f"Stream completed - chunks: {chunks_generated}, total size: {total_size} bytes, time: {processing_time:.2f}s")
        
        # 立即返回流式响应
        headers = {
            "Content-Type": "audio/mpeg",
            "Transfer-Encoding": "chunked",
            "X-Content-Type-Options": "nosniff"
        }
        
        return StreamingResponse(
            generate_audio_stream(),
            media_type="audio/mpeg",
            headers=headers
        )
        
    except Exception as e:
        logger.error(f"TTS stream setup failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Speech generation failed")

# 保留原有的非流式接口作为备用
async def create_speech_legacy(
    request: Request,
    authorization: str = Header(None),
):
    """传统的完整文件生成接口（备用）"""
    await verify_token(authorization)
    start_time = time.time()
    output_file = None
    
    try:
        data = await request.json()
        text = data.get("input", "")
        voice = data.get("voice", str(Config.DEFAULT_VOICE))
        
        text = filter_special_chars(text)
        logger.info(f"TTS legacy request - text length: {len(text)}, voice: {voice}")
        
        # 检查是否使用IndexTTS
        if Config.INDEX_TTS_ENABLED:
            try:
                index_tts = ModelManager.get_index_tts()
                if index_tts is not None:
                    logger.info("Using IndexTTS for legacy speech generation")
                    
                    output_file = await generate_with_index_tts_legacy(text, index_tts)
                    
                    # 验证音频文件完整性
                    if output_file and await validate_audio_file(output_file):
                        file_size = os.path.getsize(output_file)
                        logger.info(f"IndexTTS audio validated: {output_file} (size: {file_size} bytes)")
                        processing_time = time.time() - start_time
                        logger.info(f"IndexTTS processing completed in {processing_time:.2f} seconds")
                        return await create_file_response(output_file)
                    else:
                        logger.warning("IndexTTS generation failed or invalid, falling back to edge-tts")
                        if output_file:
                            await safe_cleanup_file(output_file)
                        output_file = None
                        
            except Exception as e:
                logger.error(f"Error generating speech with IndexTTS: {str(e)}")
                if output_file:
                    await safe_cleanup_file(output_file)
                output_file = None
        
        # 使用edge-tts回退
        logger.info("Using edge-tts for legacy speech generation")
        
        # 处理edge-tts的声音选择
        available_voices = ModelManager.get_voices()
        if available_voices and not any(v["ShortName"] == voice for v in available_voices):
            logger.warning(f"Voice {voice} not available, using default voice")
            voice = str(Config.DEFAULT_VOICE)
        
        output_file = await generate_with_edge_tts_legacy(text, voice)
        
        if not output_file or not os.path.exists(output_file):
            logger.error("Audio file creation failed")
            # 最后一次尝试生成静默音频
            output_file = await generate_silent_audio_legacy()
            if not output_file:
                raise HTTPException(status_code=500, detail="Audio file creation failed")
        
        # 最终验证
        if not await validate_audio_file(output_file):
            logger.error("Generated audio file is invalid")
            # 尝试生成静默音频作为最后手段
            fallback_file = await generate_silent_audio_legacy()
            if fallback_file:
                await safe_cleanup_file(output_file)
                output_file = fallback_file
            else:
                raise HTTPException(status_code=500, detail="Generated audio file is invalid")
        
        processing_time = time.time() - start_time
        logger.info(f"edge-tts processing completed in {processing_time:.2f} seconds")
        return await create_file_response(output_file)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        await safe_cleanup_file(output_file)
        raise HTTPException(status_code=500, detail="Speech generation failed")

async def generate_silent_audio_legacy(filename: str = None) -> str:
    """生成静默音频文件（传统方式）"""
    if not filename:
        filename = f"temp_{uuid.uuid4().hex}.mp3"
    
    try:
        silent_mp3 = b'\xff\xfb\x90\x64\x00'
        with open(filename, 'wb') as f:
            f.write(silent_mp3)
        return filename
    except Exception as e:
        logger.error(f"Failed to create silent audio: {str(e)}")
        return None

async def generate_with_index_tts_legacy(text: str, tts) -> str:
    """使用IndexTTS生成音频（传统方式）"""
    output_file = f"temp_{uuid.uuid4().hex}.mp3"
    absolute_output_path = os.path.abspath(output_file)
    
    # 获取prompt文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_wav_path = os.path.join(current_dir, "prompt.wav")
    
    if not os.path.exists(prompt_wav_path):
        logger.warning("Prompt audio file not found")
        return None
    
    try:
        logger.info(f"Starting IndexTTS inference to: {absolute_output_path}")
        
        # 调用IndexTTS
        tts.infer_fast(
            audio_prompt=prompt_wav_path,
            text=text,
            output_path=absolute_output_path,
            max_text_tokens_per_sentence=100,
            sentences_bucket_max_size=4,
            do_sample=True,
            top_p=0.8,
            temperature=1.0
        )
        
        # 等待文件生成完成
        max_wait_time = 30  # 最大等待30秒
        wait_interval = 0.5  # 检查间隔0.5秒
        elapsed = 0
        
        while elapsed < max_wait_time:
            if (os.path.exists(absolute_output_path) and 
                os.path.getsize(absolute_output_path) > 100):  # 确保文件有合理大小
                
                # 额外等待一下确保文件写入完成
                await asyncio.sleep(1)
                logger.info(f"IndexTTS file generated successfully: {absolute_output_path} (size: {os.path.getsize(absolute_output_path)} bytes)")
                return absolute_output_path
            
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
        
        logger.error(f"IndexTTS file generation timeout: {absolute_output_path}")
        return None
        
    except Exception as e:
        logger.error(f"IndexTTS inference failed: {str(e)}")
        return None

async def generate_with_edge_tts_legacy(text: str, voice: str) -> str:
    """使用edge-tts生成音频（传统方式）"""
    output_file = f"temp_{uuid.uuid4().hex}.mp3"
    
    if not text:
        return await generate_silent_audio_legacy(output_file)
    
    try:
        communicate = Communicate(text, voice)
        await communicate.save(output_file)
        
        # 验证生成的文件
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            logger.info(f"edge-tts file generated successfully: {output_file} (size: {os.path.getsize(output_file)} bytes)")
            return output_file
        else:
            logger.warning("edge-tts generated empty file, creating silent audio instead")
            return await generate_silent_audio_legacy(output_file)
            
    except Exception as e:
        logger.error(f"edge-tts generation failed: {str(e)}")
        return await generate_silent_audio_legacy(output_file)

async def validate_audio_file(file_path: str) -> bool:
    """验证音频文件是否完整"""
    if not file_path or not os.path.exists(file_path):
        return False
    
    try:
        file_size = os.path.getsize(file_path)
        if file_size < 10:  # 文件太小，可能不完整
            logger.warning(f"Audio file too small: {file_size} bytes")
            return False
        
        # 检查文件是否可读（基本验证）
        with open(file_path, 'rb') as f:
            header = f.read(10)
            if len(header) < 10:
                return False
        
        return True
    except Exception as e:
        logger.error(f"Audio file validation failed: {str(e)}")
        return False

async def create_file_response(file_path: str):
    """创建文件响应"""
    media_type = "audio/wav" if file_path.endswith(".wav") else "audio/mpeg"
    
    return file_response_with_cleanup(
        file_path,
        media_type=media_type,
        filename=os.path.basename(file_path),
        cleanup_file=file_path
    )

async def safe_cleanup_file(file_path: str):
    """安全清理文件"""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {str(e)}")