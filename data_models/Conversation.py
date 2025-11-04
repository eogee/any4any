import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from data_models.model import Model

def process_dict_datetime(data_dict: Dict[str, Any]) -> Dict[str, Any]:
    """处理字典中的datetime对象，转换为字符串"""
    if not isinstance(data_dict, dict):
        return data_dict

    processed = {}
    for key, value in data_dict.items():
        if hasattr(value, 'strftime'):  # datetime对象
            processed[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, list):
            processed[key] = [process_dict_datetime(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            processed[key] = process_dict_datetime(value)
        else:
            processed[key] = value
    return processed

class Conversation(Model):
    """会话数据模型，用于和conversations表交互"""

    def get_table_name(self) -> str:
        """获取表名"""
        return "conversations"

    def parse_date_range(self, date_range: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析时间范围字符串为开始和结束日期

        Args:
            date_range: 时间范围，支持: all, today, week, month, year, 7days, 30days, 1year

        Returns:
            tuple: (start_date_str, end_date_str)
        """
        now = datetime.now()

        if date_range == "all":
            return None, None
        elif date_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "7days":
            start = now - timedelta(days=7)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "30days":
            start = now - timedelta(days=30)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "1year":
            start = now - timedelta(days=365)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        else:
            return None, None

    def get_conversation_count(self, user_nick: str = None, platform: str = None,
                             start_date: str = None, end_date: str = None) -> int:
        """
        获取会话记录数量

        Args:
            user_nick: 用户昵称筛选
            platform: 平台筛选
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            int: 符合条件的记录数量
        """
        try:
            # 构建基础查询
            where_parts = []

            if user_nick:
                # 防止SQL注入，转义特殊字符
                escaped_user_nick = user_nick.replace("'", "\\'").replace("\\", "\\\\")
                where_parts.append(f"user_nick = '{escaped_user_nick}'")

            if platform:
                escaped_platform = platform.replace("'", "\\'").replace("\\", "\\\\")
                where_parts.append(f"platform = '{escaped_platform}'")

            if start_date:
                where_parts.append(f"created_time >= '{start_date}'")

            if end_date:
                where_parts.append(f"created_time <= '{end_date}'")

            where_sql = " AND ".join(where_parts) if where_parts else "1=1"

            query = f"""
                SELECT COUNT(*) as count
                FROM conversations
                WHERE {where_sql}
            """

            result = self.fetch_one(query)

            return result['count'] if result else 0

        except Exception as e:
            self.logger.error(f"Failed to get conversation count: {e}")
            return 0

    def get_conversations_paginated(self, page: int = 1, limit: int = 20,
                                   user_nick: str = None, platform: str = None,
                                   start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        分页获取会话列表，按created_time倒序显示

        Args:
            page: 页码，从1开始
            limit: 每页记录数
            user_nick: 用户昵称筛选
            platform: 平台筛选
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            dict: 包含数据列表和分页信息的字典
        """
        try:
            offset = (page - 1) * limit

            # 构建WHERE条件
            where_parts = []

            if user_nick:
                escaped_user_nick = user_nick.replace("'", "\\'").replace("\\", "\\\\")
                where_parts.append(f"user_nick = '{escaped_user_nick}'")

            if platform:
                escaped_platform = platform.replace("'", "\\'").replace("\\", "\\\\")
                where_parts.append(f"platform = '{escaped_platform}'")

            if start_date:
                where_parts.append(f"created_time >= '{start_date}'")

            if end_date:
                where_parts.append(f"created_time <= '{end_date}'")

            where_sql = " AND ".join(where_parts) if where_parts else "1=1"

            # 构建主查询
            query = f"""
                SELECT
                    conversation_id,
                    sender,
                    user_nick,
                    platform,
                    created_time,
                    last_active,
                    message_count,
                    DATE_FORMAT(created_time, '%Y-%m-%d %H:%i:%s') as created_at,
                    DATE_FORMAT(last_active, '%Y-%m-%d %H:%i:%s') as last_active_formatted
                FROM conversations
                WHERE {where_sql}
                ORDER BY created_time DESC
                LIMIT {int(limit)} OFFSET {int(offset)}
            """

            conversations = self.fetch_all(query)

            # 处理数据
            processed_conversations = []
            for conv in conversations:
                processed_conv = process_dict_datetime(dict(conv))

                # 获取该会话的最新用户消息和助手响应
                conversation_id = processed_conv['conversation_id']
                last_messages = self.get_last_messages(conversation_id)
                processed_conv.update(last_messages)

                processed_conversations.append(processed_conv)

            # 获取总数
            total = self.get_conversation_count(user_nick, platform, start_date, end_date)

            return {
                'data': processed_conversations,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }

        except Exception as e:
            self.logger.error(f"Failed to get conversations paginated: {e}")
            return {
                'data': [],
                'total': 0,
                'page': page,
                'limit': limit,
                'total_pages': 0
            }

    def get_unique_users(self) -> List[str]:
        """
        获取所有唯一的用户昵称列表，用于筛选下拉框

        Returns:
            list: 用户昵称列表
        """
        try:
            query = """
                SELECT DISTINCT user_nick
                FROM conversations
                WHERE user_nick IS NOT NULL
                AND user_nick != ''
                ORDER BY user_nick
            """

            results = self.fetch_all(query)
            users = []
            for result in results:
                user_nick = result.get('user_nick', '')
                if user_nick and user_nick not in users:
                    users.append(user_nick)

            return users

        except Exception as e:
            self.logger.error(f"Failed to get unique users: {e}")
            return []

    def get_unique_platforms(self) -> List[str]:
        """
        获取所有唯一的平台列表，用于筛选下拉框

        Returns:
            list: 平台列表
        """
        try:
            query = """
                SELECT DISTINCT platform
                FROM conversations
                WHERE platform IS NOT NULL
                AND platform != ''
                ORDER BY platform
            """

            results = self.fetch_all(query)
            platforms = []
            for result in results:
                platform = result.get('platform', '')
                if platform and platform not in platforms:
                    platforms.append(platform)

            return platforms

        except Exception as e:
            self.logger.error(f"Failed to get unique platforms: {e}")
            return []

    def get_last_messages(self, conversation_id: str) -> Dict[str, Any]:
        """
        获取指定会话的最新用户消息和助手响应

        Args:
            conversation_id: 会话ID

        Returns:
            dict: 包含最新用户消息和助手响应的字典
        """
        try:
            # 获取最新的用户消息
            last_user_query = f"""
                SELECT content as last_user_message, timestamp as last_user_time
                FROM messages
                WHERE conversation_id = '{conversation_id}'
                AND sender_type = 'user'
                ORDER BY timestamp DESC
                LIMIT 1
            """

            # 获取最新的助手响应
            last_assistant_query = f"""
                SELECT content as last_assistant_message, timestamp as last_assistant_time
                FROM messages
                WHERE conversation_id = '{conversation_id}'
                AND sender_type = 'assistant'
                ORDER BY timestamp DESC
                LIMIT 1
            """

            user_result = self.fetch_one(last_user_query)
            assistant_result = self.fetch_one(last_assistant_query)

            result = {
                'last_user_message': '',
                'last_assistant_message': ''
            }

            if user_result:
                result['last_user_message'] = user_result.get('last_user_message', '')

            if assistant_result:
                result['last_assistant_message'] = assistant_result.get('last_assistant_message', '')

            return result

        except Exception as e:
            self.logger.error(f"Failed to get last messages for conversation {conversation_id}: {e}")
            return {
                'last_user_message': '',
                'last_assistant_message': ''
            }