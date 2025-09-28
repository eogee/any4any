import os
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional
from core.chat.conversation_database import ConversationDatabase
from core.chat.llm import get_llm_service
from core.dingtalk.message_manager import message_dedup

logger = logging.getLogger(__name__)

class ConversationManager:
    """会话管理器"""
    
    def __init__(self):
        self.is_main_process = self._check_main_process()
        self.active_conversations = {}
        self.cache_ttl = 3600
        
        if self.is_main_process:
            self.db = ConversationDatabase()
            self.llm_service = get_llm_service()
        else:
            self.db = None
            self.llm_service = None
    
    def _check_main_process(self):
        """检查是否为主进程"""
        if os.environ.get('IS_MAIN_PROCESS') == 'true':
            return True
        current_port = os.environ.get('CURRENT_PORT', 'unknown')
        return current_port != '9999' and current_port != 'unknown'
    
    def _generate_message_id(self):
        return str(uuid.uuid4())
    
    def _get_current_time(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _create_user_message(self, content):
        return {
            'message_id': self._generate_message_id(),
            'content': content,
            'sender_type': 'user',
            'timestamp': self._get_current_time()
        }
    
    def _create_assistant_message(self, content):
        return {
            'message_id': self._generate_message_id(),
            'content': content,
            'sender_type': 'assistant',
            'timestamp': self._get_current_time()
        }
    
    def _check_message_processed(self, message_id):
        """检查消息是否已处理"""
        if not message_id or not hasattr(message_dedup, 'status_store'):
            return False
        
        current_status = message_dedup.status_store.get(message_id)
        if not current_status:
            return False
        
        status_type = current_status.get('status')
        return status_type in ['completed', 'timeout_processed', 'processing']
    
    async def process_message(self, sender, user_nick, platform, content, is_timeout=False, message_id=None, skip_save=False):
        """处理用户消息"""
        if message_id and self._check_message_processed(message_id):
            return "", ""
        
        if not self.is_main_process:
            return "该请求需要在主进程中处理。", "non_main_process"
        
        if not all([sender, user_nick, platform, content]):
            raise ValueError("Missing required parameters")
        
        # 新建会话指令
        if content.strip() == '/a':
            new_conversation = self.db.create_new_conversation(sender, user_nick, platform)
            self.active_conversations[(sender, platform)] = new_conversation
            return "新会话已开启。", new_conversation['conversation_id']
        
        # 获取或创建会话
        cache_key = (sender, platform)
        conversation = self.active_conversations.get(cache_key)
        if not conversation:
            conversation = self.db.get_latest_conversation(sender, user_nick, platform)
            if not conversation:
                conversation = self.db.create_new_conversation(sender, user_nick, platform)
        
        self.active_conversations[cache_key] = conversation
        
        # 创建用户消息
        user_message = self._create_user_message(content)
        if message_id:
            user_message['message_id'] = message_id
        user_message['sequence_number'] = len(conversation.get('messages', [])) + 1
        
        # 保存消息
        if not skip_save:
            self.db.save_message(conversation['conversation_id'], user_message)
            if 'messages' not in conversation:
                conversation['messages'] = []
            conversation['messages'].append(user_message)
        
        # 生成对话历史
        conversation_history = "\n".join([
            f"{msg['sender_type']}: {msg['content']}" 
            for msg in conversation.get('messages', [])
        ])
        
        try:
            # 生成响应
            llm_response = await self.llm_service.generate_response(conversation_history)
            
            # 创建助手消息
            assistant_message = self._create_assistant_message(llm_response)
            assistant_message['sequence_number'] = user_message['sequence_number'] + 1
            assistant_message['is_timeout'] = 1 if is_timeout else 0
            
            if not skip_save:
                self.db.save_message(conversation['conversation_id'], assistant_message)
                conversation['messages'].append(assistant_message)
            
            return llm_response, conversation['conversation_id']
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            error_message = "抱歉，暂时无法生成回复。请稍后再试。"
            
            error_assistant_message = self._create_assistant_message(error_message)
            error_assistant_message['sequence_number'] = user_message['sequence_number'] + 1
            error_assistant_message['is_timeout'] = 1 if is_timeout else 0
            
            if not skip_save:
                self.db.save_message(conversation['conversation_id'], error_assistant_message)
            
            return error_message, conversation['conversation_id']
    
    async def process_message_stream(self, sender, user_nick, platform, content, generation_id, is_timeout=False, message_id=None):
        """流式处理用户消息"""
        if message_id and self._check_message_processed(message_id):
            yield "消息已处理，跳过重复处理。"
            return
        
        if not self.is_main_process:
            yield "该流式请求需要在主进程中处理。"
            return
        
        if not all([sender, user_nick, platform, content, generation_id]):
            yield "缺少必要参数。"
            return
        
        # 新建会话指令
        if content.strip() == '/a':
            new_conversation = self.db.create_new_conversation(sender, user_nick, platform)
            self.active_conversations[(sender, platform)] = new_conversation
            yield "新会话已开启。"
            return
        
        # 获取或创建会话
        cache_key = (sender, platform)
        conversation = self.active_conversations.get(cache_key)
        if not conversation:
            conversation = self.db.get_latest_conversation(sender, user_nick, platform)
            if not conversation:
                conversation = self.db.create_new_conversation(sender, user_nick, platform)
        
        self.active_conversations[cache_key] = conversation
        
        # 创建用户消息
        user_message = self._create_user_message(content)
        user_message['sequence_number'] = len(conversation.get('messages', [])) + 1
        if message_id:
            user_message['message_id'] = message_id
        
        # 保存用户消息
        self.db.save_message(conversation['conversation_id'], user_message)
        if 'messages' not in conversation:
            conversation['messages'] = []
        conversation['messages'].append(user_message)
        
        # 生成对话历史
        conversation_history = "\n".join([
            f"{msg['sender_type']}: {msg['content']}" 
            for msg in conversation.get('messages', [])
        ])
        
        accumulated_response = ""
        
        try:
            async for text_chunk in self.llm_service.generate_stream(conversation_history, generation_id):
                # 清理特殊标记
                cleaned_chunk = text_chunk
                if "<|im_start|>assistant" in cleaned_chunk:
                    cleaned_chunk = cleaned_chunk.split("<|im_start|>assistant")[-1].strip()
                if "<|im_end|>" in cleaned_chunk:
                    cleaned_chunk = cleaned_chunk.split("<|im_end|>")[0].strip()
                
                accumulated_response += cleaned_chunk
                yield cleaned_chunk
                
        except Exception as e:
            error_message = f"\n\n[错误: {str(e)}]"
            yield error_message
            accumulated_response = f"[错误: {str(e)}]"
        
        # 保存助手消息
        assistant_message = self._create_assistant_message(accumulated_response)
        assistant_message['sequence_number'] = user_message['sequence_number'] + 1
        assistant_message['is_timeout'] = 1 if is_timeout else 0
        
        self.db.save_message(conversation['conversation_id'], assistant_message)
        conversation['messages'].append(assistant_message)
    
    def get_conversation_history(self, conversation_id):
        """获取会话历史"""
        if not conversation_id:
            return None
        
        # 优先从缓存获取
        for conversation in self.active_conversations.values():
            if conversation.get('conversation_id') == conversation_id:
                return conversation
        
        # 非主进程不查询数据库
        if not self.is_main_process:
            return None
        
        return self.db.get_conversation_by_id(conversation_id)
    
    def cleanup_cache(self):
        """清理过期缓存"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, conversation in self.active_conversations.items():
            last_active = datetime.strptime(conversation['last_active'], '%Y-%m-%d %H:%M:%S')
            if (current_time - last_active).total_seconds() > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.active_conversations[key]

# 全局实例管理
_global_conversation_manager = None
_conversation_manager_pid = None

def get_conversation_manager():
    """获取会话管理器单例"""
    global _global_conversation_manager, _conversation_manager_pid
    
    current_pid = os.getpid()
    
    if _global_conversation_manager is None or _conversation_manager_pid != current_pid:
        _global_conversation_manager = ConversationManager()
        _conversation_manager_pid = current_pid
    
    return _global_conversation_manager

conversation_manager = get_conversation_manager()