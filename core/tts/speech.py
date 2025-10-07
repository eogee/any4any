import os
import time
import uuid
import logging
import sys
from fastapi import Request, Header, HTTPException
from edge_tts import Communicate
from core.auth.model_auth import verify_token
from core.model_manager import ModelManager
from core.tts.file import file_response_with_cleanup
from utils.content_handle.filter import filter_special_chars
from config import Config

# 确保core.tts目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

async def create_speech(
    request: Request,
    authorization: str = Header(None),
):
    """根据输入文本生成语音文件"""
    await verify_token(authorization)
    start_time = time.time()
    output_file = None
    
    try:
        data = await request.json()
        text = data.get("input", "")
        voice = data.get("voice", str(Config.DEFAULT_VOICE))
        
        text = filter_special_chars(text)
        
        # 检查是否使用IndexTTS
        if Config.INDEX_TTS_ENABLED:
            try:
                index_tts = ModelManager.get_index_tts()
                if index_tts is not None:
                    logger.info("Using IndexTTS for speech generation")
                    
                    if not text:
                        # 输入为空时生成一个静默的音频文件
                        output_file = f"temp_{uuid.uuid4().hex}.mp3"
                        with open(output_file, 'wb') as f:
                            f.write(b'')  # 写入空内容
                    else:
                        # 使用IndexTTS生成语音 - 创建固定的输出路径，使用与edge-tts相同的MP3格式
                        original_output_file = f"temp_{uuid.uuid4().hex}.mp3"
                        output_file = original_output_file  # 设置主输出文件变量
                        
                        # 获取当前文件所在目录
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        prompt_wav_path = os.path.join(current_dir, "prompt.wav")
                        
                        # 确保prompt.wav文件存在
                        if not os.path.exists(prompt_wav_path):
                            logger.warning("Prompt audio file not found, falling back to edge-tts")
                            output_file = None
                        else:
                            # 获取IndexTTS实例并确保其有效
                            tts = ModelManager.get_index_tts()
                            if tts is None:
                                logger.error("Failed to get valid IndexTTS instance")
                                output_file = None
                            else:
                                # 创建输出路径的绝对路径，确保稳定性
                                absolute_output_path = os.path.abspath(original_output_file)
                                logger.info(f"IndexTTS inferring to output path: {absolute_output_path}")
                                logger.info(f"Output file variable before inference: {output_file}")
                                
                                try:
                                    # 调用IndexTTS推理
                                    tts.infer_fast(
                                        audio_prompt=prompt_wav_path,
                                        text=text,
                                        output_path=absolute_output_path,  # 使用绝对路径
                                        max_text_tokens_per_sentence=100,
                                        sentences_bucket_max_size=4,
                                        do_sample=True,
                                        top_p=0.8,
                                        temperature=1.0
                                    )
                                    
                                    # 推理完成后立即检查文件
                                    logger.info(f"IndexTTS inference completed, checking file existence...")
                                    logger.info(f"Output file variable after inference: {output_file}")
                                    
                                    # 检查绝对路径和原始路径
                                    if os.path.exists(absolute_output_path):
                                        logger.info(f"Audio file found at absolute path: {absolute_output_path}")
                                        output_file = absolute_output_path
                                    elif os.path.exists(original_output_file):
                                        logger.info(f"Audio file found at original path: {original_output_file}")
                                        output_file = original_output_file
                                    else:
                                        logger.error(f"Audio file not found at either path. Absolute: {absolute_output_path}, Original: {original_output_file}")
                                        # 尝试在当前目录下查找任何新生成的mp3文件
                                    current_dir = os.getcwd()
                                    wav_files = [f for f in os.listdir(current_dir) if f.endswith('.mp3') and f.startswith('temp_')]
                                    if wav_files:
                                        latest_file = max(wav_files, key=lambda f: os.path.getctime(os.path.join(current_dir, f)))
                                        output_file = os.path.join(current_dir, latest_file)
                                        logger.info(f"Found recently created audio file: {output_file}")
                                    else:
                                        output_file = None
                                        
                                except Exception as infer_error:
                                    logger.error(f"IndexTTS inference failed: {str(infer_error)}")
                                    logger.error(f"Output path at time of error: {absolute_output_path}")
                                    output_file = None
                    
                    # 如果IndexTTS成功生成了音频，则返回
                    if output_file and os.path.exists(output_file):
                        file_size = os.path.getsize(output_file)
                        logger.info(f"Returning IndexTTS generated audio: {output_file} (size: {file_size} bytes)")
                        # 使用与edge-tts相同的媒体类型
                        media_type = "audio/mpeg"
                        return file_response_with_cleanup(
                            output_file,
                            media_type=media_type,
                            filename=os.path.basename(output_file),
                            cleanup_file=output_file
                        )
                    else:
                        # IndexTTS失败，继续使用edge-tts
                        logger.warning("IndexTTS generation failed, falling back to edge-tts")
                        if output_file:
                            logger.warning(f"Output file path state before fallback: '{output_file}'")
                        output_file = None
                        
            except Exception as e:
                logger.error(f"Error generating speech with IndexTTS: {str(e)}")
                logger.info("Falling back to edge-tts")
                output_file = None
        
        # 使用edge-tts生成语音（默认或当IndexTTS不可用时）
        logger.info("Using edge-tts for speech generation")
        
        # 处理edge-tts的声音选择
        available_voices = ModelManager.get_voices()
        if available_voices and not any(v["ShortName"] == voice for v in available_voices):
            logger.warning(f"Voice {voice} not available, using default voice")
            voice = str(Config.DEFAULT_VOICE)
        
        # 生成edge-tts输出文件
        edge_output_file = f"temp_{uuid.uuid4().hex}.mp3"
        
        if not text:
            # 输入为空时生成一个静默的音频文件
            with open(edge_output_file, 'wb') as f:
                f.write(b'')  # 写入空内容
            output_file = edge_output_file
        else:
            try:
                communicate = Communicate(text, voice)
                await communicate.save(edge_output_file)
                output_file = edge_output_file
            except Exception as e:
                logger.error(f"Failed to generate speech with edge-tts: {str(e)}")
                # 如果edge-tts也失败，尝试使用一个简单的空文件作为回退
                with open(edge_output_file, 'wb') as f:
                    f.write(b'')
                output_file = edge_output_file

        if not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Audio file creation failed")
        
        # 根据文件扩展名设置正确的媒体类型
        media_type = "audio/wav" if output_file.endswith(".wav") else "audio/mpeg"
        
        return file_response_with_cleanup(
            output_file,
            media_type=media_type,
            filename=os.path.basename(output_file),
            cleanup_file=output_file
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))
