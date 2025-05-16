import os
import torch
class Config:
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8888
    
    # 认证配置
    API_KEY = "EMPTY"           # 替换为你的实际API密钥
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"         # 本地ASR模型路径
    RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"    # 本地rerank模型路径
    
    # MySQL数据库配置
    MYSQL_HOST = "172.17.64.1"  # 替换为你的实际的IP地址 可以使用ipconfig | findstr "IPv4" 查看
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "root"
    MYSQL_DATABASE = "any4any"  # 替换为你的数据库名称

    # 功能开关配置
    NO_THINK = True             # 是否开启nothink
    QUERY_CLEANING = True       # 是否开启SQL查询清洗功能
    PROMPT = ""                 # 自定义提示词
    
    # 确保模型目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)