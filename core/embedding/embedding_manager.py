import logging
import torch
import torch.nn.functional as F
import numpy as np
from typing import List
from transformers import AutoTokenizer, AutoModel
from config import Config
from core.log import setup_logging
from core.model_manager import ModelManager

setup_logging()
logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or Config.EMBEDDING_MODEL_DIR
        self.tokenizer = None
        self.model = None
        self._load_model()
        
    def use_global_model(self):
        """使用ModelManager中全局加载的嵌入模型"""
        try:
            model, tokenizer = ModelManager.get_embedding_model()
            if model is not None and tokenizer is not None:
                self.model = model
                self.tokenizer = tokenizer
                logger.info("Using embedding model from ModelManager")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to use global embedding model: {e}")
            return False
    
    def _load_model(self):
        """加载Embedding模型"""
        try:
            if self.use_global_model():
                return
                
            logger.info(f"Loading embedding model locally: {self.model_name}") # 如果全局模型未加载，则自己加载
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
        except Exception as e:
            logger.error(f"Load model failed: {e}")
            raise
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """获取文本的向量表示"""
        if self.tokenizer is None or self.model is None:
            raise ValueError("Model not loaded correctly")
        
        # 编码文本
        encoded_input = self.tokenizer(
            texts, 
            padding=True, 
            truncation=True, 
            return_tensors='pt',
            max_length=4096
        )
        
        # 计算嵌入
        with torch.no_grad():
            model_output = self.model(**encoded_input)            
            sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask']) # 使用平均池化获取句子嵌入            
            sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)  # 归一化                
        
        # 返回numpy数组
        return sentence_embeddings.numpy()
    
    def get_embeddings_as_list(self, texts: List[str]) -> List[List[float]]:
        """获取文本的向量表示并返回为Python列表格式（适用于ChromaDB）"""
        embeddings = self.get_embeddings(texts)
        return embeddings.tolist()
    
    def _mean_pooling(self, model_output, attention_mask):
        """平均池化"""
        token_embeddings = model_output[0]  # 第一个元素包含token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def get_single_embedding(self, text: str) -> np.ndarray:
        """获取单个文本的向量"""
        return self.get_embeddings([text])[0]