import torch
import torch.nn.functional as F
from typing import List
import numpy as np
from transformers import AutoTokenizer, AutoModel
from config import Config

class EmbeddingManager:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or Config.EMBEDDING_MODEL_DIR
        self.tokenizer = None
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """加载Embedding模型"""
        print(f"正在加载Embedding模型: {self.model_name}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            print("Embedding模型加载完成")
        except Exception as e:
            print(f"加载Embedding模型失败: {e}")
            raise
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """获取文本的向量表示"""
        if self.tokenizer is None or self.model is None:
            raise ValueError("模型未正确加载")
        
        # 编码文本
        encoded_input = self.tokenizer(
            texts, 
            padding=True, 
            truncation=True, 
            return_tensors='pt',
            max_length=512
        )
        
        # 计算嵌入
        with torch.no_grad():
            model_output = self.model(**encoded_input)
            # 使用平均池化获取句子嵌入
            sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
            # 归一化
            sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)
        
        return sentence_embeddings.numpy()
    
    def _mean_pooling(self, model_output, attention_mask):
        """平均池化"""
        token_embeddings = model_output[0]  # 第一个元素包含token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def get_single_embedding(self, text: str) -> np.ndarray:
        """获取单个文本的向量"""
        return self.get_embeddings([text])[0]