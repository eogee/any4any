import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse
from config import Config
from core.embedding.document_processor import DocumentProcessor
from core.embedding.embedding_manager import EmbeddingManager
from core.embedding.vector_store import VectorStore
from core.embedding.retrieval_engine import RetrievalEngine

class KnowledgeBaseTool:
    def __init__(self):
        # 目录创建已在config.py中自动处理
        self.embedding_manager = None
        self.vector_store = None
        self.retrieval_engine = None
        self._initialize_components()
    
    def _initialize_components(self):
        """初始化组件"""
        try:
            self.embedding_manager = EmbeddingManager(Config.EMBEDDING_MODEL_DIR)
            self.vector_store = VectorStore(Config.VECTOR_DB_PATH)
            self.retrieval_engine = RetrievalEngine(self.embedding_manager, self.vector_store)
        except Exception as e:
            print(f"初始化组件失败: {e}")
            sys.exit(1)
    
    def build_kb(self, force_rebuild=False):
        """构建知识库"""
        print("开始构建知识库...")
        
        if not force_rebuild and len(self.vector_store.vectors) > 0:
            print("知识库已存在，使用 --force 参数强制重建")
            return
        
        processor = DocumentProcessor(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP
        )
        
        documents = processor.process_documents(Config.DOCS_PATH)
        
        if not documents:
            print("没有找到可处理的文档，请将文档放入 ./docs 目录")
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
            print(f"正在为 {len(all_chunks)} 个文本块生成向量...")
            embeddings = self.embedding_manager.get_embeddings(all_chunks)
            self.vector_store.add_vectors(embeddings, all_metadata)
            self.vector_store.save_data()
            print("知识库构建完成！")
        else:
            print("没有生成任何文本块")
    
    def query(self, question: str, top_k: int = 3):
        """查询知识库"""
        if len(self.vector_store.vectors) == 0:
            print("知识库为空，请先构建知识库")
            return
        
        result = self.retrieval_engine.retrieve_and_answer(question, top_k)
        
        print(f"\n问题: {result['question']}")
        print(f"\n回答: {result['answer']}")
        
        if result['sources']:
            print(f"\n参考来源 (共 {len(result['sources'])} 个):")
            for i, source in enumerate(result['sources'], 1):
                print(f"\n{i}. 文件: {source['file_name']}")
                print(f"   相似度: {source['score']:.3f}")
                print(f"   内容: {source['chunk_text'][:200]}...")
    
    def search(self, question: str, top_k: int = 5):
        """只搜索不生成回答"""
        if len(self.vector_store.vectors) == 0:
            print("知识库为空，请先构建知识库")
            return
        
        results = self.retrieval_engine.simple_search(question, top_k)
        
        print(f"\n搜索查询: {question}")
        print(f"找到 {len(results)} 个相关结果:\n")
        
        for i, (score, metadata) in enumerate(results, 1):
            print(f"{i}. 文件: {metadata['file_name']}")
            print(f"   相似度: {score:.3f}")
            print(f"   内容: {metadata['chunk_text'][:150]}...")
            print()
    
    def stats(self):
        """显示知识库统计信息"""
        stats = self.vector_store.get_stats()
        print("知识库统计信息:")
        print(f"  总向量数: {stats['total_vectors']}")
        print(f"  总文件数: {stats['total_files']}")
        print(f"  文件列表: {', '.join(stats['files'])}")
    
    def delete_file(self, file_name: str):
        """删除指定文件的所有向量"""
        if self.vector_store.delete_file_vectors(file_name):
            self.vector_store.save_data()
            print(f"已删除文件 '{file_name}' 的所有向量")
        else:
            print(f"未找到文件 '{file_name}'")

def main():
    parser = argparse.ArgumentParser(description="本地知识库命令行工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # build 命令
    build_parser = subparsers.add_parser('build', help='构建知识库')
    build_parser.add_argument('--force', action='store_true', help='强制重建知识库')
    
    # query 命令
    query_parser = subparsers.add_parser('query', help='查询知识库')
    query_parser.add_argument('question', help='要查询的问题')
    query_parser.add_argument('--top-k', type=int, default=3, help='返回的最相关文档数量')
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='只搜索不生成回答')
    search_parser.add_argument('question', help='要搜索的问题')
    search_parser.add_argument('--top-k', type=int, default=5, help='返回的最相关文档数量')
    
    # stats 命令
    subparsers.add_parser('stats', help='显示知识库统计信息')
    
    # delete 命令
    delete_parser = subparsers.add_parser('delete', help='删除指定文件的所有向量')
    delete_parser.add_argument('file_name', help='要删除的文件名')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tool = KnowledgeBaseTool()
    
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
        print("\n操作被用户中断")
    except Exception as e:
        print(f"执行命令时出错: {e}")

if __name__ == "__main__":
    main()