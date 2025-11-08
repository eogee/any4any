import os
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Optional
from core.chat.conversation_database import ConversationDatabase
from core.chat.llm import llm_service
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
            self.llm_service = llm_service
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
            response, conversation_id, assistant_message_id = await self._process_immediately(
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
                    'conversation_id': conversation_id,
                    'assistant_message_id': assistant_message_id
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
                    'conversation_id': "",
                    'assistant_message_id': None
                }
                self.user_delay_status[sender]['processed'] = True
                if self.user_delay_status[sender].get('completion_event'):
                    self.user_delay_status[sender]['completion_event'].set()
    
    def _generate_message_id(self):
        return str(uuid.uuid4())

    def _truncate_conversation_history(self, messages):
        """截断对话历史以控制token数量"""
        if not getattr(Config, 'ENABLE_CONVERSATION_TRUNCATION', True):
            return messages

        max_messages = getattr(Config, 'MAX_CONVERSATION_MESSAGES', 20)
        max_tokens = getattr(Config, 'MAX_CONVERSATION_TOKENS', 8000)

        if not messages or len(messages) <= max_messages:
            return messages

        
        truncated_messages = messages[-max_messages:] # 保留最近的消息，确保是成对的对话

        conversation_text = "\n".join([ # 进一步基于token数量截断
            f"{msg.get('sender_type', msg.get('role', 'unknown'))}: {msg['content']}"
            for msg in truncated_messages
        ])

        estimated_tokens = len(conversation_text) * 1.2 #中文字符*1.5 + 英文单词*1

        if estimated_tokens > max_tokens:

            final_messages = [] # 从后往前逐条添加消息，直到不超过token限制
            current_tokens = 0

            for msg in reversed(truncated_messages):
                msg_text = f"{msg.get('sender_type', msg.get('role', 'unknown'))}: {msg['content']}"
                msg_tokens = len(msg_text) * 1.2

                if current_tokens + msg_tokens > max_tokens and final_messages:
                    break

                final_messages.insert(0, msg)
                current_tokens += msg_tokens

            truncated_messages = final_messages

        return truncated_messages
    
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
                is_timeout=False,
                message_id=message_id,
                skip_save=False
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
        timeout = delay_time + 60  # 延迟时间 + 60秒缓冲，给NL2SQL回退处理留出足够时间
        
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
                assistant_message_id = result.get('assistant_message_id', None)
                
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

                return response, conversation_id, assistant_message_id
            else:
                logger.warning(f"Delay message processing status error, user: {user_nick}, status: {self.user_delay_status.get(sender)}")
                # 清理异常状态
                if sender in self.user_delay_status:
                    del self.user_delay_status[sender]
                if sender in self.pending_request_counts:
                    del self.pending_request_counts[sender]
                return "消息处理异常，请稍后重试。", "", None
                
        except asyncio.TimeoutError:
            logger.warning(f"Delay message processing timeout, user: {user_nick}")
            # 清理超时的用户状态
            if sender in self.user_delay_status:
                del self.user_delay_status[sender]
            if sender in self.pending_request_counts:
                del self.pending_request_counts[sender]
            return "消息处理超时，请稍后重试。", "", None
    
    async def _process_immediately(self, sender, user_nick, platform, content, is_timeout=False, message_id=None, skip_save=False, force_web_search=False):
        """立即处理消息"""
        # 新建会话指令
        if content.strip() == '/a':
            new_conversation = self.db.create_new_conversation(sender, user_nick, platform)
            self.active_conversations[(sender, platform)] = new_conversation
            return "新会话已开启。", new_conversation['conversation_id'], None
        
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

        # 获取并截断对话历史
        all_messages = conversation.get('messages', [])
        truncated_messages = self._truncate_conversation_history(all_messages)

        # 生成对话历史
        conversation_history = "\n".join([
            f"{msg.get('sender_type', msg.get('role', 'unknown'))}: {msg['content']}"
            for msg in truncated_messages
        ])

        try:
            # 生成响应 - 检查是否启用工具
            if (hasattr(self.llm_service, 'process_with_tools') and
                self.llm_service.is_tool_supported()):
                response_text = await self.llm_service.process_with_tools(
                    content,
                    conversation_manager=self,
                    user_id=sender,
                    platform=platform,
                    force_web_search=force_web_search
                )
            else:
                # 检查LLM服务类型，为外部API提供正确的消息格式
                if self.llm_service.service_type == "external":
                    # 外部LLM需要OpenAI格式的messages数组
                    openai_messages = self._convert_to_openai_format(truncated_messages)
                    response_text = await self.llm_service.generate_response(openai_messages)
                else:
                    # 本地LLM使用对话历史字符串
                    response_text = await self.llm_service.generate_response(conversation_history)

            # 创建助手消息
            assistant_message = self._create_assistant_message(response_text)
            assistant_message['sequence_number'] = user_message['sequence_number'] + 1
            assistant_message['is_timeout'] = 1 if is_timeout else 0

            if not skip_save:
                self.db.save_message(conversation['conversation_id'], assistant_message)
                conversation['messages'].append(assistant_message)

            return response_text, conversation['conversation_id'], assistant_message['message_id']
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            error_message = "抱歉，暂时无法生成回复。请稍后再试。"
            
            error_assistant_message = self._create_assistant_message(error_message)
            error_assistant_message['sequence_number'] = user_message['sequence_number'] + 1
            error_assistant_message['is_timeout'] = 1 if is_timeout else 0
            
            if not skip_save:
                self.db.save_message(conversation['conversation_id'], error_assistant_message)
            
            return error_message, conversation['conversation_id'], error_assistant_message['message_id']
    
    async def process_message(self, sender, user_nick, platform, content, is_timeout=False, message_id=None, skip_save=False, delay_time: Optional[int] = None, is_delayed_processing=False, force_web_search=False):
        """处理用户消息"""
        # 检查消息是否已处理
        if message_id and self._check_message_processed(message_id):
            return "", "", None

        # 非主进程检查
        if not self.is_main_process:
            return "该请求需要在主进程中处理。", "non_main_process", None

        # 参数验证
        if not all([sender, user_nick, platform, content]):
            raise ValueError("Missing required parameters")

        # 如果启用了延迟模式且不是延迟处理阶段，使用延迟消息管理器
        if self.delay_mode_enabled and not is_delayed_processing:
            # 使用传入的delay_time或配置的默认延迟时间
            actual_delay_time = delay_time if delay_time is not None else self.delay_time
            
            # 使用延迟处理并等待结果
            response, conversation_id, assistant_message_id = await self._process_with_delay(
                sender=sender,
                user_nick=user_nick,
                platform=platform,
                content=content,
                delay_time=actual_delay_time,
                message_id=message_id
            )

            return response, conversation_id, assistant_message_id
        
        # 直接处理消息
        response, conversation_id, assistant_message_id = await self._process_immediately(
            sender=sender,
            user_nick=user_nick,
            platform=platform,
            content=content,
            is_timeout=is_timeout,
            message_id=message_id,
            skip_save=skip_save,
            force_web_search=force_web_search
        )

        # 返回处理结果
        return response, conversation_id, assistant_message_id
    
    async def process_message_stream(self, sender, user_nick, platform, content, generation_id, is_timeout=False, message_id=None, delay_time: Optional[int] = None, is_delayed_processing=False, force_web_search=False):
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

        # 获取并截断对话历史（流式处理也需要截断）
        all_messages = conversation.get('messages', [])
        truncated_messages = self._truncate_conversation_history(all_messages)

        # 生成对话历史
        conversation_history = "\n".join([
            f"{msg.get('sender_type', msg.get('role', 'unknown'))}: {msg['content']}"
            for msg in truncated_messages
        ])


        accumulated_response = ""
        
        try:
            # 检查是否启用工具调用
            if (hasattr(self.llm_service, 'process_with_tools') and
                self.llm_service.is_tool_supported()):
                # 对于流式处理，先获取完整响应，然后分段返回
                full_response = await self.llm_service.process_with_tools(
                    content,
                    conversation_manager=self,
                    user_id=sender,
                    platform=platform,
                    force_web_search=force_web_search
                )
                accumulated_response = full_response

                # 模拟流式输出 - 分段返回响应
                words = full_response.split()
                for i, word in enumerate(words):
                    if i % 3 == 0:  # 每3个词一组
                        yield " ".join(words[i:i+3]) + " "
                    elif i == len(words) - 1:  # 最后一个词
                        yield word
            else:
                # 检查LLM服务类型，为外部API提供正确的消息格式
                if self.llm_service.service_type == "external":
                    # 外部LLM需要OpenAI格式的messages数组
                    openai_messages = self._convert_to_openai_format(truncated_messages)
                    async for text_chunk in self.llm_service.generate_stream(openai_messages, generation_id):
                        accumulated_response += text_chunk
                        yield text_chunk
                else:
                    # 本地LLM使用对话历史字符串
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

    def find_assistant_message_by_user_id(self, user_message_id: str) -> str:
        """根据用户消息ID查找对应的助手消息ID"""
        if not user_message_id:
            return None

        try:
            # 从数据库中查找对应的助手消息
            result = self.db.fetch_one(
                """SELECT m1.message_id
                   FROM messages m1
                   JOIN messages m2 ON m1.conversation_id = m2.conversation_id
                   WHERE m2.message_id = %s
                   AND m1.sender_type = 'assistant'
                   AND m2.sender_type = 'user'
                   AND m1.sequence_number = m2.sequence_number + 1
                   ORDER BY m1.timestamp DESC
                   LIMIT 1""",
                (user_message_id,)
            )

            if result:
                assistant_message_id = result.get('message_id')
                logger.info(f"Found assistant message {assistant_message_id} for user message {user_message_id}")
                return assistant_message_id
            else:
                logger.warning(f"No assistant message found for user message {user_message_id}")
                return None

        except Exception as e:
            logger.error(f"Error finding assistant message for user message {user_message_id}: {e}")
            return None

    async def update_message_timeout(self, message_id: str, is_timeout: bool = True) -> bool:
        """更新消息的超时状态（用于预览超时场景）"""
        if not message_id:
            logger.warning("No message_id provided for timeout update")
            return False

        try:
            # 如果传入的是用户消息ID，需要找到对应的助手消息ID
            assistant_message_id = message_id

            # 检查消息是否为用户消息，如果是则查找对应的助手消息
            message_info = self.db.fetch_one(
                "SELECT sender_type FROM messages WHERE message_id = %s",
                (message_id,)
            )

            if message_info and message_info['sender_type'] == 'user':
                logger.info(f"Message {message_id} is from user, finding corresponding assistant message")
                assistant_message_id = self.find_assistant_message_by_user_id(message_id)
                if not assistant_message_id:
                    logger.error(f"Could not find assistant message for user message {message_id}")
                    return False

            # 更新助手消息的超时状态
            success = self.db.update_message_timeout_status(assistant_message_id, is_timeout)
            if success:
                # 更新缓存中的消息状态（如果存在）
                cache_updated = False
                for conversation in self.active_conversations.values():
                    if 'messages' in conversation:
                        for msg in conversation['messages']:
                            if msg.get('message_id') == assistant_message_id and msg.get('sender_type') == 'assistant':
                                old_timeout = msg.get('is_timeout', 0)
                                msg['is_timeout'] = 1 if is_timeout else 0
                                cache_updated = True
                                break

                if not cache_updated:
                    logger.warning(f"Assistant message {assistant_message_id} not found in cache for update")

            else:
                logger.error(f"Database update failed for assistant message: {assistant_message_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to update message timeout: {e}")
            return False

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

    def _convert_to_openai_format(self, messages):
        """将内部消息格式转换为OpenAI格式"""
        openai_messages = []

        for msg in messages:
            sender_type = msg.get('sender_type', msg.get('role', 'unknown'))
            role = "user" if sender_type == "user" else "assistant"
            openai_messages.append({
                "role": role,
                "content": msg['content']
            })

        return openai_messages

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