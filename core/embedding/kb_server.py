import os
import logging
import traceback
from typing import Dict, Any
from config import Config
from core.embedding.document_processor import DocumentProcessor
from core.embedding.embedding_manager import EmbeddingManager
from core.embedding.vector_store import VectorStore
from core.embedding.retrieval_engine import RetrievalEngine
from core.log import setup_logging
from core.model_manager import ModelManager

setup_logging()
logger = logging.getLogger(__name__)

class KnowledgeBaseServer:
    """知识库服务类，提供知识库相关功能的API接口"""
    def __init__(self):
        self.embedding_manager = None
        self.vector_store = None
        self.retrieval_engine = None
        self._initialized = False
    
    def _initialize_components(self):
        """初始化组件"""
        try:
            # 检查ModelManager是否已经初始化
            if not hasattr(ModelManager, '_initialized') or not ModelManager._initialized:
                self._initialized = False
                return False
                
            # 初始化嵌入管理器和向量存储
            if self.embedding_manager is None:
                self.embedding_manager = EmbeddingManager(Config.EMBEDDING_MODEL_DIR)
            if self.vector_store is None:
                self.vector_store = VectorStore(Config.VECTOR_DB_PATH)
            
            reranker = ModelManager.get_reranker()
            
            # 创建或更新检索引擎
            self.retrieval_engine = RetrievalEngine(self.embedding_manager, self.vector_store, reranker=reranker)
            self._initialized = True            
            return True

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._initialized = False
            return False
    
    def ensure_initialized(self):
        """确保组件已初始化，在每次使用前调用"""
        if not self._initialized:
            return self._initialize_components()

        if self.retrieval_engine and not self.retrieval_engine.reranker:
            return self._initialize_components()

        return True
    
    def build_knowledge_base(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """构建知识库"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            # 检查是否已有数据
            stats = self.vector_store.get_stats()
            if not force_rebuild and stats['total_vectors'] > 0:
                logger.info("Knowledge base already exists. Use force_rebuild=True to rebuild.")
                return {"success": True, "message": "知识库已存在，使用force_rebuild=True参数可强制重建"}
            
            # 如果是强制重建，先清空集合
            if force_rebuild:
                try:
                    self.vector_store.client.delete_collection(name="documents")
                    self.vector_store.collection = self.vector_store.client.create_collection(
                        name="documents",
                        metadata={"hnsw:space": "cosine"}
                    )
                    logger.info("Knowledge base collection has been rebuilt.")
                except Exception as e:
                    logger.error(f"Failed to clear knowledge base collection: {e}")
                    return {"success": False, "message": f"清空知识库失败: {str(e)}"}
            
            processor = DocumentProcessor(
                chunk_size=Config.DOC_CHUNK_SIZE,
                chunk_overlap=Config.DOC_CHUNK_OVERLAP
            )
            
            documents = processor.process_documents(Config.DOCS_PATH)
            
            if not documents:
                logger.info("No documents found in data/docs directory. Please add documents.")
                return {"success": False, "message": "未在docs目录找到文档，请添加文档后重试"}
            
            # 生成向量并存储
            all_chunks = []
            all_metadata = []
            
            for doc in documents:
                for chunk_info in doc['chunks']:
                    all_chunks.append(chunk_info['text'])
                    all_metadata.append({
                        'file_name': doc['file_name'],
                        'chunk_text': chunk_info['text'],
                        'chunk_index': chunk_info['metadata']['chunk_index'],
                        'total_chunks': chunk_info['metadata']['total_chunks']
                    })
            
            if all_chunks:
                # 获取列表格式的向量(ChromaDB)
                embeddings = self.embedding_manager.get_embeddings_as_list(all_chunks)
                self.vector_store.add_vectors(embeddings, all_metadata)
                self.vector_store.save_data()
                logger.info("Knowledge base has been built successfully.")
                return {"success": True, "message": "知识库构建成功", "document_count": len(documents), "chunk_count": len(all_chunks)}
            else:
                logger.info("No chunks generated. Please check document processing.")
                return {"success": False, "message": "未生成文本块，请检查文档处理过程"}
                
        except Exception as e:
            logger.error(f"Error during knowledge base building: {e}")
            return {"success": False, "message": f"构建知识库时出错: {str(e)}"}
    
    def retrieve_documents(self, question: str, top_k: int = 3, use_rerank: bool = True) -> Dict[str, Any]:
        """检索相关文档"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            stats = self.vector_store.get_stats()
            if stats['total_vectors'] == 0:
                logger.info("Knowledge base is empty. Please build the knowledge base first.")
                return {"success": False, "message": "知识库为空，请先构建知识库"}
            
            result = self.retrieval_engine.retrieve_documents(question, top_k, use_rerank) # 执行检索
            
            return {
                "success": True,
                "question": question,
                "documents": result.get("documents", []),
                "has_results": result.get("has_results", False),
                "total": len(result.get("documents", []))
            }
            
        except Exception as e:
            logger.error(f"Error during document retrieval: {e}")
            return {"success": False, "message": f"检索文档时出错: {str(e)}"}
    
    def simple_search(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """简单搜索，返回格式化的文档列表"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            stats = self.vector_store.get_stats()
            if stats['total_vectors'] == 0:
                logger.info("Knowledge base is empty. Please build the knowledge base first.")
                return {"success": False, "message": "知识库为空，请先构建知识库"}
            
            results = self.retrieval_engine.simple_search(question, top_k)
            
            # 格式化结果
            formatted_results = []
            for score, metadata in results:
                formatted_results.append({
                    "score": score,
                    "file_name": metadata.get("file_name", "未知文件"),
                    "content": metadata.get("chunk_text", ""),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "total_chunks": metadata.get("total_chunks", 0)
                })
            
            return {
                "success": True,
                "query": question,
                "results": formatted_results,
                "total": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Error during simple search: {e}")
            return {"success": False, "message": f"简单搜索时出错: {str(e)}"}
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            stats = self.vector_store.get_stats()
            
            return {
                "success": True,
                "total_vectors": stats['total_vectors'],
                "total_files": stats['total_files'],
                "files": stats['files']
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"success": False, "message": f"获取统计信息时出错: {str(e)}"}
    
    def delete_document_by_file(self, file_name: str) -> Dict[str, Any]:
        """删除指定文件的所有向量"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            success = self.vector_store.delete_file_vectors(file_name)
            if success:
                self.vector_store.save_data()
                logger.info(f"Deleted all vectors for file '{file_name}'")
                return {"success": True, "message": "文档删除成功"}
            else:
                logger.info(f"File '{file_name}' not found in knowledge base")
                return {"success": False, "message": "未找到指定文件的文档"}
                
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return {"success": False, "message": f"删除文档时出错: {str(e)}"}
    
    def add_document(self, file_path: str) -> Dict[str, Any]:
        """添加单个文档到知识库"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            if not os.path.exists(file_path):
                return {"success": False, "message": f"文件不存在: {file_path}"}
            
            # 创建文档处理器
            processor = DocumentProcessor(
                chunk_size=Config.DOC_CHUNK_SIZE,
                chunk_overlap=Config.DOC_CHUNK_OVERLAP
            )
            
            # 处理单个文件
            doc = processor.process_single_file(file_path)
            if not doc or not doc.get('chunks'):
                return {"success": False, "message": "文档处理失败，未生成文本块"}
            
            # 生成向量并存储
            chunks = []
            metadata_list = []
            
            for chunk_info in doc['chunks']:
                chunks.append(chunk_info['text'])
                metadata_list.append({
                    'file_name': doc['file_name'],
                    'chunk_text': chunk_info['text'],
                    'chunk_index': chunk_info['metadata']['chunk_index'],
                    'total_chunks': chunk_info['metadata']['total_chunks']
                })
            
            if chunks:
                embeddings = self.embedding_manager.get_embeddings_as_list(chunks)
                self.vector_store.add_vectors(embeddings, metadata_list)
                self.vector_store.save_data()
                logger.info(f"Document '{doc['file_name']}' added successfully with {len(chunks)} chunks")
                return {
                    "success": True,
                    "message": f"文档 '{doc['file_name']}' 添加成功",
                    "file_name": doc['file_name'],
                    "chunk_count": len(chunks)
                }
            else:
                return {"success": False, "message": "未生成文本块，无法添加文档"}
                
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            return {"success": False, "message": f"添加文档时出错: {str(e)}"}
    
    def search(self, question: str, top_k: int = 3, use_rerank: bool = True) -> Dict[str, Any]:
        """统一的检索API，供外部调用"""
        try:
            if not self.ensure_initialized():
                return {"success": False, "message": "组件初始化失败"}
            
            # 调用核心检索方法
            result = self.retrieval_engine.search(question, top_k, use_rerank)
            
            return {
                "success": True,
                "question": question,
                "documents": result.get("documents", []),
                "has_results": result.get("has_results", False)
            }
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return {"success": False, "message": f"搜索时出错: {str(e)}"}

# 全局知识库服务实例
_kb_server_instance = None

def get_kb_server() -> KnowledgeBaseServer:
    """获取知识库服务单例"""
    global _kb_server_instance
    if _kb_server_instance is None:
        # 创建实例但不立即初始化组件
        _kb_server_instance = KnowledgeBaseServer()
    return _kb_server_instance

def initialize_kb_server_after_model():
    """在ModelManager初始化完成后初始化知识库服务"""
    global _kb_server_instance
    if _kb_server_instance is not None:
        logger.info("Attempting to initialize KnowledgeBaseServer after ModelManager")
        _kb_server_instance.ensure_initialized()