import chromadb
from chromadb.config import Settings
import uuid
import logging
from typing import List, Dict, Any, Tuple
from config import Config
from core.log import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or Config.VECTOR_DB_PATH
        
        # 初始化ChromaDB客户端，禁用匿名遥测
        self.client = chromadb.PersistentClient(
            path=self.storage_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 创建或获取集合
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )
        
        logger.info(f"ChromaDB vector storage initialized, collection: documents")
    
    def add_vectors(self, vectors: List[List[float]], metadata_list: List[Dict[str, Any]]):
        """添加向量和元数据"""
        ids = [str(uuid.uuid4()) for _ in range(len(metadata_list))]    # 为每个文档生成唯一ID        
        
        documents = [meta['chunk_text'] for meta in metadata_list]      # 提取文档文本

        # 添加到集合
        self.collection.add(
            documents=documents,
            embeddings=vectors,
            metadatas=metadata_list,
            ids=ids
        )
        
        logger.info(f"Successfully added {len(vectors)} vectors to ChromaDB")
    
    def search_similar(self, query_vector: List[float], top_k: int = None) -> List[Tuple[float, Dict[str, Any]]]:
        """搜索相似的向量"""
        if top_k is None:
            top_k = Config.TOP_K
        
        # 使用向量搜索
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["metadatas", "documents", "distances"]
        )
        
        # 转换结果格式
        formatted_results = []
        if results and 'metadatas' in results and results['metadatas'] and results['distances']:
            for i in range(len(results['metadatas'][0])):
                # ChromaDB返回的是距离，我们需要转换为相似度（1-距离）
                similarity = 1 - results['distances'][0][i]
                formatted_results.append((similarity, results['metadatas'][0][i]))
        
        return formatted_results
    
    def get_file_vectors(self, file_name: str) -> List[str]:
        """获取文件的向量ID"""
        results = self.collection.get(
            where={"file_name": file_name},
            include=["ids"]
        )
        return results.get("ids", [])
    
    def delete_file_vectors(self, file_name: str) -> bool:
        """删除文件的所有向量"""
        try:
            # 获取文件的所有向量ID
            ids_to_delete = self.get_file_vectors(file_name)
            
            if not ids_to_delete:
                return False
            
            # 删除向量
            self.collection.delete(ids=ids_to_delete)
            logger.info(f"Successfully deleted {len(ids_to_delete)} vectors for file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors for file {file_name}: {e}")
            return False
    
    def save_data(self):
        """保存数据"""
        logger.info("ChromaDB has persisted data")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取向量库统计信息"""        
        results = self.collection.get(include=["metadatas"]) # 获取所有向量
        total_vectors = len(results.get("ids", [])) # 计算统计信息
        
        # 获取唯一文件名
        files = set()
        if results.get("metadatas"):
            for meta in results["metadatas"]:
                if meta and "file_name" in meta:
                    files.add(meta["file_name"])
        
        return {
            "total_vectors": total_vectors,
            "total_files": len(files),
            "files": list(files)
        }