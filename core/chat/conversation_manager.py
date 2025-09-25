import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from core.chat.conversation_database import ConversationDatabase
from core.chat.llm import get_llm_service
from config import Config

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    会话管理器，负责处理会话的业务逻辑
    调用数据库层进行数据操作
    """
    
    def __init__(self):
        """
        初始化会话管理器
        """
        self.db = ConversationDatabase()
        self.llm_service = get_llm_service()
        # 简单的内存缓存，用于存储活跃会话
        self.active_conversations = {}
        # 缓存过期时间（秒）
        self.cache_ttl = 3600  # 1小时
    
    def _generate_message_id(self) -> str:
        """
        生成唯一的消息ID
        
        Returns:
            str: UUID格式的消息ID
        """
        return str(uuid.uuid4())
    
    def _get_current_time(self) -> str:
        """
        获取当前时间的字符串表示
        
        Returns:
            str: 格式化的时间字符串
        """
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _create_user_message(self, content: str) -> dict:
        """
        创建用户消息对象
        
        Args:
            content: 消息内容
            
        Returns:
            dict: 消息对象
        """
        return {
            'message_id': self._generate_message_id(),
            'content': content,
            'sender_type': 'user',
            'timestamp': self._get_current_time()
        }
    
    def _create_assistant_message(self, content: str) -> dict:
        """
        创建助手消息对象
        
        Args:
            content: 消息内容
            
        Returns:
            dict: 消息对象
        """
        return {
            'message_id': self._generate_message_id(),
            'content': content,
            'sender_type': 'assistant',
            'timestamp': self._get_current_time()
        }
    
    def _format_messages_for_llm(self, conversation: dict) -> List[Dict[str, str]]:
        """
        将会话消息格式化为LLM需要的格式
        
        Args:
            conversation: 会话数据
            
        Returns:
            List[Dict[str, str]]: 格式化的消息列表
        """
        messages = []
        for msg in conversation.get('messages', []):
            messages.append({
                'role': msg['sender_type'],
                'content': msg['content']
            })
        return messages
    
    async def process_message(self, sender: str, user_nick: str, platform: str, content: str) -> tuple:
        """
        处理用户消息的核心方法
        
        Args:
            sender: 发送者唯一标识
            user_nick: 用户昵称
            platform: 来源平台
            content: 用户消息内容
            
        Returns:
            tuple: (响应内容, 会话ID)
        """
        # 参数验证
        if not all([sender, user_nick, platform, content]):
            raise ValueError("Missing required parameters")
        
        # 检查是否为创建新会话的指令
        if content.strip() == '/a':
            # 创建新会话
            new_conversation = self.db.create_new_conversation(sender, user_nick, platform)
            # 更新缓存
            self.active_conversations[(sender, platform)] = new_conversation
            # 返回新会话提示
            return "新会话已开启，您可以开始新的对话。", new_conversation['conversation_id']
        
        # 尝试从缓存获取当前会话
        cache_key = (sender, platform)
        conversation = self.active_conversations.get(cache_key)
        
        # 如果缓存中没有，则从数据库获取最新会话
        if not conversation:
            conversation = self.db.get_latest_conversation(sender, user_nick, platform)
            
            # 如果数据库中也没有，创建新会话
            if not conversation:
                conversation = self.db.create_new_conversation(sender, user_nick, platform)
        
        # 更新缓存
        self.active_conversations[cache_key] = conversation
        
        # 创建用户消息
        user_message = self._create_user_message(content)
        
        # 设置消息的序列号
        user_message['sequence_number'] = len(conversation.get('messages', [])) + 1
        
        # 保存用户消息
        if not self.db.save_message(conversation['conversation_id'], user_message):
            logger.error("Failed to save user message")
            # 即使保存失败，继续处理以保证用户体验
        
        # 更新会话中的消息列表
        if 'messages' not in conversation:
            conversation['messages'] = []
        conversation['messages'].append(user_message)
        
        # 生成完整的对话历史文本
        conversation_history = "\n".join([f"{msg['sender_type']}: {msg['content']}" for msg in conversation.get('messages', [])])
        
        try:
            # 调用LLM生成响应
            llm_response = await self.llm_service.generate_response(conversation_history)
            
            # 创建助手消息
            assistant_message = self._create_assistant_message(llm_response)
            assistant_message['sequence_number'] = user_message['sequence_number'] + 1
            
            # 保存助手消息
            if not self.db.save_message(conversation['conversation_id'], assistant_message):
                logger.error("Failed to save assistant message")
            
            # 更新会话中的消息列表
            conversation['messages'].append(assistant_message)
            
            return llm_response, conversation['conversation_id']
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            # 返回错误响应
            error_message = "抱歉，我暂时无法生成回复。请稍后再试。"
            
            # 创建错误回复的助手消息
            error_assistant_message = self._create_assistant_message(error_message)
            error_assistant_message['sequence_number'] = user_message['sequence_number'] + 1
            
            # 尝试保存错误消息
            self.db.save_message(conversation['conversation_id'], error_assistant_message)
            
            return error_message, conversation['conversation_id']
            
    async def process_message_stream(self, sender: str, user_nick: str, platform: str, content: str, generation_id: str):
        """
        流式处理用户消息的方法
        
        Args:
            sender: 发送者唯一标识
            user_nick: 用户昵称
            platform: 来源平台
            content: 用户消息内容
            generation_id: 生成ID，用于标识当前流式生成
            
        Yields:
            str: 生成的文本块
        """
        # 参数验证
        if not all([sender, user_nick, platform, content, generation_id]):
            yield "缺少必要参数，请检查输入。"
            return
        
        # 检查是否为创建新会话的指令
        if content.strip() == '/a':
            # 创建新会话
            new_conversation = self.db.create_new_conversation(sender, user_nick, platform)
            # 更新缓存
            self.active_conversations[(sender, platform)] = new_conversation
            # 返回新会话提示
            yield "新会话已开启，您可以开始新的对话。"
            return
        
        # 尝试从缓存获取当前会话
        cache_key = (sender, platform)
        conversation = self.active_conversations.get(cache_key)
        
        # 如果缓存中没有，则从数据库获取最新会话
        if not conversation:
            conversation = self.db.get_latest_conversation(sender, user_nick, platform)
            
            # 如果数据库中也没有，创建新会话
            if not conversation:
                conversation = self.db.create_new_conversation(sender, user_nick, platform)
        
        # 更新缓存
        self.active_conversations[cache_key] = conversation
        
        # 创建用户消息
        user_message = self._create_user_message(content)
        
        # 设置消息的序列号
        user_message['sequence_number'] = len(conversation.get('messages', [])) + 1
        
        # 保存用户消息
        if not self.db.save_message(conversation['conversation_id'], user_message):
            logger.error("Failed to save user message")
        
        # 更新会话中的消息列表
        if 'messages' not in conversation:
            conversation['messages'] = []
        conversation['messages'].append(user_message)
        
        # 生成完整的对话历史文本
        conversation_history = "\n".join([f"{msg['sender_type']}: {msg['content']}" for msg in conversation.get('messages', [])])
        
        # 累积的助手响应内容
        accumulated_response = ""
        
        try:
            # 使用LLM服务的流式生成方法
            async for text_chunk in self.llm_service.generate_stream(conversation_history, generation_id):
                # 处理特殊标记
                cleaned_chunk = text_chunk
                if "<|im_start|>assistant" in cleaned_chunk:
                    cleaned_chunk = cleaned_chunk.split("<|im_start|>assistant")[-1].strip()
                if "<|im_end|>" in cleaned_chunk:
                    cleaned_chunk = cleaned_chunk.split("<|im_end|>")[0].strip()
                
                # 累积响应内容
                accumulated_response += cleaned_chunk
                
                # 产生当前文本块
                yield cleaned_chunk
                
        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            # 产生错误信息
            error_message = f"\n\n[错误: {str(e)}]"
            yield error_message
            accumulated_response = f"[错误: {str(e)}]"
        
        # 创建助手消息
        assistant_message = self._create_assistant_message(accumulated_response)
        assistant_message['sequence_number'] = user_message['sequence_number'] + 1
        
        # 保存助手消息
        if not self.db.save_message(conversation['conversation_id'], assistant_message):
            logger.error("Failed to save assistant message")
        
        # 更新会话中的消息列表
        conversation['messages'].append(assistant_message)
    
    def get_conversation_history(self, conversation_id: str) -> Optional[dict]:
        """
        获取会话历史
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            Optional[dict]: 会话历史数据
        """
        if not conversation_id:
            return None
        
        # 先尝试从缓存获取
        for conversation in self.active_conversations.values():
            if conversation.get('conversation_id') == conversation_id:
                return conversation
        
        # 缓存中没有则从数据库获取
        return self.db.get_conversation_by_id(conversation_id)
    
    def cleanup_cache(self):
        """
        清理过期的缓存会话
        可以定时调用此方法来清理内存
        """
        current_time = datetime.now()
        expired_keys = []
        
        for key, conversation in self.active_conversations.items():
            last_active = datetime.strptime(conversation['last_active'], '%Y-%m-%d %H:%M:%S')
            if (current_time - last_active).total_seconds() > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.active_conversations[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired conversations from cache")

# 创建全局会话管理器实例
conversation_manager = ConversationManager()