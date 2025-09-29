import requests
import json
from typing import List, Dict, Any, Tuple
from config import Config
from embedding_manager import EmbeddingManager
from vector_store import VectorStore

class RetrievalEngine:
    def __init__(self, embedding_manager: EmbeddingManager, vector_store: VectorStore):
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
    
    def query(self, prompt: str, model: str = None, system_prompt: str = None) -> str:
        """查询OpenAI兼容的模型API"""
        url = f"http://{Config.HOST}:{Config.PORT}/v1/chat/completions"
        if model is None:
            model = Config.LLM_MODEL_NAME
        
        # 构建OpenAI兼容的消息格式
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            # OpenAI的响应结构中，内容在choices[0].message.content中
            if result.get("choices") and len(result["choices"]) > 0:
                return result["choices"][0].get("message", {}).get("content", "抱歉，我没有得到有效的回复。")
            return "抱歉，我没有得到有效的回复。"
        except requests.exceptions.RequestException as e:
            return f"请求API时出错: {e}"
        except json.JSONDecodeError as e:
            return f"解析响应时出错: {e}"
    
    def retrieve_and_answer(self, question: str, top_k: int = None) -> Dict[str, Any]:
        """检索相关信息并生成回答"""
        if top_k is None:
            top_k = Config.TOP_K
        print(f"正在处理问题: {question}")
        
        # 1. 将问题转换为向量
        print("正在生成问题向量...")
        question_embedding = self.embedding_manager.get_single_embedding(question)
        
        # 2. 在向量库中搜索相似内容
        print("正在检索相似内容...")
        similar_docs = self.vector_store.search_similar(question_embedding, top_k=top_k)
        
        if not similar_docs:
            return {
                "answer": "知识库中没有找到相关信息。",
                "sources": [],
                "question": question
            }
        
        # 3. 构建上下文
        context = "以下是从知识库中检索到的相关信息：\n\n"
        sources = []
        
        for score, metadata in similar_docs:
            context += f"文档: {metadata['file_name']}\n"
            context += f"内容: {metadata['chunk_text']}\n\n"
            sources.append({
                "file_name": metadata['file_name'],
                "chunk_text": metadata['chunk_text'],
                "score": float(score)
            })
        
        # 4. 构建提示词
        system_prompt = """你是一个专业的助手，请根据提供的上下文信息回答问题。
        如果上下文中有答案，请基于上下文回答。
        如果上下文中没有足够的信息，请如实告知，不要编造信息。"""
        
        prompt = f"{context}\n问题：{question}\n请根据以上信息回答："
        
        # 5. 调用LLM生成回答
        print("正在生成回答...")
        answer = self.query(prompt, "qwen3:1.7b", system_prompt)
        
        return {
            "answer": answer,
            "sources": sources,
            "question": question
        }
    
    def simple_search(self, question: str, top_k: int = None) -> List[Tuple[float, Dict[str, Any]]]:
        if top_k is None:
            top_k = Config.TOP_K
        """只进行向量搜索，不生成回答"""
        question_embedding = self.embedding_manager.get_single_embedding(question)
        return self.vector_store.search_similar(question_embedding, top_k=top_k)