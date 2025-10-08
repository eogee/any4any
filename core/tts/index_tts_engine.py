import os
import logging
import threading
import time
import sys
import torch
from typing import Optional, Dict, Any
from config import Config

logger = logging.getLogger(__name__)

class IndexTTSEngine:
    """IndexTTS-1.5模型引擎"""
    _instance: Optional['IndexTTSEngine'] = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls, config=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(IndexTTSEngine, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config=None):
        if not IndexTTSEngine._initialized:
            with self._lock:
                if not IndexTTSEngine._initialized:
                    self.config = config or {}
                    self.model_path = self.config.get('model_path', Config.INDEX_TTS_MODEL_DIR)
                    self.device = self.config.get('device', Config.INDEX_TTS_DEVICE)
                    self.max_workers = self.config.get('max_workers', Config.INDEX_TTS_MAX_WORKERS)
                    self.timeout = self.config.get('timeout', Config.INDEX_TTS_TIMEOUT)
                    self.supported_voices = self.config.get('supported_voices', Config.INDEX_TTS_SUPPORTED_VOICES)
                    self.model = None
                    self._min_request_interval = self.config.get('min_request_interval', 0.5)
                    self._last_request_time = 0
                    self._processing_lock = threading.Lock()
                    self._initialize()
    
    def _initialize(self):
        """初始化IndexTTS-1.5引擎"""
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model path not found: {self.model_path}")
            
            config_path = os.path.join(self.model_path, "config.yaml")
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Config file not found: {config_path}")
            
            # 添加模块路径到系统路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            indextts_path = os.path.join(current_dir, "indextts")
            if os.path.exists(indextts_path):
                sys.path.insert(0, current_dir)
                sys.path.insert(0, indextts_path)
            
            IndexTTSInference = self._import_model()
            
            if IndexTTSInference is None:
                raise ImportError("Failed to import IndexTTSInference class")
            
            self.model = IndexTTSInference(model_path=self.model_path, device=self.device)
            logger.info(f"IndexTTS-1.5 engine loaded with {'CUDA' if self.device == 'cuda' else 'CPU'}")
            IndexTTSEngine._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize IndexTTS-1.5 engine: {str(e)}")
            IndexTTSEngine._initialized = False
            self.model = None
    
    def _import_model(self):
        """导入IndexTTS模型"""
        try:
            from indextts.infer import IndexTTSInference
            return IndexTTSInference
        except ImportError as e:
            logger.warning(f"Direct import failed: {e}")
        
        return None
    
    def generate_speech(self, text: str, output_path: str, voice: Optional[str] = None) -> bool:
        """生成语音文件"""
        try:
            return self._process_with_throttling(text, output_path, voice)
        except Exception as e:
            logger.error(f"Error in generate_speech: {str(e)}")
            return False
    
    def _process_with_throttling(self, text: str, output_path: str, voice: Optional[str] = None) -> bool:
        """限流处理TTS请求"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)
        
        with self._processing_lock:
            self._last_request_time = time.time()
            return self._generate_speech(text, output_path, voice)
    
    def _generate_speech(self, text: str, output_path: str, voice: Optional[str] = None) -> bool:
        """语音生成"""
        if not self._initialized or self.model is None:
            logger.error("IndexTTS engine not initialized")
            return False
        
        if not text or len(text.strip()) == 0:
            logger.error("Empty text provided")
            return False
        # if len(text) > 30:
        #     logger.warning(f"Text too long: {len(text)} characters")
        #     return False        
        voice_id = voice or "default"
        if voice_id == "default":
            default_wav_path = os.path.join(os.path.dirname(__file__), "indextts", "default.wav")
            if os.path.exists(default_wav_path):
                voice_id = default_wav_path

        if voice_id != default_wav_path and voice_id not in self.supported_voices:
            logger.warning(f"Voice '{voice_id}' not in supported voices list, using default")
            voice_id = "default"
        
        logger.info(f"Generating speech, text: {text}, length: {len(text)}")
        
        try:
            # 尝试不同的方法调用
            if hasattr(self.model, 'infer'):
                result = self.model.infer(text=text, output_path=output_path, voice=voice_id)
            else:
                logger.error("Model has no 'infer' or 'generate' method")
                return False
            
            # 检查输出文件
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully generated: {output_path}")
                return True
            else:
                logger.error("Output file not found or empty")
                return False
                
        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            return False

    @classmethod
    def get_instance(cls, config=None):
        """获取引擎实例"""
        if cls._instance is None:
            return cls(config)
        return cls._instance
    
    @classmethod
    def cleanup(cls):
        """清理资源"""
        with cls._lock:
            logger.info("Cleaning up IndexTTS-1.5 engine...")
            try:
                if cls._instance and cls._instance.model is not None:
                    if hasattr(cls._instance.model, 'cleanup'):
                        cls._instance.model.cleanup()
                    cls._instance.model = None
                
                cls._initialized = False
                cls._instance = None
                
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    
            except Exception as e:
                logger.error(f"Error cleaning up: {str(e)}")
    
    @classmethod
    def is_initialized(cls) -> bool:
        """检查引擎是否已初始化"""
        return cls._initialized
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """获取引擎状态信息"""
        instance = cls._instance
        status = {
            "initialized": cls._initialized,
            "enabled": Config.INDEX_TTS_ENABLED,
            "model_loaded": instance.model is not None if instance else False,
            "device": instance.device if instance else "unknown",
            "model_path": instance.model_path if instance else "unknown"
        }
        
        # 添加更多实例相关的状态信息
        if instance:
            status.update({
                "max_workers": instance.max_workers,
                "timeout": instance.timeout,
                "supported_voices": instance.supported_voices
            })
        
        return status