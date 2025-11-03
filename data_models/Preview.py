import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from data_models.model import Model

class Preview(Model):
    """预览数据模型，用于和previews表交互"""
    
    def get_table_name(self) -> str:
        """获取表名"""
        return "previews"
    
    def save_preview_content(self, preview_id: str, saved_content: str, pre_content: str, 
                           full_request: dict, current_request: str, conversation_id: str, 
                           message_id: str, response_time: float, user_id: int) -> int:
        """保存预览编辑内容到数据库"""
        if not conversation_id or not message_id:
            raise ValueError("Invalid conversation_id or message_id")
        
        try:
            full_request_str = json.dumps(full_request) if isinstance(full_request, dict) else str(full_request)
            is_edited = 1 if pre_content != saved_content else 0
            
            data = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "current_request": current_request,
                "saved_content": saved_content,
                "pre_content": pre_content,
                "full_request": full_request_str,
                "response_time": response_time,
                "user_id": user_id,
                "preview_id": preview_id
            }
            
            # 验证消息是否存在
            message_exists = self.fetch_one(
                "SELECT 1 FROM messages WHERE conversation_id = %s AND message_id = %s",
                (conversation_id, message_id)
            )
            
            if not message_exists:
                self.logger.warning(f"Message not found: {conversation_id}, {message_id}")
            else:
                self.logger.debug(f"Message verified: {conversation_id}, {message_id}")
            
            # 检查是否已存在记录
            existing = self.fetch_one(
                "SELECT * FROM previews WHERE conversation_id = %s AND message_id = %s", 
                (conversation_id, message_id)
            )
            
            if existing:
                result = self.update(existing['id'], data, id_column="id")
                return result
            else:
                result = self.insert(data)
                return result
                
        except Exception as e:
            self.logger.error(f"Save preview failed: {str(e)}")
            raise
    
    def get_preview_by_id(self, preview_id: str) -> Optional[Dict[str, Any]]:
        """根据preview_id获取预览记录"""
        return self.find_by_id(preview_id, id_column="preview_id")
    
    def get_all_previews(self) -> list:
        """获取所有预览记录"""
        return self.find_all()
    
    def delete_preview(self, preview_id: str) -> int:
        """删除指定的预览记录"""
        return self.delete(preview_id, id_column="preview_id")

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

    def get_previews_count(self, user_nick: str = None, start_date: str = None,
                           end_date: str = None, search: str = None) -> int:
        """
        获取预览权数量

        Args:
            user_nick: 用户昵称筛选
            start_date: 开始日期
            end_date: 结束日期
            search: 搜索关键词

        Returns:
            int: 符合条件的记录数量
        """
        try:
            # 直接基于传入参数构建查询
            if user_nick or start_date or end_date or search:
                # 有筛选条件时构建WHERE子句
                where_parts = []
                query_params = []

                if user_nick:
                    # 使用字符串拼接来避免参数占位符冲突
                    escaped_nick = user_nick.replace("'", "\\'").replace("\\", "\\\\")
                    where_parts.append(f"JSON_EXTRACT(p.full_request, '$.sender_nickname') = '{escaped_nick}'")

                if start_date:
                    where_parts.append(f"p.created_at >= '{start_date}'")

                if end_date:
                    where_parts.append(f"p.created_at <= '{end_date}'")

                if search:
                    # 转义搜索关键词以防止SQL注入
                    escaped_search = search.replace("'", "\\'").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    # 在请求内容(current_request)和回复内容(saved_content)中搜索
                    search_conditions = [
                        f"p.current_request LIKE '%{escaped_search}%'",
                        f"p.saved_content LIKE '%{escaped_search}%'"
                    ]
                    where_parts.append(f"({' OR '.join(search_conditions)})")

                where_sql = " AND ".join(where_parts)
                query = f"SELECT COUNT(*) as count FROM {self.get_table_name()} p WHERE {where_sql}"

                # 使用字符串拼接避免参数冲突
                self.logger.debug(f"Count SQL: {query}")
                result = self.fetch_one(query)
            else:
                # 无筛选条件时
                query = f"SELECT COUNT(*) as count FROM {self.get_table_name()} p"
                result = self.fetch_one(query)
            return result['count'] if result else 0

        except Exception as e:
            self.logger.error(f"Failed to get previews count: {e}")
            return 0

    def get_previews_paginated(self, page: int = 1, limit: int = 20,
                               user_nick: str = None, start_date: str = None,
                               end_date: str = None, search: str = None) -> Dict[str, Any]:
        """
        分页获取预览列表

        Args:
            page: 页码，从1开始
            limit: 每页记录数
            user_nick: 用户昵称筛选
            start_date: 开始日期
            end_date: 结束日期
            search: 搜索关键词，用于搜索请求内容和回复内容

        Returns:
            dict: 包含数据列表和分页信息的字典
        """
        try:
            offset = (page - 1) * limit

            # 添加详细的调试日志
            self.logger.debug(f"get_previews_paginated called with: user_nick={repr(user_nick)}, start_date={repr(start_date)}, end_date={repr(end_date)}, search={repr(search)}")

            # 直接基于传入参数构建查询
            if user_nick or start_date or end_date or search:
                # 有筛选条件时构建WHERE子句
                where_parts = []
                query_params = []

                if user_nick:
                    # 使用字符串拼接来避免参数占位符冲突
                    escaped_nick = user_nick.replace("'", "\\'").replace("\\", "\\\\")
                    where_parts.append(f"JSON_EXTRACT(p.full_request, '$.sender_nickname') = '{escaped_nick}'")

                if start_date:
                    where_parts.append(f"p.created_at >= '{start_date}'")

                if end_date:
                    where_parts.append(f"p.created_at <= '{end_date}'")

                if search:
                    # 转义搜索关键词以防止SQL注入
                    escaped_search = search.replace("'", "\\'").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    # 在请求内容(current_request)和回复内容(saved_content)中搜索
                    search_conditions = [
                        f"p.current_request LIKE '%{escaped_search}%'",
                        f"p.saved_content LIKE '%{escaped_search}%'"
                    ]
                    where_parts.append(f"({' OR '.join(search_conditions)})")

                where_sql = " AND ".join(where_parts)

                # 构建基础查询，避免在f-string中使用DATE_FORMAT
                query = f"""
                    SELECT p.*,
                           JSON_EXTRACT(p.full_request, '$.sender_nickname') as sender_nickname,
                           JSON_EXTRACT(p.full_request, '$.sender_id') as sender_id,
                           JSON_EXTRACT(p.full_request, '$.platform') as platform,
                           JSON_EXTRACT(p.full_request, '$.messages') as messages,
                           DATE_FORMAT(p.created_at, '%Y-%m-%d %H:%i:%s') as created_at_formatted,
                           DATE_FORMAT(p.updated_at, '%Y-%m-%d %H:%i:%s') as updated_at_formatted
                    FROM {self.get_table_name()} p
                    WHERE {where_sql}
                    ORDER BY p.created_at DESC
                    LIMIT {int(limit)} OFFSET {int(offset)}
                """

                previews = self.fetch_all(query)
            else:
                # 无筛选条件时，直接构建完整查询
                query = f"""
                    SELECT p.*,
                           JSON_EXTRACT(p.full_request, '$.sender_nickname') as sender_nickname,
                           JSON_EXTRACT(p.full_request, '$.sender_id') as sender_id,
                           JSON_EXTRACT(p.full_request, '$.platform') as platform,
                           JSON_EXTRACT(p.full_request, '$.messages') as messages,
                           DATE_FORMAT(p.created_at, '%Y-%m-%d %H:%i:%s') as created_at_formatted,
                           DATE_FORMAT(p.updated_at, '%Y-%m-%d %H:%i:%s') as updated_at_formatted
                    FROM {self.get_table_name()} p
                    ORDER BY p.created_at DESC
                    LIMIT {int(limit)} OFFSET {int(offset)}
                """

                previews = self.fetch_all(query)

            # 处理数据，解析JSON字段
            processed_previews = []
            for preview in previews:
                processed_preview = dict(preview)  # 转换为字典

                # 解析JSON字段
                for field in ['sender_nickname', 'sender_id', 'platform', 'messages']:
                    value = processed_preview.get(field)
                    if value and isinstance(value, str):
                        try:
                            # 移除JSON字符串的引号
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            # 处理转义字符，但保持中文字符正确显示
                            if '\\' in value:
                                # 尝试修复编码问题
                                try:
                                    # 先尝试直接解码
                                    if value.encode('utf-8').decode('utf-8') != value:
                                        value = value.encode('utf-8').decode('utf-8')
                                except:
                                    pass

                                # 处理常见的转义字符
                                value = value.replace('\\n', '\n')
                                value = value.replace('\\t', '\t')
                                value = value.replace('\\"', '"')
                                value = value.replace('\\\\', '\\')

                                # 处理Unicode转义 \\uXXXX 格式（但要小心中文字符）
                                import re
                                def replace_unicode(match):
                                    try:
                                        return chr(int(match.group(1), 16))
                                    except:
                                        return match.group(0)

                                value = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, value)

                            # 如果是messages字段且是JSON格式，则解析
                            if field == 'messages' and value.startswith('['):
                                processed_preview[field] = json.loads(value)
                            else:
                                processed_preview[field] = value
                        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                            # 如果解析失败，保持原值
                            processed_preview[field] = value

                # 使用格式化后的日期字符串替换原始datetime对象
                if 'created_at_formatted' in processed_preview:
                    processed_preview['created_at'] = processed_preview['created_at_formatted']
                if 'updated_at_formatted' in processed_preview:
                    processed_preview['updated_at'] = processed_preview['updated_at_formatted']

                processed_previews.append(processed_preview)

            # 获取总数
            total = self.get_previews_count(user_nick, start_date, end_date)

            return {
                'data': processed_previews,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }

        except Exception as e:
            self.logger.error(f"Failed to get previews paginated: {e}")
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
            query = f"""
                SELECT DISTINCT JSON_EXTRACT(p.full_request, '$.sender_nickname') as user_nick
                FROM {self.get_table_name()} p
                WHERE JSON_EXTRACT(p.full_request, '$.sender_nickname') IS NOT NULL
                ORDER BY user_nick
            """

            results = self.fetch_all(query)
            users = []
            for result in results:
                user_nick = result.get('user_nick', '')
                if user_nick and isinstance(user_nick, str):
                    # 移除引号并解析转义字符
                    if user_nick.startswith('"') and user_nick.endswith('"'):
                        user_nick = user_nick[1:-1]
                    # 处理转义字符，但保持中文字符正确显示
                    if '\\' in user_nick:
                        import re
                        # 处理常见的转义字符
                        user_nick = user_nick.replace('\\n', '\n')
                        user_nick = user_nick.replace('\\t', '\t')
                        user_nick = user_nick.replace('\\"', '"')
                        user_nick = user_nick.replace('\\\\', '\\')
                        # 处理Unicode转义 \\uXXXX 格式
                        user_nick = re.sub(r'\\u([0-9a-fA-F]{4})',
                                         lambda m: chr(int(m.group(1), 16)), user_nick)

                    if user_nick and user_nick not in users:
                        users.append(user_nick)

            return users

        except Exception as e:
            self.logger.error(f"Failed to get unique users: {e}")
            return []

    def get_last_user_message(self, messages: List[Dict[str, Any]]) -> str:
        """
        从消息列表中获取最后一条用户消息

        Args:
            messages: 消息列表

        Returns:
            str: 最后一条用户消息内容
        """
        if not messages:
            return ""

        for message in reversed(messages):
            if message.get('role') == 'user':
                content = message.get('content', '')
                if content:
                    return content

        return ""

    