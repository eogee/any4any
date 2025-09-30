import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import logging
import argparse
import asyncio
from config import Config
from core.embedding.document_processor import DocumentProcessor
from core.embedding.embedding_manager import EmbeddingManager
from core.embedding.vector_store import VectorStore
from core.embedding.retrieval_engine import RetrievalEngine
from core.log import setup_logging
from core.model_manager import ModelManager

setup_logging()
logger = logging.getLogger(__name__)

class KnowledgeBaseTool:
    """本地知识库命令行工具"""
    def __init__(self):
        self.embedding_manager = None
        self.vector_store = None
        self.retrieval_engine = None
        # 仅在作为命令行工具直接运行时初始化，避免被导入时提前初始化
        if __name__ == '__main__':
            self._initialize_components()
    
    def _initialize_components(self):
        """初始化组件"""
        try:
            # 初始化嵌入管理器和向量存储
            self.embedding_manager = EmbeddingManager(Config.EMBEDDING_MODEL_DIR)
            self.vector_store = VectorStore(Config.VECTOR_DB_PATH)
            
            # 获取ModelManager中的重排序器
            reranker = ModelManager.get_reranker()
            
            # 只在重排序器不存在时才进行初始化
            if reranker is None:
                logger.info("Reranker not found, initializing ModelManager...")
                # 使用asyncio.run来运行异步初始化
                try:
                    # 检查是否已有事件循环
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环已在运行，创建新任务
                        asyncio.create_task(self._async_initialize_reranker())
                    else:
                        # 否则直接运行
                        asyncio.run(self._async_initialize_reranker())
                except RuntimeError:
                    # 如果没有事件循环，创建新的
                    asyncio.run(self._async_initialize_reranker())
                
                reranker = ModelManager.get_reranker()
                logger.info(f"Reranker initialized: {reranker is not None}")
            else:
                logger.info("Using existing reranker from ModelManager")
            
            # 创建检索引擎时传入重排序器
            self.retrieval_engine = RetrievalEngine(self.embedding_manager, self.vector_store, reranker=reranker)
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            sys.exit(1)
    
    async def _async_initialize_reranker(self):
        """异步初始化重排序器"""
        await ModelManager.initialize(load_llm=False, load_asr=False, load_tts=False, load_reranker=True)
    
    def build_kb(self, force_rebuild=False):
        """构建知识库"""
        # 检查是否已有数据
        stats = self.vector_store.get_stats()
        if not force_rebuild and stats['total_vectors'] > 0:
            logger.info("Knowledge base already exists. Use --force to rebuild.")
            return
        
        # 如果是强制重建，先清空集合
        if force_rebuild:
            try:
                # 重新创建集合以清空数据
                self.vector_store.client.delete_collection(name="documents")
                self.vector_store.collection = self.vector_store.client.create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Knowledge base collection has been rebuilt.")
            except Exception as e:
                logger.error(f"Failed to clear knowledge base collection: {e}")
        
        processor = DocumentProcessor(
            chunk_size=Config.DOC_CHUNK_SIZE,
            chunk_overlap=Config.DOC_CHUNK_OVERLAP
        )
        
        documents = processor.process_documents(Config.DOCS_PATH)
        
        if not documents:
            logger.info("No documents found in data/docs directory. Please add documents.")
            return
        
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
            # 使用专门为ChromaDB设计的方法获取列表格式的向量
            embeddings = self.embedding_manager.get_embeddings_as_list(all_chunks)
            self.vector_store.add_vectors(embeddings, all_metadata)
            self.vector_store.save_data()
            logger.info("Knowledge base has been built successfully.")
        else:
            logger.info("No chunks generated. Please check document processing.")
    
    def query(self, question: str, top_k: int = 3):
        """查询知识库"""
        stats = self.vector_store.get_stats()
        if stats['total_vectors'] == 0:
            logger.info("Knowledge base is empty. Please build the knowledge base first.")
            return
        
        result = self.retrieval_engine.retrieve_documents(question, top_k)
        
        print(f"\nQuery: {result['question']}")
        
        if result['has_results']:
            print(f"\nFound {len(result['documents'])} relevant documents:\n")
            for i, doc in enumerate(result['documents'], 1):
                print(f"{i}. File: {doc['file_name']}")
                print(f"   Similarity: {doc['score']:.3f}")
                print(f"   Content: {doc['chunk_text'][:200]}...\n")
        else:
            print("\nNo relevant documents found.")
    
    def search(self, question: str, top_k: int = 5):
        """只搜索不生成回答"""
        stats = self.vector_store.get_stats()
        if stats['total_vectors'] == 0:
            logger.info("Knowledge base is empty. Please build the knowledge base first.")    
            return
        
        results = self.retrieval_engine.simple_search(question, top_k)
        
        print(f"\nSearch query: {question}")
        print(f"Found {len(results)} relevant results:\n")
        
        for i, (score, metadata) in enumerate(results, 1):
            print(f"{i}. File: {metadata['file_name']}")
            print(f"   Similarity: {score:.3f}")
            print(f"   Content: {metadata['chunk_text'][:150]}...")
            print("")
    
    def stats(self):
        """显示知识库统计信息"""
        stats = self.vector_store.get_stats()
        print("Knowledge base statistics:")
        print(f"  Total vectors: {stats['total_vectors']}")
        print(f"  Total files: {stats['total_files']}")
        print(f"  File list: {', '.join(stats['files'])}")
    
    def delete_file(self, file_name: str):
        """删除指定文件的所有向量"""
        if self.vector_store.delete_file_vectors(file_name):
            self.vector_store.save_data()
            print(f"Deleted all vectors for file '{file_name}'")
        else:
            print(f"File '{file_name}' not found in knowledge base")

def main():
    parser = argparse.ArgumentParser(description="本地知识库命令行工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    build_parser = subparsers.add_parser('build', help='构建知识库')
    build_parser.add_argument('--force', action='store_true', help='强制重建知识库')

    query_parser = subparsers.add_parser('query', help='查询知识库')
    query_parser.add_argument('question', help='要查询的问题')
    query_parser.add_argument('--top-k', type=int, default=3, help='返回的最相关文档数量')
    
    search_parser = subparsers.add_parser('search', help='只搜索不生成回答')
    search_parser.add_argument('question', help='要搜索的问题')
    search_parser.add_argument('--top-k', type=int, default=5, help='返回的最相关文档数量')
    
    subparsers.add_parser('stats', help='显示知识库统计信息')
    
    delete_parser = subparsers.add_parser('delete', help='删除指定文件的所有向量')
    delete_parser.add_argument('file_name', help='要删除的文件名')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tool = KnowledgeBaseTool()
    # 显式初始化组件，因为构造函数不再自动初始化
    tool._initialize_components()
    
    try:
        if args.command == 'build':
            tool.build_kb(force_rebuild=args.force)
        elif args.command == 'query':
            tool.query(args.question, top_k=args.top_k)
        elif args.command == 'search':
            tool.search(args.question, top_k=args.top_k)
        elif args.command == 'stats':
            tool.stats()
        elif args.command == 'delete':
            tool.delete_file(args.file_name)
    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
    except Exception as e:
        logger.error(f"Error during command execution: {e}")

if __name__ == "__main__":
    main()