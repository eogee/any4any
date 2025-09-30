import os
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Optional
from core.chat.conversation_database import ConversationDatabase
from core.chat.llm import get_llm_service
from core.dingtalk.message_manager import message_dedup
from config import Config

logger = logging.getLogger(__name__)

class ConversationManager:
    """会话管理器"""
    def __init__(self):
        self.is_main_process = self._check_main_process()
        self.active_conversations = {}
        self.cache_ttl = 3600
        
        # 从配置获取延迟模式设置
        self.delay_mode_enabled = Config.DELAY_MODE
        self.delay_time = Config.DELAY_TIME
        
        # 延迟管理器将在初始化后设置
        self.delay_manager = None
        self.user_delay_status = {}
        self.pending_request_counts = {}
        
        if self.is_main_process:
            self.db = ConversationDatabase()
            self.llm_service = get_llm_service()
        else:
            self.db = None
            self.llm_service = None
    
    def set_delay_manager(self, delay_manager):
        """设置延迟管理器"""
        self.delay_manager = delay_manager
        # 注册延迟消息处理回调
        if self.delay_mode_enabled and self.delay_manager:
            self.delay_manager.add_processing_callback(self._handle_delayed_messages)
    
    def _check_main_process(self):
        """检查是否为主进程"""
        if os.environ.get('IS_MAIN_PROCESS') == 'true':
            return True
        current_port = os.environ.get('CURRENT_PORT', 'unknown')
        return current_port != '9999' and current_port != 'unknown'
    
    async def _handle_delayed_messages(self, request_data: dict):
        """处理延迟合并后的消息 延迟消息管理器的回调函数"""
        try:            
            # 从请求数据中提取必要信息
            sender = request_data.get('sender_id')
            user_nick = request_data.get('sender_name')
            platform = request_data.get('platform', 'dingtalk')
            combined_content = request_data.get('combined_content')
            
            if not all([sender, user_nick, combined_content]):
                logger.error("Missing required parameters in delayed message")
                return
            
            # 使用合并后的内容处理消息
            response, conversation_id = await self._process_immediately(
                sender=sender,
                user_nick=user_nick,
                platform=platform,
                content=combined_content,
                is_timeout=False,
                message_id=None,  # 使用新的消息ID
                skip_save=False
            )
            
            # 存储处理结果到用户状态 - 所有等待的请求共享同一个结果
            if sender in self.user_delay_status:
                self.user_delay_status[sender]['result'] = {
                    'response': response,
                    'conversation_id': conversation_id
                }
                self.user_delay_status[sender]['processed'] = True
                # 通知所有等待的请求
                if self.user_delay_status[sender].get('completion_event'):
                    self.user_delay_status[sender]['completion_event'].set()
            
        except Exception as e:
            logger.error(f"Error processing delayed messages: {e}", exc_info=True)
            # 设置错误响应
            sender = request_data.get('sender_id')
            if sender in self.user_delay_status:
                self.user_delay_status[sender]['result'] = {
                    'response': f"处理延迟消息时出错: {str(e)}",
                    'conversation_id': ""
                }
                self.user_delay_status[sender]['processed'] = True
                if self.user_delay_status[sender].get('completion_event'):
                    self.user_delay_status[sender]['completion_event'].set()
    
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
    
    async def _process_with_delay(self, sender, user_nick, platform, content, delay_time, message_id):
        """处理带延迟的消息并等待结果"""
        # 检查延迟管理器是否可用
        if not self.delay_manager:
            logger.error("Delay manager not available, processing immediately")
            return await self._process_immediately(
                sender=sender,
                user_nick=user_nick,
                platform=platform,
                content=content,
                message_id=message_id
            )
        
        # 检查是否已经有在处理中的延迟请求
        if sender in self.user_delay_status and self.user_delay_status[sender].get('processing'):
            # 增加等待计数
            if sender not in self.pending_request_counts:
                self.pending_request_counts[sender] = 0
            self.pending_request_counts[sender] += 1
            
            # 后续消息也需要添加到延迟管理器，这样才能被合并
            request_data = {
                'sender_id': sender,
                'sender_name': user_nick,
                'platform': platform,
                'user_message': content
            }
            
            await self.delay_manager.add_message(
                user_id=sender,
                content=content,
                request_data=request_data,
                delay_time=delay_time
            )
            
            # 后续请求，我们返回一个特殊的标记,确保不立即发送响应
            return "DELAY_PROCESSING", "delay_processing"
            
        else:
            # 初始化用户延迟状态
            self.user_delay_status[sender] = {
                'processing': True,
                'processed': False,
                'result': None,
                'completion_event': asyncio.Event(),
                'start_time': asyncio.get_event_loop().time(),
                'completed_count': 0,  # 记录已完成请求的数量
                'waiting_requests': set(),  # 记录所有等待的请求ID
                'is_first_request': True  # 标记这是第一个请求
            }
            
            # 初始化等待计数
            self.pending_request_counts[sender] = 1
            
            # 记录当前请求
            if message_id:
                self.user_delay_status[sender]['waiting_requests'].add(message_id)
            
            request_data = {
                'sender_id': sender,
                'sender_name': user_nick,
                'platform': platform,
                'user_message': content
            }
            
            # 添加第一条消息到延迟管理器
            await self.delay_manager.add_message(
                user_id=sender,
                content=content,
                request_data=request_data,
                delay_time=delay_time
            )
        
        # 等待处理完成
        completion_event = self.user_delay_status[sender]['completion_event']
        start_time = self.user_delay_status[sender]['start_time']
        timeout = delay_time + 30  # 延迟时间 + 30秒缓冲
        
        try:
            # 等待处理完成事件
            await asyncio.wait_for(completion_event.wait(), timeout=timeout)
            
            # 获取处理结果 - 所有等待的请求都返回相同的结果
            if (self.user_delay_status.get(sender) and 
                self.user_delay_status[sender].get('processed') and 
                self.user_delay_status[sender].get('result')):
                
                result = self.user_delay_status[sender]['result']
                response = result.get('response', '处理完成')
                conversation_id = result.get('conversation_id', '')
                
                # 增加已完成计数
                self.user_delay_status[sender]['completed_count'] += 1
                completed_count = self.user_delay_status[sender]['completed_count']
                total_requests = self.pending_request_counts.get(sender, 1)
                
                # 如果所有等待的请求都已完成，清理状态
                if completed_count >= total_requests:
                    if sender in self.user_delay_status:
                        del self.user_delay_status[sender]
                    if sender in self.pending_request_counts:
                        del self.pending_request_counts[sender]
                
                return response, conversation_id
            else:
                logger.warning(f"Delay message processing status error, user: {user_nick}, status: {self.user_delay_status.get(sender)}")
                # 清理异常状态
                if sender in self.user_delay_status:
                    del self.user_delay_status[sender]
                if sender in self.pending_request_counts:
                    del self.pending_request_counts[sender]
                return "消息处理异常，请稍后重试。", ""
                
        except asyncio.TimeoutError:
            logger.warning(f"Delay message processing timeout, user: {user_nick}")
            # 清理超时的用户状态
            if sender in self.user_delay_status:
                del self.user_delay_status[sender]
            if sender in self.pending_request_counts:
                del self.pending_request_counts[sender]
            return "消息处理超时，请稍后重试。", ""
    
    async def _process_immediately(self, sender, user_nick, platform, content, is_timeout=False, message_id=None, skip_save=False):
        """立即处理消息"""
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
    
    async def process_message(self, sender, user_nick, platform, content, is_timeout=False, message_id=None, skip_save=False, delay_time: Optional[int] = None, is_delayed_processing=False):
        """处理用户消息"""
        # 检查消息是否已处理
        if message_id and self._check_message_processed(message_id):
            return "", ""

        # 非主进程检查
        if not self.is_main_process:
            return "该请求需要在主进程中处理。", "non_main_process"

        # 参数验证
        if not all([sender, user_nick, platform, content]):
            raise ValueError("Missing required parameters")

        # 如果启用了延迟模式且不是延迟处理阶段，使用延迟消息管理器
        if self.delay_mode_enabled and not is_delayed_processing:
            # 使用传入的delay_time或配置的默认延迟时间
            actual_delay_time = delay_time if delay_time is not None else self.delay_time
            
            # 使用延迟处理并等待结果
            response, conversation_id = await self._process_with_delay(
                sender=sender,
                user_nick=user_nick,
                platform=platform,
                content=content,
                delay_time=actual_delay_time,
                message_id=message_id
            )
            
            return response, conversation_id
        
        # 直接处理消息
        return await self._process_immediately(
            sender=sender,
            user_nick=user_nick,
            platform=platform,
            content=content,
            is_timeout=is_timeout,
            message_id=message_id,
            skip_save=skip_save
        )
    
    async def process_message_stream(self, sender, user_nick, platform, content, generation_id, is_timeout=False, message_id=None, delay_time: Optional[int] = None, is_delayed_processing=False):
        """流式处理用户消息 流式响应不支持延迟功能"""
        
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
    
    def get_buffered_message_count(self, user_id: str) -> int:
        """获取用户缓冲消息数量"""
        if self.delay_manager:
            return self.delay_manager.get_buffered_count(user_id)
        return 0
    
    def clear_user_buffers(self, user_id: str):
        """清空用户消息缓冲区"""
        if self.delay_manager:
            self.delay_manager.clear_buffers(user_id)
        # 清理用户延迟状态
        if user_id in self.user_delay_status:
            del self.user_delay_status[user_id]
        if user_id in self.pending_request_counts:
            del self.pending_request_counts[user_id]
    
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
        
        # 清理过期的用户延迟状态
        current_timestamp = asyncio.get_event_loop().time()
        expired_users = []
        for user_id, status in self.user_delay_status.items():
            if current_timestamp - status.get('start_time', current_timestamp) > 3600:  # 1小时
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_delay_status[user_id]
            if user_id in self.pending_request_counts:
                del self.pending_request_counts[user_id]

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