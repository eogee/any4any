import logging
from typing import Dict, Any
from config import Config
from core.tools.voice_kb.voice_retriever import get_voice_retriever

logger = logging.getLogger(__name__)

class VoiceKBWorkflow:
    """语音知识库工作流程 - 参考nl2sql设计模式"""

    def __init__(self):
        self.voice_retriever = get_voice_retriever()

    async def process_voice_query(self, user_input: str) -> Dict[str, Any]:
        """
        处理语音查询的完整工作流程

        工作流程：
        1. 检查是否启用语音知识库
        2. 进行语音匹配搜索
        3. 评估匹配质量
        4. 返回语音文件信息
        """
        try:
            logger.info(f"Processing voice query: {user_input}")

            # 步骤2: 语音搜索
            search_result = self.voice_retriever.search_voice(user_input, top_k=1)

            if not search_result["success"]:
                logger.warning(f"Voice search failed: {search_result.get('error')}")
                return {
                    "success": False,
                    "message": "Voice search failed",
                    "should_use_voice": False,
                    "fallback_to_tts": Config.ANY4DH_VOICE_KB_FALLBACK_TO_TTS
                }

            results = search_result["results"]
            if not results:
                logger.info("No matching voice found")
                return {
                    "success": True,
                    "message": "No matching voice found",
                    "should_use_voice": False,
                    "confidence": 0.0,
                    "fallback_to_tts": Config.ANY4DH_VOICE_KB_FALLBACK_TO_TTS
                }

            # 步骤3: 选择最佳匹配并检查置信度
            best_match = results[0]
            confidence = best_match.get("score", 0.0)

            # 步骤4: 根据置信度决定是否使用语音回复
            should_use_voice = confidence >= Config.ANY4DH_VOICE_KB_SEMANTIC_THRESHOLD

            voice_info = None
            if should_use_voice:
                entry = best_match.get("entry", {})

                # 根据语言配置选择对应的文本
                if Config.ANY4DH_VOICE_KB_LANGUAGE == "zh":
                    question_text = entry.get("chinese_question", "")
                    response_text = entry.get("chinese_response", "")
                else:
                    question_text = entry.get("english_question", "")
                    response_text = entry.get("response", "")

                voice_info = {
                    "voice_id": entry.get("id"),
                    "audio_file": entry.get("audio_file"),
                    "audio_path": entry.get("audio_path"),
                    "question_text": question_text,
                    "response_text": response_text,
                    "category": entry.get("category"),
                    "background": entry.get("background"),
                    "confidence": confidence,
                    "search_method": search_result.get("method", "unknown")
                }

                logger.info(f"Voice match found: {voice_info['audio_file']} (confidence: {confidence:.3f})")

            return {
                "success": True,
                "should_use_voice": should_use_voice,
                "confidence": confidence,
                "voice_info": voice_info,
                "search_method": search_result.get("method", "unknown"),
                "fallback_to_tts": Config.ANY4DH_VOICE_KB_FALLBACK_TO_TTS,
                "threshold": Config.ANY4DH_VOICE_KB_SEMANTIC_THRESHOLD,
                "use_llm_fallback": not should_use_voice  # 当置信度低于阈值时使用LLM生成
            }

        except Exception as e:
            logger.error(f"Voice workflow processing failed: {e}")
            return {
                "success": False,
                "message": f"Workflow processing failed: {str(e)}",
                "should_use_voice": False,
                "fallback_to_tts": True
            }

    def is_voice_kb_question(self, question: str) -> bool:
        """
        判断问题是否适合使用语音知识库回复

        简化逻辑：只要启用了voice_kb且问题不为空就使用
        """
        return Config.ANY4DH_VOICE_KB_ENABLED and question and question.strip()

    def get_available_categories(self) -> Dict[str, Any]:
        """获取可用的语音分类"""
        try:
            categories = self.voice_retriever.get_voice_categories()
            return {
                "success": True,
                "categories": categories,
                "total": len(categories)
            }
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return {
                "success": False,
                "error": str(e),
                "categories": []
            }

    async def search_by_category(self, category: str, query: str = "") -> Dict[str, Any]:
        """按分类搜索语音"""
        try:
            if not Config.ANY4DH_VOICE_KB_ENABLED:
                return {
                    "success": False,
                    "message": "Voice knowledge base is disabled"
                }

            result = self.voice_retriever.search_by_category(category, query)
            return result

        except Exception as e:
            logger.error(f"Category search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

# 全局实例
_voice_workflow = None

def get_voice_workflow() -> VoiceKBWorkflow:
    """获取语音工作流程单例"""
    global _voice_workflow
    if _voice_workflow is None:
        _voice_workflow = VoiceKBWorkflow()
    return _voice_workflow