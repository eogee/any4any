import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from data_models.model import Model

def serialize_datetime(obj):
    """将datetime对象序列化为字符串"""
    if hasattr(obj, 'strftime'):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    return str(obj)

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

class Timeout(Model):
    """超时响应数据模型，用于和messages表交互"""

    def get_table_name(self) -> str:
        """获取表名"""
        return "messages"

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

    def get_timeout_count(self, user_nick: str = None, start_date: str = None,
                         end_date: str = None, search: str = None) -> int:
        """
        获取超时响应记录数量

        Args:
            user_nick: 用户昵称筛选
            start_date: 开始日期
            end_date: 结束日期
            search: 搜索关键词

        Returns:
            int: 符合条件的记录数量
        """
        try:
            # 构建基础查询 - 使用字符串格式化
            where_parts = ["m.is_timeout = 1"]

            if user_nick:
                # 防止SQL注入，转义特殊字符
                escaped_user_nick = user_nick.replace("'", "\\'").replace("\\", "\\\\")
                where_parts.append(f"c.user_nick = '{escaped_user_nick}'")

            if start_date:
                where_parts.append(f"m.timestamp >= '{start_date}'")

            if end_date:
                where_parts.append(f"m.timestamp <= '{end_date}'")

            if search:
                # 防止SQL注入，转义特殊字符
                escaped_search = search.replace("'", "\\'").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                where_parts.append(f"(m.content LIKE '%{escaped_search}%')")

            where_sql = " AND ".join(where_parts)

            query = f"""
                SELECT COUNT(*) as count
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE {where_sql}
            """

            result = self.fetch_one(query)

            return result['count'] if result else 0

        except Exception as e:
            self.logger.error(f"Failed to get timeout count: {e}")
            return 0

    def get_timeout_messages_paginated(self, page: int = 1, limit: int = 20,
                                      user_nick: str = None, start_date: str = None,
                                      end_date: str = None, search: str = None) -> Dict[str, Any]:
        """
        分页获取超时响应列表

        Args:
            page: 页码，从1开始
            limit: 每页记录数
            user_nick: 用户昵称筛选
            start_date: 开始日期
            end_date: 结束日期
            search: 搜索关键词，用于搜索消息内容

        Returns:
            dict: 包含数据列表和分页信息的字典
        """
        try:
            offset = (page - 1) * limit

            # 构建WHERE条件 - 使用字符串格式化而不是参数化查询
            where_parts = ["m.is_timeout = 1"]

            if user_nick:
                # 防止SQL注入，转义特殊字符
                escaped_user_nick = user_nick.replace("'", "\\'").replace("\\", "\\\\")
                where_parts.append(f"c.user_nick = '{escaped_user_nick}'")

            if start_date:
                where_parts.append(f"m.timestamp >= '{start_date}'")

            if end_date:
                where_parts.append(f"m.timestamp <= '{end_date}'")

            if search:
                # 防止SQL注入，转义特殊字符
                escaped_search = search.replace("'", "\\'").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                where_parts.append(f"(m.content LIKE '%{escaped_search}%')")

            where_sql = " AND ".join(where_parts)

            # 构建主查询 - 使用字符串格式化
            query = f"""
                SELECT
                    m.message_id,
                    m.conversation_id,
                    m.content,
                    m.timestamp,
                    m.is_timeout,
                    c.user_nick,
                    c.sender,
                    c.platform,
                    DATE_FORMAT(m.timestamp, '%Y-%m-%d %H:%i:%s') as created_at
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE {where_sql}
                ORDER BY m.timestamp DESC
                LIMIT {int(limit)} OFFSET {int(offset)}
            """

            timeout_messages = self.fetch_all(query)

            # 处理数据，获取相关的用户请求消息
            processed_messages = []
            for msg in timeout_messages:
                # 首先处理所有datetime对象
                processed_msg = process_dict_datetime(dict(msg))

                # 获取该对话中最后一条用户消息作为请求内容
                conversation_id = processed_msg['conversation_id']
                timestamp = processed_msg['timestamp']
                last_user_query = f"""
                    SELECT content
                    FROM messages
                    WHERE conversation_id = '{conversation_id}'
                    AND sender_type = 'user'
                    AND timestamp < '{timestamp}'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                try:
                    last_user_result = self.fetch_one(last_user_query)
                except Exception as e:
                    self.logger.error(f"Failed to fetch last user message: {e}")
                    self.logger.error(f"Query: {last_user_query}")
                    last_user_result = None

                processed_msg['last_user_message'] = last_user_result['content'] if last_user_result else '无关联请求'

                # 映射字段名以匹配前端期望
                processed_msg['sender_nickname'] = processed_msg.get('user_nick', '未知用户')
                processed_msg['sender_id'] = processed_msg.get('sender', '未知ID')

                processed_messages.append(processed_msg)

            # 获取总数
            total = self.get_timeout_count(user_nick, start_date, end_date, search)

            return {
                'data': processed_messages,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }

        except Exception as e:
            self.logger.error(f"Failed to get timeout messages paginated: {e}")
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
                SELECT DISTINCT c.user_nick
                FROM conversations c
                JOIN messages m ON c.conversation_id = m.conversation_id
                WHERE m.is_timeout = 1
                AND c.user_nick IS NOT NULL
                AND c.user_nick != ''
                ORDER BY c.user_nick
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

    def get_timeout_detail(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定超时消息的详细信息

        Args:
            message_id: 消息ID

        Returns:
            dict: 消息详细信息
        """
        try:
            # 获取超时消息详情
            query = f"""
                SELECT
                    m.*,
                    c.user_nick,
                    c.sender,
                    c.platform,
                    DATE_FORMAT(m.timestamp, '%Y-%m-%d %H:%i:%s') as created_at_formatted
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE m.message_id = '{message_id}' AND m.is_timeout = 1
            """

            result = self.fetch_one(query)

            if result:
                # 首先处理所有datetime对象
                result = process_dict_datetime(result)

                # 获取对话历史
                conversation_id = result['conversation_id']
                history_query = f"""
                    SELECT content, sender_type, timestamp
                    FROM messages
                    WHERE conversation_id = '{conversation_id}'
                    ORDER BY timestamp ASC
                """
                history_results = self.fetch_all(history_query)

                result['messages'] = []
                for hist_msg in history_results:
                    hist_msg = process_dict_datetime(hist_msg)
                    result['messages'].append({
                        'role': hist_msg['sender_type'],
                        'content': hist_msg['content'],
                        'timestamp': hist_msg['timestamp']
                    })

                # 映射字段名以匹配前端期望
                result['sender_nickname'] = result.get('user_nick', '未知用户')
                result['sender_id'] = result.get('sender', '未知ID')

            return result

        except Exception as e:
            self.logger.error(f"Failed to get timeout detail: {e}")
            return None