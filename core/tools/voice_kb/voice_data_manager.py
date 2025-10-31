import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from config import Config
import pandas as pd

logger = logging.getLogger(__name__)

class VoiceDataManager:
    """语音数据管理器"""

    def __init__(self):
        self.voice_index = {}
        self.category_index = {}
        self.initialized = False
        self._load_attempted = False

    def ensure_initialized(self):
        """确保数据已加载"""
        if not self.initialized and not self._load_attempted:
            self._load_voice_data()
            self._load_attempted = True
        return self.initialized

    def _load_voice_data(self):
        """加载CSV数据并建立索引"""
        try:
            csv_path = Path(Config.VOICE_KB_CSV_PATH)
            audio_dir = Path(Config.VOICE_KB_AUDIO_DIR)

            if not csv_path.exists():
                logger.error(f"Voice CSV file not found: {csv_path}")
                return

            # 读取UTF-8编码的CSV文件
            df = pd.read_csv(csv_path, encoding='utf-8')

            loaded_count = 0
            for idx, row in df.iterrows():
                audio_file = f"row_{idx}_{idx}.mp3"
                audio_path = audio_dir / audio_file

                if not audio_path.exists():
                    logger.warning(f"Audio file not found: {audio_path}")
                    continue

                # 根据语言配置选择对应的问题字段
                if Config.ANY4DH_VOICE_KB_LANGUAGE == "zh":
                    question_key = "提问翻译"  # 中文问题
                else:
                    question_key = "英文提问"  # 英文问题

                voice_entry = {
                    "id": idx,
                    "question": row[question_key],
                    "english_question": row["英文提问"],
                    "chinese_question": row["提问翻译"],
                    "response": row["英文响应"],
                    "chinese_response": row["响应翻译"],
                    "category": row["分类"],
                    "background": row["背景说明"],
                    "audio_file": audio_file,
                    "audio_path": str(audio_path),
                    "exists": True
                }

                self.voice_index[idx] = voice_entry

                # 建立分类索引
                category = row["分类"]
                if category not in self.category_index:
                    self.category_index[category] = []
                self.category_index[category].append(voice_entry)

                loaded_count += 1

            self.initialized = True
            logger.info(f"Loaded {loaded_count} voice entries from {len(df)} CSV rows")

        except Exception as e:
            logger.error(f"Failed to load voice data: {e}")

    def search_by_text(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """基于文本内容搜索语音"""
        if not self.ensure_initialized():
            return []

        # 简单的关键词匹配
        results = []
        query_lower = query.lower()

        for voice_id, entry in self.voice_index.items():
            # 根据语言配置搜索对应的问题字段
            search_field = entry["chinese_question"] if Config.ANY4DH_VOICE_KB_LANGUAGE == "zh" else entry["english_question"]

            # 计算简单匹配度
            if query_lower in search_field.lower():
                score = len(query_lower) / len(search_field.lower())
                results.append({
                    "voice_id": voice_id,
                    "score": score,
                    "entry": entry
                })
            elif any(word in search_field.lower() for word in query_lower.split()):
                # 部分词汇匹配
                match_words = sum(1 for word in query_lower.split() if word in search_field.lower())
                score = match_words / len(query_lower.split()) * 0.7  # 降低部分匹配的分数
                results.append({
                    "voice_id": voice_id,
                    "score": score,
                    "entry": entry
                })

        # 按分数排序并返回top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_voice_by_id(self, voice_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取语音信息"""
        if not self.ensure_initialized():
            return None
        return self.voice_index.get(voice_id)

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        if not self.ensure_initialized():
            return []
        return list(self.category_index.keys())

    def search_by_category(self, category: str, query: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
        """根据分类搜索语音"""
        if not self.ensure_initialized() or category not in self.category_index:
            return []

        category_entries = self.category_index[category]

        if not query:
            # 如果没有查询，返回分类下的所有语音
            return [{"voice_id": entry["id"], "score": 1.0, "entry": entry} for entry in category_entries[:top_k]]

        # 在分类内搜索
        results = []
        query_lower = query.lower()

        for entry in category_entries:
            search_field = entry["chinese_question"] if Config.ANY4DH_VOICE_KB_LANGUAGE == "zh" else entry["english_question"]

            if query_lower in search_field.lower():
                score = len(query_lower) / len(search_field.lower())
                results.append({
                    "voice_id": entry["id"],
                    "score": score,
                    "entry": entry
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

# 全局实例
_voice_data_manager = None

def get_voice_data_manager() -> VoiceDataManager:
    """获取语音数据管理器单例"""
    global _voice_data_manager
    if _voice_data_manager is None:
        _voice_data_manager = VoiceDataManager()
    return _voice_data_manager