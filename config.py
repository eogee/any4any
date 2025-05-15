# config.py 配置文件
import os
import torch # type: ignore
class Config:
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8888
    
    # 认证配置
    API_KEY = "EMPTY"  # 替换为你的实际API密钥
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"  # 本地ASR模型路径
    RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"  # 本地rerank模型路径

    # 是否开启nothink，目前仅有qwen3系列LLM模型支持
    NO_THINK = True

    # 提示词
    PROMPT = "" # 自定义提示词，会在语音转文字识别结果后面显示，建议使用中文，留空则无内容
    
    # 确保模型目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)