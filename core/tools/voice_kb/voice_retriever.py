import logging
from typing import Dict, List, Any
from config import Config
from core.tools.voice_kb.voice_data_manager import get_voice_data_manager

logger = logging.getLogger(__name__)

class VoiceRetriever:
    """语音检索引擎 - 支持文本匹配和语义搜索"""

    def __init__(self):
        self.voice_data_manager = get_voice_data_manager()
        self.embedding_enabled = Config.EMBEDDING_MODEL_ENABLED and Config.KNOWLEDGE_BASE_ENABLED
        self.retrieval_engine = None
        self.voice_vector_index_built = False

        if self.embedding_enabled:
            self._initialize_embedding_components()

    def _initialize_embedding_components(self):
        """初始化embedding组件"""
        try:
            from core.embedding.retrieval_engine import RetrievalEngine
            from core.embedding.embedding_manager import EmbeddingManager
            from core.embedding.vector_store import VectorStore
            from core.model_manager import ModelManager

            self.embedding_manager = EmbeddingManager(Config.EMBEDDING_MODEL_DIR)
            self.vector_store = VectorStore(Config.VECTOR_DB_PATH)

            reranker = ModelManager.get_reranker()
            self.retrieval_engine = RetrievalEngine(
                self.embedding_manager,
                self.vector_store,
                reranker=reranker
            )

            logger.info("Voice retrieval engine initialized with embedding support")

        except Exception as e:
            logger.error(f"Failed to initialize embedding components: {e}")
            self.embedding_enabled = False

    def _build_voice_vector_index(self):
        """为voice数据建立向量索引，同时索引英文提问和中文翻译"""
        if self.voice_vector_index_built or not self.embedding_enabled:
            return

        try:
            # 清理现有的向量数据库中可能存在的语音数据
            self._clear_existing_voice_data()

            # 确保数据管理器已初始化
            if not self.voice_data_manager.ensure_initialized():
                logger.warning("Cannot build voice vector index: data manager not initialized")
                return

            import uuid

            documents = []

            for voice_id, voice_entry in self.voice_data_manager.voice_index.items():
                # 为英文提问建立索引
                english_question = voice_entry.get("english_question", "")
                if english_question:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "content": english_question,
                        "metadata": {
                            "voice_id": voice_id,
                            "audio_file": voice_entry["audio_file"],
                            "response": voice_entry.get("response", ""),
                            "chinese_response": voice_entry.get("chinese_response", ""),
                            "question_type": "english"
                        }
                    }
                    documents.append(doc)

                # 为中文翻译建立索引
                chinese_question = voice_entry.get("chinese_question", "")
                if chinese_question:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "content": chinese_question,
                        "metadata": {
                            "voice_id": voice_id,
                            "audio_file": voice_entry["audio_file"],
                            "response": voice_entry.get("response", ""),
                            "chinese_response": voice_entry.get("chinese_response", ""),
                            "question_type": "chinese"
                        }
                    }
                    documents.append(doc)

            if documents:
                # 直接为语音数据建立向量索引
                self._build_voice_vector_index_direct(documents)

                self.voice_vector_index_built = True
                logger.info(f"Built voice vector index with {len(documents)} entries (english + chinese)")

        except Exception as e:
            logger.error(f"Failed to build voice vector index: {e}")
            self.embedding_enabled = False

    def _build_voice_vector_index_direct(self, documents: List[Dict]):
        """直接为语音数据建立向量索引"""
        try:
            # 准备文本和元数据
            texts = [doc["content"] for doc in documents]
            metadata_list = []

            for doc in documents:
                # 构建符合VectorStore期望格式的metadata
                metadata = {
                    "file_name": doc["metadata"]["audio_file"],  # 使用audio_file作为file_name
                    "voice_id": doc["metadata"]["voice_id"],
                    "audio_file": doc["metadata"]["audio_file"],
                    "response": doc["metadata"]["response"],
                    "chinese_response": doc["metadata"]["chinese_response"],
                    "question_type": doc["metadata"]["question_type"],
                    "chunk_text": doc["content"]  # VectorStore需要这个字段
                }
                metadata_list.append(metadata)

            # 获取embedding向量
            embeddings = self.embedding_manager.get_embeddings(texts)

            # 添加到向量存储
            self.retrieval_engine.vector_store.add_vectors(embeddings.tolist(), metadata_list)

            logger.info(f"Successfully added {len(documents)} voice entries to vector index")

        except Exception as e:
            logger.error(f"Failed to build direct voice vector index: {e}")
            raise

    def _clear_existing_voice_data(self):
        """清理现有的语音向量数据"""
        try:
            # 获取向量库统计信息
            stats = self.retrieval_engine.vector_store.get_stats()

            if stats.get("total_vectors", 0) > 0:
                logger.info(f"Clearing existing vector database with {stats['total_vectors']} vectors")

                # 直接删除整个集合并重新创建
                client = self.retrieval_engine.vector_store.client

                # 删除现有的集合
                try:
                    client.delete_collection("documents")
                    logger.info("Deleted existing collection")
                except:
                    logger.warning("Collection might not exist, continuing...")

                # 重新创建集合
                self.retrieval_engine.vector_store.collection = client.get_or_create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"}
                )

                logger.info("Successfully cleared and recreated vector database")

        except Exception as e:
            logger.warning(f"Failed to clear existing voice data: {e}")

    def search_voice(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """搜索语音，使用embedding语义匹配"""
        try:
            # 确保数据管理器已初始化
            if not self.voice_data_manager.ensure_initialized():
                logger.warning("Failed to initialize voice data manager")
                return {
                    "success": False,
                    "error": "Failed to initialize voice data manager",
                    "results": []
                }

            # 获取所有可用语音
            voice_entries = list(self.voice_data_manager.voice_index.values())

            if not voice_entries:
                logger.warning("No voice entries available")
                return {
                    "success": False,
                    "error": "No voice entries available",
                    "results": []
                }

            # 检查embedding组件是否可用
            if not self.embedding_enabled or not self.retrieval_engine:
                logger.warning("Embedding components not available")
                return {
                    "success": True,
                    "method": "semantic_match",
                    "results": [],
                    "max_score": 0.0
                }

            # 构建向量索引（如果尚未建立）
            self._build_voice_vector_index()

            if not self.voice_vector_index_built:
                logger.warning("Voice vector index not built")
                return {
                    "success": True,
                    "method": "semantic_match",
                    "results": [],
                    "max_score": 0.0
                }

            # 使用embedding进行语义搜索
            results = self._embedding_search(query, top_k)

            max_score = results[0]["score"] if results else 0.0
            logger.info(f"Semantic match completed, best score: {max_score:.3f}")

            return {
                "success": True,
                "method": "semantic_match",
                "results": results,
                "max_score": max_score
            }

        except Exception as e:
            logger.error(f"Voice search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    def _embedding_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """使用embedding进行语义搜索"""
        try:
            # 使用检索引擎进行语义搜索
            result = self.retrieval_engine.retrieve_documents(query, top_k=top_k, use_rerank=True)

            if not result.get("has_results"):
                return []

            documents = result.get("documents", [])

            # 转换语义搜索结果为语音结果
            voice_results = []
            for doc in documents:
                # 从metadata中获取voice_id
                metadata = doc.get('metadata', {})
                voice_id = metadata.get('voice_id')

                if voice_id is not None and voice_id in self.voice_data_manager.voice_index:
                    voice_entry = self.voice_data_manager.voice_index[voice_id]
                    similarity_score = doc.get('score', 0.0)

                    voice_results.append({
                        "voice_id": voice_id,
                        "score": float(similarity_score),
                        "entry": voice_entry
                    })

            return sorted(voice_results, key=lambda x: x["score"], reverse=True)[:top_k]

        except Exception as e:
            logger.error(f"Embedding search failed: {e}")
            return []

    def _convert_semantic_to_voice_results(self, semantic_docs: List[Dict]) -> List[Dict[str, Any]]:
        """将语义搜索结果转换为语音结果格式"""
        voice_results = []

        for doc in semantic_docs:
            # 尝试从文档内容中匹配语音条目
            doc_content = doc.get('chunk_text', '')

            # 在语音数据中查找匹配的条目
            for voice_id, entry in self.voice_data_manager.voice_index.items():
                search_field = entry["chinese_question"] if Config.ANY4DH_VOICE_KB_LANGUAGE == "zh" else entry["english_question"]

                # 计算相似度（简单的字符串包含匹配）
                if doc_content in search_field or search_field in doc_content:
                    score = len(doc_content) / max(len(search_field), len(doc_content))
                    voice_results.append({
                        "voice_id": voice_id,
                        "score": score,
                        "entry": entry
                    })
                    break  # 每个文档只匹配一个语音条目

        return voice_results[:3]  # 限制返回数量

    def get_voice_categories(self) -> List[str]:
        """获取语音分类列表"""
        return self.voice_data_manager.get_categories()

    def search_by_category(self, category: str, query: str = "", top_k: int = 5) -> Dict[str, Any]:
        """按分类搜索语音"""
        try:
            results = self.voice_data_manager.search_by_category(category, query, top_k)
            return {
                "success": True,
                "category": category,
                "results": results,
                "total": len(results)
            }
        except Exception as e:
            logger.error(f"Category search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

# 全局实例
_voice_retriever = None

def get_voice_retriever() -> VoiceRetriever:
    """获取语音检索引擎单例"""
    global _voice_retriever
    if _voice_retriever is None:
        _voice_retriever = VoiceRetriever()
    return _voice_retriever