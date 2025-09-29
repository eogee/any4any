import json
import os
import pickle
import numpy as np
from typing import List, Dict, Any, Tuple
from config import Config

class VectorStore:
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or Config.VECTOR_DB_PATH
        self.vectors = []  # 存储向量
        self.metadata = []  # 存储元数据
        self.vector_index = {}  # 文件名到向量索引的映射
        
        self._load_data()
    
    def _get_data_files(self):
        """获取数据文件路径"""
        vectors_file = os.path.join(self.storage_path, "vectors.npy")
        metadata_file = os.path.join(self.storage_path, "metadata.pkl")
        index_file = os.path.join(self.storage_path, "index.json")
        return vectors_file, metadata_file, index_file
    
    def _load_data(self):
        """加载存储的数据"""
        vectors_file, metadata_file, index_file = self._get_data_files()
        
        if all(os.path.exists(f) for f in [vectors_file, metadata_file, index_file]):
            try:
                self.vectors = np.load(vectors_file)
                with open(metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                with open(index_file, 'r', encoding='utf-8') as f:
                    self.vector_index = json.load(f)
                print(f"加载了 {len(self.vectors)} 个向量")
            except Exception as e:
                print(f"加载向量数据失败: {e}")
                self.vectors = []
                self.metadata = []
                self.vector_index = {}
    
    def save_data(self):
        """保存数据到磁盘"""
        os.makedirs(self.storage_path, exist_ok=True)
        vectors_file, metadata_file, index_file = self._get_data_files()
        
        try:
            if len(self.vectors) > 0:
                np.save(vectors_file, np.array(self.vectors))
            with open(metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(self.vector_index, f, ensure_ascii=False, indent=2)
            print(f"保存了 {len(self.vectors)} 个向量")
        except Exception as e:
            print(f"保存向量数据失败: {e}")
    
    def add_vectors(self, vectors: np.ndarray, metadata_list: List[Dict[str, Any]]):
        """添加向量和元数据"""
        start_index = len(self.vectors)
        
        # 添加向量
        if len(self.vectors) == 0:
            self.vectors = vectors
        else:
            self.vectors = np.vstack([self.vectors, vectors])
        
        # 添加元数据
        self.metadata.extend(metadata_list)
        
        # 更新索引
        for i, metadata in enumerate(metadata_list):
            file_name = metadata['file_name']
            if file_name not in self.vector_index:
                self.vector_index[file_name] = []
            self.vector_index[file_name].append(start_index + i)
    
    def search_similar(self, query_vector: np.ndarray, top_k: int = None) -> List[Tuple[float, Dict[str, Any]]]:
        if top_k is None:
            top_k = Config.TOP_K
        """搜索相似的向量"""
        if len(self.vectors) == 0:
            return []
        
        # 计算余弦相似度
        similarities = np.dot(self.vectors, query_vector) / (
            np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(query_vector)
        )
        
        # 获取最相似的top_k个结果
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if idx < len(self.metadata):
                results.append((similarities[idx], self.metadata[idx]))
        
        return results
    
    def get_file_vectors(self, file_name: str) -> List[int]:
        """获取文件的向量索引"""
        return self.vector_index.get(file_name, [])
    
    def delete_file_vectors(self, file_name: str) -> bool:
        """删除文件的所有向量"""
        if file_name not in self.vector_index:
            return False
        
        indices_to_remove = set(self.vector_index[file_name])
        
        # 创建新的向量、元数据和索引
        new_vectors = []
        new_metadata = []
        new_index = {}
        
        for i, (vector, metadata) in enumerate(zip(self.vectors, self.metadata)):
            if i not in indices_to_remove:
                new_index_pos = len(new_vectors)
                new_vectors.append(vector)
                new_metadata.append(metadata)
                
                # 更新索引
                current_file = metadata['file_name']
                if current_file not in new_index:
                    new_index[current_file] = []
                new_index[current_file].append(new_index_pos)
        
        # 更新数据
        self.vectors = np.array(new_vectors) if new_vectors else np.array([])
        self.metadata = new_metadata
        self.vector_index = new_index
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取向量库统计信息"""
        return {
            "total_vectors": len(self.vectors),
            "total_files": len(self.vector_index),
            "files": list(self.vector_index.keys())
        }