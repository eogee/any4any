import uuid
import logging
from datetime import datetime
from typing import Optional
from data_models.model import Model

logger = logging.getLogger(__name__)

class ConversationDatabase(Model):
    """会话数据库交互类，处理会话和消息的存储、查询和删除"""
    
    def get_table_name(self) -> str:
        """获取表名"""
        return "conversations"
    
    def save_conversation(self, conversation_data: dict) -> bool:
        """保存完整会话数据，包括会话基本信息和相关消息"""
        try:
            self.begin_transaction()
            
            # 提取会话基本信息
            conversation_info = {
                'conversation_id': conversation_data['conversation_id'],
                'sender': conversation_data['sender'],
                'user_nick': conversation_data['user_nick'],
                'platform': conversation_data['platform'],
                'created_time': conversation_data['created_time'],
                'last_active': conversation_data['last_active'],
                'message_count': len(conversation_data.get('messages', []))
            }
            
            # 检查并保存会话
            existing = self.find_by_id(conversation_info['conversation_id'], 'conversation_id')
            if existing:
                self.update(conversation_info['conversation_id'], conversation_info, 'conversation_id')
                logger.info(f"Updated conversation: {conversation_info['conversation_id']}")
            else:
                self.insert(conversation_info)
                logger.info(f"Inserted new conversation: {conversation_info['conversation_id']}")
            
            # 保存消息
            messages = conversation_data.get('messages', [])
            for message in messages:
                msg_exists = self.fetch_one(
                    "SELECT * FROM messages WHERE message_id = %s", 
                    (message['message_id'],)
                )
                
                if not msg_exists:
                    message_data = {
                        'message_id': message['message_id'],
                        'conversation_id': conversation_info['conversation_id'],
                        'content': message['content'],
                        'sender_type': message['sender_type'],
                        'is_timeout': message.get('is_timeout', 0),
                        'timestamp': message['timestamp'],
                        'sequence_number': message.get('sequence_number', 0)
                    }
                    
                    # 插入消息
                    self.execute_query(
                        "INSERT INTO messages (message_id, conversation_id, content, sender_type, is_timeout, timestamp, sequence_number) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (message_data['message_id'], message_data['conversation_id'], 
                         message_data['content'], message_data['sender_type'], 
                         message_data['is_timeout'], message_data['timestamp'], message_data['sequence_number'])
                    )
            
            self.commit_transaction()
            return True
            
        except Exception as e:
            self.rollback_transaction()
            logger.error(f"Failed to save conversation: {e}")
            return False
    
    def get_conversation_by_id(self, conversation_id: str) -> Optional[dict]:
        """根据ID获取会话详情，包括消息列表"""
        try:
            # 获取会话基本信息
            conversation = self.find_by_id(conversation_id, 'conversation_id')
            if not conversation or not isinstance(conversation, dict):
                logger.warning(f"Conversation not found or invalid format, ID: {conversation_id}")
                return None
            
            # 获取消息列表
            try:
                messages = self.fetch_all(
                    "SELECT * FROM messages WHERE conversation_id = %s ORDER BY sequence_number",
                    (conversation_id,)
                )
            except Exception as msg_error:
                logger.error(f"Failed to fetch messages: {msg_error}")
                messages = []
            
            # 构建完整会话数据
            try:
                result = conversation.copy()
                formatted_messages = []
                for msg in messages:
                    if isinstance(msg, dict):
                        try:
                            # 处理datetime对象序列化
                            timestamp = msg.get('timestamp', '')
                            if hasattr(timestamp, 'isoformat'):
                                timestamp = timestamp.isoformat()
                            
                            formatted_message = {
                                'message_id': msg.get('message_id', ''),
                                'content': msg.get('content', ''),
                                'sender_type': msg.get('sender_type', ''),
                                'timestamp': timestamp,
                                'sequence_number': msg.get('sequence_number', 0),
                                'is_timeout': msg.get('is_timeout', 0)
                            }
                            formatted_messages.append(formatted_message)
                        except Exception as item_error:
                            logger.error(f"Failed to format message: {item_error}")
                
                result['messages'] = formatted_messages
                return result
            except Exception as build_error:
                logger.error(f"Failed to build conversation data: {build_error}")
                # 返回基本会话信息
                return conversation
            
        except Exception as e:
            logger.error(f"Failed to get conversation by ID: {e}")
            return None
    
    def get_latest_conversation(self, sender: str, user_nick: str, platform: str) -> Optional[dict]:
        """获取用户在特定平台上的最新活跃会话"""
        try:
            # 查询最新会话
            query = (
                "SELECT * FROM conversations "
                "WHERE sender = %s AND user_nick = %s AND platform = %s "
                "ORDER BY last_active DESC LIMIT 1"
            )
            
            conversation = self.fetch_one(query, (sender, user_nick, platform))
            
            if not conversation:
                return None
            
            # 获取消息列表
            messages = self.fetch_all(
                "SELECT * FROM messages WHERE conversation_id = %s ORDER BY sequence_number",
                (conversation['conversation_id'],)
            )
            
            # 构建完整会话数据
            result = conversation.copy()
            result['messages'] = [
                {
                    'message_id': msg['message_id'],
                    'content': msg['content'],
                    'sender_type': msg['sender_type'],
                    'timestamp': msg['timestamp'],
                    'sequence_number': msg['sequence_number']
                }
                for msg in messages
            ]
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get latest conversation: {e}")
            return None
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """删除会话及其所有相关消息"""
        try:
            # 外键约束会自动删除相关消息
            result = self.delete(conversation_id, 'conversation_id')
            logger.info(f"Deleted conversation: {conversation_id}, affected rows: {result}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    def save_message(self, conversation_id: str, message: dict) -> bool:
        """保存单条消息到数据库"""
        try:
            # 保存消息
            self.execute_query(
                "INSERT INTO messages (message_id, conversation_id, content, sender_type, is_timeout, timestamp, sequence_number) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (message['message_id'], conversation_id, message['content'], 
                 message['sender_type'], message.get('is_timeout', 0), message['timestamp'], message.get('sequence_number', 0))
            )
            
            # 更新会话信息
            self.execute_query(
                "UPDATE conversations SET last_active = %s, message_count = message_count + 1 WHERE conversation_id = %s",
                (message['timestamp'], conversation_id)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False
    
    def create_new_conversation(self, sender: str, user_nick: str, platform: str) -> dict:
        """创建新的会话"""
        # 生成会话ID
        conversation_id = str(uuid.uuid4())
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conversation_data = {
            'conversation_id': conversation_id,
            'sender': sender,
            'user_nick': user_nick,
            'platform': platform,
            'created_time': current_time,
            'last_active': current_time,
            'message_count': 0,
            'messages': []
        }
        
        # 保存新会话
        if self.save_conversation(conversation_data):
            logger.info(f"Created new conversation for user {sender} on {platform}")
            return conversation_data
        else:
            raise Exception("Failed to create new conversation")