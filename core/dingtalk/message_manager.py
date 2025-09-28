import logging
import time
import dingtalk_stream
import httpx
import json
import uuid
import os
import fcntl
import tempfile
import hashlib
import threading
from typing import Any, Optional
from config import Config
from dingtalk_stream import AckMessage
from core.log import setup_logging
from utils.content_handle.filter import filter_think_content
from alibabacloud_dingtalk.oauth2_1_0.client import Client as dingtalkoauth2_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.oauth2_1_0 import models as dingtalkoauth_2__1__0_models
from alibabacloud_dingtalk.robot_1_0.client import Client as dingtalkrobot_1_0Client
from alibabacloud_dingtalk.robot_1_0 import models as dingtalkrobot__1__0_models
from alibabacloud_tea_util import models as util_models
from core.chat.preview import preview_service

# 多进程安全的内存数据存储（使用文件锁和文件存储）
class MultiProcessSafeDataStore:
    def __init__(self, storage_file=None):
        # 使用临时文件或指定文件进行存储
        if storage_file:
            self.storage_file = storage_file
        else:
            self.storage_file = os.path.join(tempfile.gettempdir(), 'dingtalk_bot_data.json')
        
        self._lock_file = self.storage_file + '.lock'
        self._cleanup_interval = 300  # 5分钟清理一次过期数据
        self._last_cleanup = time.time()
        
        # 初始化存储文件
        self._init_storage_file()
    
    def _init_storage_file(self):
        """初始化存储文件"""
        if not os.path.exists(self.storage_file):
            with self._get_file_lock():
                if not os.path.exists(self.storage_file):
                    with open(self.storage_file, 'w', encoding='utf-8') as f:
                        json.dump({}, f)
                    logging.info(f"Initialized storage file: {self.storage_file}")
    
    def _get_file_lock(self):
        """获取文件锁（支持多进程）"""
        lock_file = open(self._lock_file, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return lock_file
    
    def _read_data(self):
        """读取存储数据"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_data(self, data):
        """写入存储数据"""
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def set(self, key: str, value: Any, expire_seconds: int = 300):
        """多进程安全地存储数据"""
        lock = self._get_file_lock()
        try:
            # 定期清理过期数据
            self._auto_cleanup()
            
            data = self._read_data()
            data[key] = {
                'value': value,
                'expire_time': time.time() + expire_seconds,
                'created_time': time.time(),
                'process_id': os.getpid()  # 记录是哪个进程创建的
            }
            self._write_data(data)
        finally:
            lock.close()
    
    def get(self, key: str) -> Optional[Any]:
        """多进程安全地获取数据"""
        lock = self._get_file_lock()
        try:
            self._auto_cleanup()
            
            data = self._read_data()
            if key in data:
                item = data[key]
                if time.time() < item['expire_time']:
                    return item['value']
                else:
                    # 自动清理过期数据
                    del data[key]
                    self._write_data(data)
            return None
        finally:
            lock.close()
    
    def delete(self, key: str) -> bool:
        """多进程安全地删除数据"""
        lock = self._get_file_lock()
        try:
            data = self._read_data()
            if key in data:
                del data[key]
                self._write_data(data)
                logging.info(f"Process {os.getpid()} deleted data for key: {key}")
                return True
            return False
        finally:
            lock.close()
    
    def _auto_cleanup(self):
        """自动清理过期数据"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        data = self._read_data()
        keys_to_remove = []
        for key, item in data.items():
            if current_time > item['expire_time']:
                keys_to_remove.append(key)
        
        if keys_to_remove:
            for key in keys_to_remove:
                del data[key]
            self._write_data(data)
            logging.info(f"Auto-cleaned {len(keys_to_remove)} expired records")
        
        self._last_cleanup = current_time

# 创建全局多进程安全的数据存储实例
memory_store = MultiProcessSafeDataStore()

# 超时处理状态管理器（新增）
class TimeoutMessageManager:
    def __init__(self):
        self.timeout_processed_messages = set()
        self.timeout_lock = threading.Lock()
        # 使用单独的文件存储超时状态，确保多进程间同步
        self.timeout_store = MultiProcessSafeDataStore(
            os.path.join(tempfile.gettempdir(), 'dingtalk_timeout_data.json')
        )
        logging.info("TimeoutMessageManager initialized")
    
    def mark_message_timeout_processed(self, message_id):
        """标记消息因超时已处理"""
        if not message_id:
            return
        
        with self.timeout_lock:
            self.timeout_processed_messages.add(message_id)
            # 同时存储到文件，确保多进程可见
            self.timeout_store.set(f"timeout_{message_id}", {
                'processed': True,
                'timestamp': time.time(),
                'process_id': os.getpid()
            }, expire_seconds=3600)  # 1小时过期
        logging.info(f"Message {message_id} marked as timeout-processed")
    
    def is_message_timeout_processed(self, message_id):
        """检查消息是否因超时已处理"""
        if not message_id:
            return False
        
        # 先检查内存
        if message_id in self.timeout_processed_messages:
            return True
        
        # 再检查文件存储
        timeout_data = self.timeout_store.get(f"timeout_{message_id}")
        if timeout_data:
            # 如果文件中有记录，同步到内存
            with self.timeout_lock:
                self.timeout_processed_messages.add(message_id)
            return True
        
        return False
    
    def cleanup_message_state(self, message_id):
        """清理消息状态"""
        if not message_id:
            return
        
        with self.timeout_lock:
            self.timeout_processed_messages.discard(message_id)
            self.timeout_store.delete(f"timeout_{message_id}")

# 创建全局超时消息管理器
timeout_manager = TimeoutMessageManager()

# 消息去重管理器（简化版）- 以消息ID为核心
class MessageDeduplication:
    def __init__(self):
        config = Config()
        self.dedup_window = config.PREVIEW_TIMEOUT + 300  # 去重窗口时间
        # 合并状态存储，简化管理
        self.status_store = MultiProcessSafeDataStore(
            os.path.join(tempfile.gettempdir(), 'dingtalk_message_status.json')
        )
        self.lock = threading.Lock()
        logging.info(f"Message deduplication initialized with window: {self.dedup_window} seconds")
    
    def check_and_mark_processing(self, msg_id, sender_id, content):
        """检查并标记消息状态（原子操作）
        
        Args:
            msg_id: 消息ID
            sender_id: 发送者ID
            content: 消息内容
            
        Returns:
            bool: True表示消息已处理或正在处理，False表示可以处理
        """
        if not msg_id:
            return False
            
        with self.lock:  # 确保原子操作
            current_status = self.status_store.get(msg_id)
            
            if current_status:
                status_type = current_status.get('status')
                # 已最终完成的消息直接拒绝
                if status_type in ['completed', 'timeout_processed']:
                    logging.info(f"Message {msg_id} already completed with status: {status_type}")
                    return True
                # 处理中的消息检查超时
                elif status_type == 'processing':
                    elapsed = time.time() - current_status.get('timestamp', 0)
                    if elapsed > self.dedup_window:
                        # 超时标记为失败，允许重新处理
                        logging.warning(f"Message {msg_id} processing timeout ({elapsed:.2f}s), allowing reprocessing")
                        self.status_store.set(msg_id, {
                            'status': 'timeout_failed',
                            'timestamp': time.time()
                        }, self.dedup_window)
                        return False
                    logging.info(f"Message {msg_id} is already processing")
                    return True
            
            # 标记为处理中
            self.status_store.set(msg_id, {
                'status': 'processing',
                'timestamp': time.time(),
                'sender_id': sender_id,
                'content': content[:100]  # 只存部分内容用于日志
            }, self.dedup_window)
            logging.info(f"Message {msg_id} marked as processing")
            return False
    
    def mark_final_status(self, msg_id, status='completed'):
        """标记最终状态
        
        Args:
            msg_id: 消息ID
            status: 最终状态 (completed, timeout_processed, failed, preview_failed)
        """
        if not msg_id:
            return
            
        with self.lock:  # 确保原子操作
            current = self.status_store.get(msg_id) or {}
            current.update({
                'status': status,
                'final_timestamp': time.time()
            })
            self.status_store.set(msg_id, current, self.dedup_window)
            logging.info(f"Message {msg_id} marked as {status}")

# 创建全局消息去重管理器
message_dedup = MessageDeduplication()

# 进程内令牌缓存（每个进程独立缓存）
_token_cache = {"token": None, "expire": 0}

class Options:
    def __init__(self):
        # 从配置文件加载参数
        self.client_id = Config.CLIENT_ID
        self.client_secret = Config.CLIENT_SECRET
        self.robot_code = Config.ROBOT_CODE
        self.msg = 'python-getting-start say：hello'  # 默认消息内容

def define_options():
    # 使用配置文件中的常量创建Options对象
    return Options()

def get_token(options):
    """
    使用钉钉SDK获取access_token，带本地缓存，2小时（7200秒）有效，提前200秒刷新。
    :param options: 配置对象，包含 client_id, client_secret
    :return: access_token字符串，获取失败返回None
    """
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expire"]:
        return _token_cache["token"]
    
    config = open_api_models.Config()
    config.protocol = 'https'
    config.region_id = 'central'
    client = dingtalkoauth2_1_0Client(config)
    get_access_token_request = dingtalkoauth_2__1__0_models.GetAccessTokenRequest(
        app_key=options.client_id,
        app_secret=options.client_secret
    )
    try:
        response = client.get_access_token(get_access_token_request)
        token = getattr(response.body, "access_token", None)
        expire_in = getattr(response.body, "expire_in", 7200)
        if token:
            _token_cache["token"] = token
            _token_cache["expire"] = now + expire_in - 200  # Refresh 200 seconds in advance
            logging.info(f"Process {os.getpid()} obtained access_token, valid until: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_token_cache['expire']))}")
        return token
    except Exception as err:
        logging.error(f"Process {os.getpid()} failed to get token: {err}")
        return None

def send_robot_private_message(access_token: str, options, user_ids: list, custom_msg=None):
    """
    使用钉钉SDK发送机器人私聊消息
    :param access_token: 已获取的 access_token
    :param options: 配置对象
    :param user_ids: 用户ID列表
    :param custom_msg: 自定义消息内容，如果为None则使用options.msg
    :return: 发送结果或 None
    """
    robot_code = options.robot_code
    msg_key = 'sampleText'
    msg_content = custom_msg if custom_msg else options.msg
    # 使用json.dumps安全地序列化消息内容，确保JSON格式正确
    msg_param = json.dumps({"content": msg_content})

    config = open_api_models.Config()
    config.protocol = 'https'
    config.region_id = 'central'
    client = dingtalkrobot_1_0Client(config)

    batch_send_otoheaders = dingtalkrobot__1__0_models.BatchSendOTOHeaders()
    batch_send_otoheaders.x_acs_dingtalk_access_token = access_token
    batch_send_otorequest = dingtalkrobot__1__0_models.BatchSendOTORequest(
        robot_code=robot_code,
        user_ids=user_ids,
        msg_key=msg_key,
        msg_param=msg_param
    )
    try:
        response = client.batch_send_otowith_options(
            batch_send_otorequest,
            batch_send_otoheaders,
            util_models.RuntimeOptions()
        )
        logging.info(f"Process {os.getpid()} sent message to user: {user_ids}")
        return response
    except Exception as err:
        logging.error(f"Process {os.getpid()} failed to send private message: {err}")
        return None

class EchoTextHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None, options=None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.options = options
        # 标记是否为预览模式的回调请求
        self.is_preview_callback = False
        # 进程ID用于日志记录
        self.process_id = os.getpid()

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        # 初始化关键变量
        msg_id = None
        sender_id = None
        original_content = None
        timeout_auto_sent = False
        
        try:
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            
            # 获取发送人信息
            sender_id = incoming_message.sender_staff_id
            user_nick = incoming_message.sender_nick
            
            # 获取消息内容
            original_content = getattr(incoming_message.text, 'content', '')
            
            # 严格获取消息ID（关键）
            msg_id = None
            # 方法1：从原始数据字典获取（优先级最高）
            if isinstance(callback.data, dict):
                msg_id = (callback.data.get('msgId') or 
                         callback.data.get('messageId') or 
                         callback.data.get('msgid'))
            
            # 方法2：从消息对象属性获取
            if not msg_id:
                msg_id = getattr(incoming_message, 'msgId', None)
                if not msg_id:
                    msg_id = getattr(incoming_message, 'messageId', None)
            
            # 方法3：从incoming_message的字典表示中获取
            if not msg_id:
                try:
                    msg_dict = incoming_message.to_dict() if hasattr(incoming_message, 'to_dict') else vars(incoming_message)
                    if isinstance(msg_dict, dict):
                        msg_id = msg_dict.get('msgId') or msg_dict.get('messageId')
                except Exception as e:
                    pass
            
            # 如果消息为空，直接返回
            if not original_content:
                self.logger.info(f"Empty message content, skipping processing")
                return AckMessage.STATUS_OK, 'OK'
            
            # 严格的消息状态检查（原子操作）
            if msg_id and message_dedup.check_and_mark_processing(msg_id, sender_id, original_content):
                self.logger.info(f"Message {msg_id} already processed or processing, skipped")
                return AckMessage.STATUS_OK, 'OK'
            
            # 控制台打印收到的消息信息
            self.logger.info(f"Received message - Sender: {sender_id}, MsgID: {msg_id}")                       
            
            # 防止消息循环：检查是否是机器人本身发送的消息
            if hasattr(incoming_message, 'chatbot_user_id') and incoming_message.sender_staff_id == incoming_message.chatbot_user_id:
                self.logger.info(f"Ignoring message sent by the robot itself to prevent loop")
                # 标记消息已处理
                if msg_id:
                    message_dedup.mark_final_status(msg_id, 'completed')
                return AckMessage.STATUS_OK, 'OK'
            
            # 构建发送到openai_api.chat_completions的请求体
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": original_content
                    }
                ],
                "model": "default",
                "stream": False,
                "temperature": Config.TEMPERATURE,
                "max_tokens": Config.MAX_LENGTH,
                "top_p": Config.TOP_P,
                "repetition_penalty": Config.REPETITION_PENALTY,
                "sender_id": sender_id,
                "sender_nickname": user_nick,
                "platform": "DingTalk",
                "msg_id": msg_id  # 添加消息ID用于去重
            }
            
            # 发送请求到app.py中的/v1/chat/completions接口
            self.logger.info(f"Process {self.process_id} forwarding message to OpenAI API: {original_content}")
            
            api_response = None
            timeout_auto_sent = False  # 标记是否因超时而自动发送
            reply_content = ""  # 初始化回复内容
            
            try:
                # 使用httpx发送异步HTTP请求
                async with httpx.AsyncClient() as client:
                    # 使用配置文件中的端口设置
                    api_url = f"http://localhost:{getattr(Config, 'PORT', 8888)}/v1/chat/completions"
                    response = await client.post(
                        api_url,
                        json=request_body,
                        timeout=message_dedup.dedup_window  # 增加超时时间大于PREVIEW_TIMEOUT+300秒，确保有足够时间等待预览超时
                    )
                    
                    # 检查响应状态
                    if response.status_code == 200:
                        # 解析响应内容
                        api_response = response.json()
                        self.logger.info(f"Process {self.process_id} received API response: {json.dumps(api_response, ensure_ascii=False)[:200]}...")
                        
                        # 检查是否为超时自动发送
                        if api_response and "timeout_auto_sent" in api_response:
                            timeout_auto_sent = api_response["timeout_auto_sent"]
                            self.logger.info(f"Process {self.process_id} response is auto-sent due to timeout: {timeout_auto_sent}")
                        
                        # 从响应中提取assistant的回复
                        if api_response and "choices" in api_response and len(api_response["choices"]) > 0:
                            if "message" in api_response["choices"][0] and "content" in api_response["choices"][0]["message"]:
                                reply_content = api_response["choices"][0]["message"]["content"]
                    
                            else:
                                reply_content = "Sorry, I couldn't generate a response."
                                self.logger.error(f"Process {self.process_id} invalid message format in API response: {api_response['choices'][0]}")
                        else:
                            reply_content = "Sorry, I couldn't generate a response."
                            self.logger.error(f"Process {self.process_id} invalid response format from OpenAI API: {api_response}")
                    else:
                        reply_content = f"Error: API returned status code {response.status_code}"
                        self.logger.error(f"Process {self.process_id} API request failed with status {response.status_code}: {response.text}")
            except httpx.TimeoutException:
                reply_content = "Error: Request timeout while calling OpenAI API"
                self.logger.error(f"Process {self.process_id} timeout occurred while calling OpenAI API")
            except Exception as api_err:
                reply_content = f"Error: {str(api_err)}"
                self.logger.error(f"Process {self.process_id} exception occurred while calling OpenAI API: {api_err}")
            
            # 如果回复内容为空，设置默认错误消息
            if not reply_content:
                reply_content = "Error: No response content received"
                self.logger.error(f"Reply content is empty")
            
            # 获取access_token用于发送钉钉回复
            access_token = get_token(self.options)
            if not access_token:
                self.logger.error(f"Failed to get access_token, unable to reply message")
                # 标记消息已处理（即使失败也要标记，避免重复处理）
                if msg_id:
                    message_dedup.mark_final_status(msg_id, 'failed')
                return AckMessage.STATUS_OK, 'OK'
            
            # 根据配置中的NO_THINK设置，过滤掉</think>和</think>之间的内容
            if hasattr(Config, 'NO_THINK') and Config.NO_THINK:
                reply_content = filter_think_content(reply_content)    
            
            # 检查是否为预览模式且不是超时自动发送的情况
            if Config.PREVIEW_MODE and not self.is_preview_callback and not timeout_auto_sent:
                # 预览模式：不直接发送回复，存储消息等待确认
                request_id = str(uuid.uuid4())
                
                # 尝试从API响应中提取preview_id
                preview_id = None
                if isinstance(api_response, dict):
                    if 'preview_id' in api_response:
                        preview_id = api_response['preview_id']
                    elif 'choices' in api_response:
                        for choice in api_response['choices']:
                            if isinstance(choice, dict) and 'preview_id' in choice:
                                preview_id = choice['preview_id']
                                break
                    elif 'response' in api_response:
                        response_obj = api_response['response']
                        if isinstance(response_obj, dict) and 'preview_id' in response_obj:
                            preview_id = response_obj['preview_id']
                
                # 如仍然没找到preview_id，生成一个并使用
                if not preview_id and Config.PREVIEW_MODE:
                    preview_id = f"preview_{int(time.time())}_{sender_id}_{self.process_id}"  # 添加进程ID避免冲突
                    self.logger.warning(f"Process {self.process_id} no preview_id found in response, generating one: {preview_id}")
                
                if preview_id:                        
                    # 存储必要的信息到共享存储中，设置过期时间为去重窗口时间
                    preview_data = {
                        'sender': sender_id,
                        'sender_name': user_nick,
                        'original_content': original_content,
                        'request_id': request_id,
                        'content': reply_content,
                        'options': self.options.__dict__,
                        'timestamp': time.time(),
                        'process_id': self.process_id,
                        'msg_id': msg_id,
                        'message_timestamp': message_timestamp
                    }
                    
                    # 使用去重窗口作为过期时间，确保在去重期间数据有效
                    memory_store.set(preview_id, preview_data, expire_seconds=message_dedup.dedup_window)
                    self.logger.info(f"Process {self.process_id} stored preview data for preview_id: {preview_id}, waiting for confirmation")
                    
                    # 标记消息已处理（预览模式下，等待确认后再发送）
                    if msg_id:
                        message_dedup.mark_final_status(msg_id, 'preview_pending')
                else:
                    self.logger.error(f"Process {self.process_id} failed to get preview_id, falling back to direct send")
                    # 如果无法获取preview_id，直接发送回复
                    result = send_robot_private_message(
                        access_token, 
                        self.options, 
                        [sender_id], 
                        reply_content
                    )
                    if result:
                        self.logger.info(f"Process {self.process_id} fallback: successfully sent reply to user")
                    else:
                        self.logger.error(f"Process {self.process_id} fallback: failed to send reply to user")
                    
                    # 标记消息已处理
                    message_dedup.mark_message_processed(sender_id, original_content, msg_id, session_id, message_timestamp)
                    message_processed = True
            else:
                # 非预览模式、预览确认后的回调、或超时自动发送的情况，直接发送回复消息
                self.logger.info(f"Process {self.process_id} sending reply directly (preview_mode: {Config.PREVIEW_MODE}, timeout_auto_sent: {timeout_auto_sent})")
                
                # 如果是超时自动发送，标记消息为超时已处理
                if timeout_auto_sent:
                    timeout_manager.mark_message_timeout_processed(msg_id)
                    self.logger.info(f"Message marked as timeout-processed: {msg_id}")
                
                result = send_robot_private_message(
                    access_token, 
                    self.options, 
                    [sender_id], 
                    reply_content
                )
                
                if result:
                    if timeout_auto_sent:
                        self.logger.info(f"Auto-sent reply to user due to timeout")
                        if msg_id:
                            message_dedup.mark_final_status(msg_id, 'timeout_processed')
                    else:
                        self.logger.info(f"Successfully sent reply to user")
                        if msg_id:
                            message_dedup.mark_final_status(msg_id, 'completed')
                else:
                    self.logger.error(f"Failed to send reply to user")
                    if msg_id:
                        message_dedup.mark_final_status(msg_id, 'failed')
                
        except Exception as e:
            self.logger.error(f"Exception occurred while processing message: {e}")
            # 标记错误状态
            if msg_id:
                message_dedup.mark_final_status(msg_id, 'failed')
        
        return AckMessage.STATUS_OK, 'OK'

async def send_reply_after_preview_confirm(preview_id: str, confirmed_content: str, request_data=None) -> bool:
    """
    预览确认后发送回复给钉钉用户
    """
    logger = logging.getLogger('core.dingtalk.message_manager')
    current_process_id = os.getpid()
    
    try:
        # 从多进程安全的存储中获取消息数据
        message_data = memory_store.get(preview_id)
        
        # 如果数据不存在，尝试使用request_data中的信息
        if not message_data:
            logger.warning(f"Process {current_process_id} no data found in memory for preview_id: {preview_id}")
            # 尝试从request_data中提取必要信息
            if request_data and isinstance(request_data, dict):
                # 构建基本的消息数据
                message_data = {
                    'content': confirmed_content,  # 使用确认的内容
                    'sender': None,  # 稍后填充
                    'sender_name': 'User',  # 默认值
                    'full_request': request_data
                }
                
                # 尝试从request_data的不同位置获取sender_id
                sender_id_sources = [
                    request_data.get('sender_id'),
                    request_data.get('user_id'),
                    request_data.get('sender'),
                    request_data.get('from_user_id'),
                    request_data.get('user', {}).get('id')
                ]
                
                # 遍历所有可能的来源，找到非None的sender_id
                for sender_id in sender_id_sources:
                    if sender_id:
                        message_data['sender'] = sender_id
                        break
                
                # 如果没有找到sender_id，尝试从preview_id中提取（格式为preview_timestamp_senderId_processId）
                if not message_data['sender'] and '_' in preview_id:
                    parts = preview_id.split('_')
                    if len(parts) >= 3:
                        # 尝试从preview_id中提取sender_id（第三个部分）
                        potential_sender_id = parts[2]
                        if potential_sender_id and not potential_sender_id.isdigit():
                            # sender_id通常不是纯数字，而是类似035266212437873268这样的格式
                            message_data['sender'] = potential_sender_id
                
                # 获取sender_name
                sender_name_sources = [
                    request_data.get('sender_nickname'),
                    request_data.get('user_name'),
                    request_data.get('nickname'),
                    request_data.get('user', {}).get('name')
                ]
                
                for sender_name in sender_name_sources:
                    if sender_name:
                        message_data['sender_name'] = sender_name
                        break
                
                # 如果仍然没有找到sender_id，尝试从预览服务获取
                if not message_data['sender']:
                    try:
                        preview = await preview_service.get_preview(preview_id)
                        if preview and preview.request_data:
                            # 再次尝试从preview.request_data中提取sender_id
                            for sender_id in sender_id_sources:
                                if sender_id:
                                    message_data['sender'] = sender_id
                                    break
                    except Exception as e:
                        logger.warning(f"Process {current_process_id} failed to get preview from preview_service: {e}")
                
                # 如果仍然没有sender_id，记录错误
                if not message_data['sender']:
                    logger.error(f"Process {current_process_id} cannot find sender_id in any source")
                    return False
            else:
                logger.error(f"Process {current_process_id} no data found for preview_id: {preview_id} and no request_data available, cannot process")
                return False
        
        # 从存储中获取数据
        sender_id = message_data.get('sender')
        sender_name = message_data.get('sender_name')
        original_content = message_data.get('original_content')
        request_id = message_data.get('request_id')
        options_dict = message_data.get('options', {})
        original_process_id = message_data.get('process_id', 'unknown')
        session_id = message_data.get('session_id')
        msg_id = message_data.get('msg_id')
        message_timestamp = message_data.get('message_timestamp')       
        
        # 检查是否获取到关键字段
        if not all([sender_id, sender_name]):
            # 如果缺少sender_id，尝试其他方式获取
            if not sender_id and request_data:
                sender_id = request_data.get('sender_id')
                sender_name = request_data.get('sender_nickname', 'User')
                
            if not sender_id:
                logger.error(f"Process {current_process_id} missing critical fields for preview_id {preview_id}: sender_id={sender_id}, sender_name={sender_name}")
                # 从内存中删除数据（如果存在）
                if preview_id in memory_store._read_data():
                    memory_store.delete(preview_id)
                return False
        
        # 创建默认的options对象，始终使用配置中的值
        options = Options()
        
        # 确定要发送的内容
        content_to_send = confirmed_content
        if not confirmed_content:
            content_to_send = message_data.get('content', '')
        
        # 根据配置中的NO_THINK设置，过滤内容
        if hasattr(Config, 'NO_THINK') and Config.NO_THINK:
            content_to_send = filter_think_content(content_to_send)      

        result = False
        try:
            # 获取最新的access_token
            current_access_token = get_token(options)
            if not current_access_token:
                logger.error(f"Process {current_process_id} failed to get access_token, cannot send message")
                return False
            
            # 检查消息是否已有最终状态（简化检查）
            if msg_id and message_dedup.status_store.get(msg_id):
                current_status = message_dedup.status_store.get(msg_id)
                if current_status.get('status') in ['completed', 'timeout_processed']:
                    logger.warning(f"Message {msg_id} already has final status: {current_status.get('status')}, skipping preview confirmation")
                    memory_store.delete(preview_id)
                    return False
            
            # 尝试发送消息
            result = send_robot_private_message(
                current_access_token,
                options,
                [sender_id],
                content_to_send
            )
            
            if result is False or result is None:
                logger.warning(f"Process {current_process_id} send_robot_private_message returned failure or None")
        except Exception as e:
            logger.error(f"Process {current_process_id} exception when sending message: {e}")
            result = False
        
        # 从内存中删除数据（如果存在），防止重复处理
        if preview_id in memory_store._read_data():
            memory_store.delete(preview_id)
        
        if result:
            logger.info(f"Successfully sent reply to user after preview confirmation")
            # 发送成功后标记最终状态
            if msg_id:
                message_dedup.mark_final_status(msg_id, 'completed')
        else:
            logger.error(f"Failed to send reply to user after preview confirmation")
            # 发送失败标记状态
            if msg_id:
                message_dedup.mark_final_status(msg_id, 'preview_failed')
        
        return result
    except Exception as e:
        logger.error(f"Unexpected error in send_reply_after_preview_confirm: {e}")
        # 确保异常时也清理数据
        memory_store.delete(preview_id)
        # 异常时标记失败状态
        if msg_id:
            message_dedup.mark_final_status(msg_id, 'preview_failed')
        return False

# 注册预览确认回调
def register_preview_confirm_callback():
    """
    注册预览确认回调函数到preview_service，用于在用户确认预览后发送钉钉消息
    """
    
    async def wrapped_confirm_preview(preview_id, content, request_data):
        """包装的预览确认回调函数"""
        current_process_id = os.getpid()
        try:
            success = await send_reply_after_preview_confirm(preview_id, content, request_data)
            if not success:
                logging.error(f"Process {current_process_id} failed to send reply for preview {preview_id}")
        except Exception as e:
            logging.error(f"Process {current_process_id} error in preview confirm callback: {e}")
            memory_store.delete(preview_id)
    
    # 注册回调到preview_service
    preview_service.register_confirm_callback(wrapped_confirm_preview)
    logging.info(f"Process {os.getpid()} preview confirm callback registered with preview_service")
    return wrapped_confirm_preview

def main():
    # 使用全局日志配置
    setup_logging()
    logger = logging.getLogger(__name__)
    current_process_id = os.getpid()
    
    # 注册预览确认回调
    if Config.PREVIEW_MODE:
        register_preview_confirm_callback()
        logging.info(f"Process {current_process_id} preview confirm callback registered with preview_service")
    
    options = define_options()
    
    # 检查配置是否完整
    if not all([options.client_id, options.client_secret, options.robot_code]):
        logger.error(f"Process {current_process_id} DingTalk robot configuration is incomplete. Please check CLIENT_ID, CLIENT_SECRET and ROBOT_CODE in .env file")
        return
    
    # 获取并验证端口配置
    try:
        dingtalk_port = int(Config.DINGTALK_PORT)
    except ValueError:
        logger.error(f"Process {current_process_id} invalid DingTalk port configuration: {Config.DINGTALK_PORT}")
        return
    
    # 打印启动信息
    logger.info(f"Process {current_process_id} starting DingTalk robot, Robot Code: {options.robot_code}, Listening on port: {dingtalk_port}")
    
    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    # 创建钉钉流客户端
    client = dingtalk_stream.DingTalkStreamClient(
        credential
    )
    
    # 注册消息处理器
    client.register_callback_handler(
        dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
        EchoTextHandler(logger, options)
    )
    
    logger.info(f"Process {current_process_id} DingTalk robot started successfully, begin listening for messages...")
    client.start_forever()