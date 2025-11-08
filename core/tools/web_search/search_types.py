"""
Web搜索工具数据类型定义
"""
from dataclasses import dataclass
from typing import List, Optional
import json


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str           # 标题
    url: str            # URL链接
    description: str    # 摘要描述
    source: str         # 来源网站
    engine: str         # 搜索引擎（固定为"bing"）

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "source": self.source,
            "engine": self.engine
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SearchResult':
        """从字典创建SearchResult实例"""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            description=data.get("description", ""),
            source=data.get("source", ""),
            engine=data.get("engine", "bing")
        )


@dataclass
class SearchResponse:
    """搜索响应数据结构"""
    success: bool           # 搜索是否成功
    query: str             # 搜索查询
    tool_name: str         # 工具名称
    total_results: int     # 结果总数
    results: List[SearchResult]  # 搜索结果列表
    response_time: str     # 响应时间
    error_message: Optional[str] = None  # 错误信息

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "success": self.success,
            "query": self.query,
            "tool_name": self.tool_name,
            "total_results": self.total_results,
            "results": [result.to_dict() for result in self.results],
            "response_time": self.response_time,
            "error_message": self.error_message
        }

    @classmethod
    def success_response(cls, query: str, results: List[SearchResult], response_time: str) -> 'SearchResponse':
        """创建成功响应"""
        return cls(
            success=True,
            query=query,
            tool_name="web_search",
            total_results=len(results),
            results=results,
            response_time=response_time
        )

    @classmethod
    def error_response(cls, query: str, error_message: str, response_time: str) -> 'SearchResponse':
        """创建错误响应"""
        return cls(
            success=False,
            query=query,
            tool_name="web_search",
            total_results=0,
            results=[],
            response_time=response_time,
            error_message=error_message
        )


# 搜索意图关键词
SEARCH_INTENT_KEYWORDS = [
    # 搜索相关
    "搜索", "查找", "搜", "查一下", "找一找", "检索",
    # 实时信息
    "最新", "新闻", "当前", "现在", "实时", "近期", "近日",
    # 网络相关
    "网页", "网站", "网络", "网上", "在线", "互联网",
    # 信息查询
    "什么", "怎么样", "如何", "为什么", "哪里", "哪里有",
    # 英文搜索词
    "search", "find", "look for", "google", "bing", "web"
]

# SQL查询排除词（避免与NL2SQL工具冲突）
SQL_EXCLUDE_KEYWORDS = [
    "数据库", "表", "记录", "字段", "查询", "统计", "多少", "几个",
    "总数", "平均", "最高", "最低", "列表", "table", "database", "record"
]

# 语音知识库排除词（避免与VoiceKB工具冲突）
VOICE_EXCLUDE_PATTERNS = [
    r"^[a-zA-Z\s]+$",  # 纯英文输入
    r"hello", r"hi", r"hey",  # 简单英文问候
]