"""
语音知识库工具 - 整合检测、处理和执行逻辑
"""
import logging
from typing import Dict, Any, Optional, Callable

from config import Config
from ..base_tool import BaseTool
from ..result import ToolResult
from .voice_retriever import get_voice_retriever

logger = logging.getLogger(__name__)

class VoiceKBTool(BaseTool):
    """语音知识库工具 - 完整的语音查询检测、处理和执行"""

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self.voice_retriever = get_voice_retriever()

    @property
    def priority(self) -> int:
        return 2  # 中等优先级

    @property
    def name(self) -> str:
        return "voice_kb"

    @property
    def description(self) -> str:
        return "语音知识库查询工具，支持语义语音匹配和播放"

    async def can_handle(self, user_message: str) -> bool:
        """检测是否为英文输入 - VoiceKB主要用于英文内容响应"""
        if not user_message or not user_message.strip() or not self.enabled:
            return False

        # 检查配置
        if not Config.ANY4DH_VOICE_KB_ENABLED:
            return False

        # 检测输入是否包含英文内容
        return self._is_english_input(user_message)

    def _is_english_input(self, text: str) -> bool:
        """检测文本是否包含英文内容"""
        # 检查是否包含英文字母
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        total_chars = sum(1 for char in text if char.isalpha())

        # 如果英文字符占字母字符总数的50%以上，认为是英文输入
        if total_chars == 0:
            return False

        english_ratio = english_chars / total_chars
        return english_ratio >= 0.5

    async def process(self, user_message: str, generate_response_func: Callable,
                     conversation_manager=None, user_id: str = None,
                     platform: str = None) -> Optional[str]:
        """处理语音查询"""
        try:
            if not Config.ANY4DH_VOICE_KB_ENABLED:
                return None

            result = await self.process_voice_query(user_message)

            if result["success"] and result["should_use_voice"]:
                voice_info = result["voice_info"]
                if voice_info:
                    return f"[VOICE_KB_RESPONSE:{voice_info['audio_file']}:{voice_info['response_text']}]"
                else:
                    self.logger.warning("Voice info is empty, falling back to text")
                    return None
            else:
                self.logger.info(f"Voice KB not suitable: confidence={result.get('confidence', 0):.3f}")
                return None

        except Exception as e:
            self.logger.error(f"Voice KB processing failed: {e}")
            return None

    # 保持原有的工作流程方法
    async def process_voice_query(self, user_input: str) -> Dict[str, Any]:
        """原有的语音查询工作流程 - 保持不变"""
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
        """语音知识库问题检测（兼容原接口）"""
        import asyncio

        # 由于这是一个同步方法，我们需要运行异步的检测逻辑
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，创建任务
                task = asyncio.create_task(self.can_handle(question))
                return task
            else:
                # 如果没有运行的事件循环，直接运行
                return asyncio.run(self.can_handle(question))
        except Exception as e:
            self.logger.error(f"Voice KB question detection failed: {e}")
            return False

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行语音知识库工具方法（兼容原接口）"""
        try:
            operation = parameters.get("operation", "")
            query = parameters.get("query", "")

            if operation == "get_categories":
                categories = self.get_available_categories()
                return ToolResult.success_result(
                    data=categories,
                    tool_name=self.name,
                    metadata={"operation": "get_categories"}
                )

            elif operation == "search_by_category":
                category = parameters.get("category", "")
                if not category:
                    return ToolResult.error_result(
                        "缺少必需参数: category",
                        tool_name=self.name
                    )

                result = await self.search_by_category(category, query)
                return ToolResult.success_result(
                    data=result,
                    tool_name=self.name,
                    metadata={"operation": "search_by_category", "category": category}
                )

            elif operation == "voice_query":
                if not query:
                    return ToolResult.error_result(
                        "缺少必需参数: query",
                        tool_name=self.name
                    )

                result = await self.process_voice_query(query)
                return ToolResult.success_result(
                    data=result,
                    tool_name=self.name,
                    metadata={"operation": "voice_query"}
                )

            else:
                return ToolResult.error_result(
                    f"不支持的操作: {operation}",
                    tool_name=self.name
                )

        except Exception as e:
            self.logger.error(f"Voice KB tool execution failed: {e}")
            return ToolResult.error_result(
                f"语音知识库工具执行失败: {str(e)}",
                tool_name=self.name
            )

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

# 保持向后兼容的类和函数
class VoiceKBWorkflow(VoiceKBTool):
    """向后兼容的语音知识库工作流程类"""
    pass

# 工厂函数
def get_voice_kb_tool() -> VoiceKBTool:
    """获取语音知识库工具实例"""
    return VoiceKBTool()

def get_voice_workflow() -> VoiceKBWorkflow:
    """获取语音工作流程实例（向后兼容）"""
    return VoiceKBWorkflow()

# 保持原有的全局实例（向后兼容）
_voice_workflow = None

def get_voice_workflow_legacy() -> VoiceKBWorkflow:
    """获取语音工作流程单例（向后兼容）"""
    global _voice_workflow
    if _voice_workflow is None:
        _voice_workflow = VoiceKBWorkflow()
    return _voice_workflow