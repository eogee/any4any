import logging
import time
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SQLContextManager:
    """SQL查询上下文管理器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_context_length = 2000  # 上下文最大字符数
        self.max_history_items = 5     # 最大历史记录数
        self.context_keywords = [
            '查询', '统计', '计算', '显示', '列出', '多少', '几个', '总数', '平均',
            '最高', '最低', '最大', '最小', '排序', '分组', '汇总', '数据', '记录',
            '表', '字段', '数据库', 'SELECT', 'FROM', 'WHERE', 'COUNT', 'SUM', 'AVG',
            'MAX', 'MIN', 'ORDER BY', 'GROUP BY', '产品', '商品', '订单', '库存',
            'sql', 'SQL', '数据库', '表格', '查询结果'
        ]
        # 预编译正则表达式以提高性能
        self.data_patterns = [
            re.compile(r'多少.*?个'), re.compile(r'总数.*?是'), re.compile(r'平均.*?是'), re.compile(r'最高.*?是'),
            re.compile(r'列表.*?显示'), re.compile(r'统计.*?数据'), re.compile(r'查询.*?信息')
        ]

    def _calculate_relevance_score(self, message: str, current_question: str) -> float:
        """
        计算消息与当前问题的相关性得分

        Args:
            message: 历史消息内容
            current_question: 当前用户问题

        Returns:
            相关性得分 (0-1)
        """
        if not message or not current_question:
            return 0.0

        message_lower = message.lower()
        question_lower = current_question.lower()

        # 时间衰减因子（越近的消息权重越高）
        time_score = 1.0
        message_words = set(message_lower.split())
        question_words = set(question_lower.split())

        # 1. 关键词匹配得分 (权重: 0.6)
        keyword_matches = len(message_words & question_words)
        keyword_score = min(keyword_matches / len(question_words), 1.0) * 0.6 if question_words else 0.0

        # 2. 内容长度惩罚 (避免过长消息) (权重: 0.2)
        length_penalty = max(0, 1 - len(message) / 500) * 0.2

        # 3. SQL相关词汇得分 (权重: 0.2)
        sql_keywords_in_message = sum(1 for keyword in self.context_keywords if keyword in message_lower)
        sql_score = min(sql_keywords_in_message / 10, 1.0) * 0.2

        total_score = (keyword_score + length_penalty + sql_score) * time_score
        return min(max(total_score, 0.0), 1.0)

    def _format_context_message(self, message: Dict[str, Any]) -> str:
        """
        格式化上下文消息

        Args:
            message: 消息字典对象

        Returns:
            格式化后的字符串
        """
        timestamp = message.get('timestamp', '')
        sender_type = message.get('sender_type', 'unknown')
        content = message.get('content', '')

        # 格式化时间戳
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    # 尝试解析ISO格式时间
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%m-%d %H:%M')
                else:
                    formatted_time = str(timestamp)
            except:
                formatted_time = str(timestamp)
        else:
            formatted_time = '未知时间'

        sender_label = "用户" if sender_type == 'user' else "助手"

        return f"[{formatted_time}] {sender_label}: {content}"

    def _truncate_context(self, context: str) -> str:
        """
        截断上下文以适应最大长度限制

        Args:
            context: 原始上下文

        Returns:
            截断后的上下文
        """
        if len(context) <= self.max_context_length:
            return context

        # 智能截断：在句子边界处截断
        truncated = context[:self.max_context_length]

        # 找到最后一个完整句子
        last_punctuation = max(
            truncated.rfind('。'),
            truncated.rfind('！'),
            truncated.rfind('？'),
            truncated.rfind('.'),
            truncated.rfind('!')
        )

        if last_punctuation > self.max_context_length * 0.8:
            return truncated[:last_punctuation + 1]

        return truncated + "..."

    async def get_sql_conversation_history(
        self,
        conversation_manager,
        user_id: str,
        platform: str = None,
        limit: int = None,
        hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """
        获取SQL相关的对话历史

        Args:
            conversation_manager: 对话管理器实例
            user_id: 用户ID
            platform: 平台标识
            limit: 返回记录数限制
            hours_back: 查询时间范围（小时）

        Returns:
            SQL相关的对话历史列表
        """
        try:
            # 获取对话ID
            conversation_ids = self._get_user_conversation_ids(
                conversation_manager, user_id, platform, hours_back
            )

            if not conversation_ids:
                self.logger.info(f"No conversations found for user {user_id}")
                return []

            # 获取消息历史
            all_messages = []
            for conv_id in conversation_ids:
                messages = self._get_conversation_messages(
                    conversation_manager, conv_id
                )
                if messages:
                    all_messages.extend(messages)

            # 过滤SQL相关消息
            sql_messages = self._filter_sql_related_messages(all_messages)

            # 按时间排序
            sql_messages.sort(key=lambda x: x.get('timestamp', ''))

            # 限制返回数量
            if limit:
                sql_messages = sql_messages[-limit:] if len(sql_messages) > limit else sql_messages

            self.logger.info(f"Found {len(sql_messages)} SQL-related messages for user {user_id}")
            return sql_messages

        except Exception as e:
            self.logger.error(f"Error getting SQL conversation history: {e}")
            return []

    def _get_user_conversation_ids(self, conversation_manager, user_id: str, platform: str, hours_back: int) -> List[str]:
        """获取用户的对话ID列表"""
        try:
            # 使用ConversationDatabase获取用户对话
            db = conversation_manager.db
            if not db:
                return []

            # 查询对话ID
            time_threshold = datetime.now() - timedelta(hours=hours_back)

            # 根据实际数据库表结构查询用户对话
            if platform:
                query = """
                    SELECT conversation_id, last_active
                    FROM conversations
                    WHERE sender = %s
                    AND last_active >= %s
                    AND platform = %s
                    GROUP BY conversation_id, last_active
                    ORDER BY last_active DESC
                """
                params = [user_id, time_threshold, platform]
            else:
                query = """
                    SELECT conversation_id, last_active
                    FROM conversations
                    WHERE sender = %s
                    AND last_active >= %s
                    GROUP BY conversation_id, last_active
                    ORDER BY last_active DESC
                """
                params = [user_id, time_threshold]

            # 执行查询
            result = db.fetch_all(query, tuple(params))

            if not result:
                return []

            # 提取对话ID
            conversation_ids = [row['conversation_id'] for row in result]
            return conversation_ids

        except Exception as e:
            self.logger.error(f"Error getting conversation IDs: {e}")
            return []

    def _get_conversation_messages(self, conversation_manager, conversation_id: str) -> List[Dict[str, Any]]:
        """获取对话的消息历史"""
        try:
            conversation = conversation_manager.db.get_conversation_by_id(conversation_id)
            if conversation and 'messages' in conversation:
                return conversation['messages']
            return []
        except Exception as e:
            self.logger.error(f"Error getting conversation messages: {e}")
            return []

    def _filter_sql_related_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤SQL相关的消息"""
        sql_messages = []

        for message in messages:
            content = message.get('content', '')
            if self._is_sql_related_message(content):
                sql_messages.append(message)

        return sql_messages

    def _is_sql_related_message(self, content: str) -> bool:
        """判断消息是否与SQL相关"""
        if not content:
            return False

        content_lower = content.lower()

        # 检查SQL关键词
        sql_indicators = [
            'select', 'from', 'where', 'join', 'group by', 'order by',
            'count', 'sum', 'avg', 'max', 'min', '查询', '数据库',
            '表', '表格', '字段', '记录', '数据', 'sql'
        ]

        # 检查是否包含SQL关键词
        has_sql_keywords = any(indicator in content_lower for indicator in sql_indicators)

        # 检查数据查询模式
        has_data_pattern = any(pattern.search(content) for pattern in self.data_patterns)

        return has_sql_keywords or has_data_pattern

    async def build_context_from_history(
        self,
        current_question: str,
        conversation_history: List[Dict[str, Any]],
        max_items: int = None
    ) -> str:
        """
        从历史记录构建上下文

        Args:
            current_question: 当前问题
            conversation_history: 对话历史
            max_items: 最大包含的历史记录数

        Returns:
            格式化的上下文字符串
        """
        if not conversation_history:
            return ""

        # 限制历史记录数量
        relevant_history = conversation_history[-max_items:] if max_items else conversation_history

        # 计算相关性得分并排序
        scored_messages = []
        for message in relevant_history:
            score = self._calculate_relevance_score(
                message.get('content', ''),
                current_question
            )
            if score > 0.1:  # 只保留有一定相关性的消息
                scored_messages.append((score, message))

        # 按相关性得分排序
        scored_messages.sort(key=lambda x: x[0], reverse=True)

        # 构建上下文
        context_parts = []

        if scored_messages:
            context_parts.append("## 相关对话历史")
            context_parts.append("")

            for score, message in scored_messages:
                formatted_message = self._format_context_message(message)
                context_parts.append(formatted_message)

        context_text = "\n".join(context_parts)
        return self._truncate_context(context_text)

    async def get_enhanced_context(
        self,
        current_question: str,
        conversation_manager = None,
        user_id: str = None,
        platform: str = None,
        manual_context: str = "",
        max_history: int = None
    ) -> str:
        """
        获取增强的上下文（历史记录 + 手动上下文）

        Args:
            current_question: 当前问题
            conversation_manager: 对话管理器
            user_id: 用户ID
            platform: 平台标识
            manual_context: 手动提供的上下文
            max_history: 最大历史记录数

        Returns:
            组合后的上下文字符串
        """
        context_parts = []

        # 1. 添加手动提供的上下文
        if manual_context:
            context_parts.append("## 手动提供的上下文")
            context_parts.append("")
            context_parts.append(manual_context)
            context_parts.append("")

        # 2. 自动获取对话历史上下文
        if conversation_manager and user_id:
            try:
                history_context = await self.build_context_from_history(
                    current_question,
                    await self.get_sql_conversation_history(
                        conversation_manager,
                        user_id,
                        platform,
                        max_history or self.max_history_items
                    ),
                    max_history or self.max_history_items
                )

                if history_context:
                    if context_parts:
                        context_parts.append("")
                    context_parts.append(history_context)

            except Exception as e:
                self.logger.error(f"Error getting conversation history context: {e}")

        return "\n".join(context_parts) if context_parts else ""

    def should_use_enhanced_context(self, current_question: str, user_id: str = None) -> bool:
        """
        判断是否应该使用增强的上下文功能

        Args:
            current_question: 当前问题
            user_id: 用户ID

        Returns:
            是否启用增强上下文
        """
        # 检查当前问题是否复杂，可能需要上下文
        question_indicators = [
            '继续', '接下来', '然后', '另外', '还有', '补充',
            '修改', '调整', '改变', '重新', '再次'
        ]

        current_lower = current_question.lower()
        has_continuation_indicator = any(indicator in current_lower for indicator in question_indicators)

        # 检查是否是追问类问题
        is_follow_up = (
            len(current_question.strip()) < 10 and  # 短问题可能是追问
            not self._is_sql_related_message(current_question)  # 本身不是SQL问题
        )

        return has_continuation_indicator or is_follow_up

    def format_context_for_llm(self, context: str, current_question: str) -> str:
        """
        为LLM格式化上下文信息

        Args:
            context: 上下文字符串
            current_question: 当前问题

        Returns:
            格式化后的上下文字符串
        """
        if not context:
            return ""

        # 构建完整的提示词
        prompt_parts = [
            "你是一个SQL查询助手。请基于以下对话历史和上下文信息，回答用户的问题。",
            "",
            "## 对话历史和上下文",
            context,
            "",
            f"## 当前问题",
            current_question,
            "",
            "请基于上述信息提供准确、相关的回答。如果历史信息不足以回答问题，请明确说明并提供合理建议。"
        ]

        return "\n".join(prompt_parts)