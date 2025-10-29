import logging
from typing import List, Dict, Any
from config import Config
from .embedding_manager import EmbeddingManager
from .vector_store import VectorStore
from core.log import setup_logging
from core.model_manager import ModelManager

setup_logging()
logger = logging.getLogger(__name__)

class RetrievalEngine:
    """检索引擎，负责查询向量数据库并返回相关内容，支持重排序功能"""
    def __init__(self, embedding_manager: EmbeddingManager, vector_store: VectorStore, reranker=None):
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store

        if reranker is not None:
            self.reranker = reranker
        else:
            self.reranker = ModelManager.get_reranker()
    
    def retrieve_documents(self, question: str, top_k: int = None, use_rerank: bool = None) -> Dict[str, Any]:
        """检索相关文档并返回结果，支持重排序功能"""
        if top_k is None:
            top_k = Config.TOP_K
        
        if use_rerank is None:
            use_rerank = Config.RERANK_MODEL_ENABLED

        # 初步检索
        initial_top_k = top_k * Config.RERANK_CANDIDATE_FACTOR if use_rerank and self.reranker else top_k # rerank 候选文档数 默认10倍于top_k
        logger.info(f"Using embedding model to retriavaling...")
        question_embedding = self.embedding_manager.get_single_embedding(question) # 将问题转换为向量
        similar_docs = self.vector_store.search_similar(question_embedding, top_k=initial_top_k)  # 在向量库中搜索相似内容
        
        if not similar_docs:
            return {
                "documents": [],
                "question": question,
                "has_results": False
            }
        
        # rerank重排序
        if use_rerank and self.reranker and Config.RERANK_MODEL_ENABLED:            
            logger.info(f"Using rerank model to retriavaling...")
            documents = [metadata['chunk_text'] for _, metadata in similar_docs] # 准备重排序所需的数据
            
            # 批处理
            all_scores = []
            batch_size = Config.RERANK_BATCH_SIZE
            
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i + batch_size]                
                batch_pairs = [[question, doc] for doc in batch_docs] # 为批次中的每个文档创建(query, document)对
                batch_scores = self.reranker.compute_score(batch_pairs) # 计算批次的相关性分数
                # 如果返回的是单个分数，将其扩展为列表
                if isinstance(batch_scores, float):
                    batch_scores = [batch_scores] * len(batch_docs)
                all_scores.extend(batch_scores)
           
            # 组合结果并排序
            reranked_results = []
            for i, (_, metadata) in enumerate(similar_docs):
                reranked_results.append({
                    'score': all_scores[i],
                    'metadata': metadata
                })
                        
            reranked_results.sort(key=lambda x: x['score'], reverse=True) # 按相关性分数降序排列            
            final_docs = reranked_results[:top_k] # 取前top_k个结果
        else:
            # 不使用重排序，直接使用初始检索结果
            logger.info("Skipping reranking, using initial retrieval results")
            final_docs = [{'score': score, 'metadata': metadata} for score, metadata in similar_docs[:top_k]]
        
        # 构建返回结果
        documents = []
        
        for item in final_docs:
            metadata = item['metadata']
            documents.append({
                "file_name": metadata['file_name'],
                "chunk_text": metadata['chunk_text'],
                "score": float(item['score']),
                "metadata": metadata
            })
        
        return {
            "documents": documents,
            "question": question,
            "has_results": len(documents) > 0
        }
    
    def simple_search(self, question: str, top_k: int = None, use_rerank: bool = None) -> List[Dict[str, Any]]:
        """简单搜索，返回格式化的文档列表，保持向后兼容性"""
        result = self.retrieve_documents(question, top_k, use_rerank)
        
        # 提取文档列表并转换为所需格式
        return result.get("documents", [])
    
    def search(self, question: str, top_k: int = None, use_rerank: bool = None) -> Dict[str, Any]:
        """统一的检索API，供外部调用，返回完整的检索结果信息"""
        return self.retrieve_documents(question, top_k, use_rerank)

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取向量库统计信息，作为向量库的状态查询API"""
        try:
            return self.vector_store.get_stats()
        except Exception as e:
            logger.error(f"Error retrieving collection stats: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    def delete_document_by_file(self, file_name: str) -> Dict[str, Any]:
        """根据文件名删除相关文档"""
        logger.info(f"Deleting documents for file: {file_name}")
        try:
            success = self.vector_store.delete_file_vectors(file_name)
            return {
                "success": success,
                "file_name": file_name,
                "message": "文档删除成功" if success else "未找到指定文件的文档"
            }
        except Exception as e:
            logger.error(f"Error deleting documents for file {file_name}: {e}")
            return {
                "success": False,
                "file_name": file_name,
                "error": str(e)
            }
