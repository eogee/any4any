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

# 消息去重管理器（多进程安全）- 改进版本
class MessageDeduplication:
    def __init__(self):
        # 使用配置中的 PREVIEW_TIMEOUT + 300 作为去重窗口
        config = Config()
        self.preview_timeout = config.PREVIEW_TIMEOUT
        self.dedup_window = self.preview_timeout + 300  # PREVIEW_TIMEOUT + 300秒
        
        self.dedup_store = MultiProcessSafeDataStore(
            os.path.join(tempfile.gettempdir(), 'dingtalk_dedup_data.json')
        )
        # 存储正在处理的消息，防止并发处理
        self.processing_store = MultiProcessSafeDataStore(
            os.path.join(tempfile.gettempdir(), 'dingtalk_processing_data.json')
        )
        
        logging.info(f"Message deduplication initialized with window: {self.dedup_window} seconds (PREVIEW_TIMEOUT: {self.preview_timeout} + 300)")
    
    def generate_message_fingerprint(self, sender_id, content, msg_id=None, session_id=None, timestamp=None):
        """生成消息指纹用于去重"""
        # 如果msg_id存在，优先使用msg_id（最准确）
        if msg_id and msg_id != 'None':
            return f"msgid_{msg_id}"
        
        # 否则使用发送者ID、内容、会话ID和时间戳组合
        fingerprint_data = f"{sender_id}:{content}"
        if session_id:
            fingerprint_data += f":{session_id}"
        if timestamp:
            fingerprint_data += f":{int(timestamp)}"
        else:
            fingerprint_data += f":{int(time.time())}"
        
        return hashlib.md5(fingerprint_data.encode('utf-8')).hexdigest()
    
    def is_duplicate_or_processing(self, sender_id, content, msg_id=None, session_id=None, timestamp=None):
        """检查是否为重复消息或正在处理的消息"""
        fingerprint = self.generate_message_fingerprint(sender_id, content, msg_id, session_id, timestamp)
        
        # 检查是否正在处理该消息
        if self.processing_store.get(fingerprint):
            logging.info(f"Message is already being processed: {fingerprint}")
            return True
        
        # 检查是否已经处理过该消息
        existing = self.dedup_store.get(fingerprint)
        if existing:
            logging.info(f"Duplicate message detected and ignored: {fingerprint}")
            return True
        
        # 标记该消息为正在处理
        self.processing_store.set(fingerprint, {
            'sender_id': sender_id,
            'content': content,
            'timestamp': time.time(),
            'msg_id': msg_id,
            'session_id': session_id
        }, expire_seconds=self.dedup_window)  # 处理超时时间大于PREVIEW_TIMEOUT+300秒
        
        return False
    
    def mark_message_processed(self, sender_id, content, msg_id=None, session_id=None, timestamp=None):
        """标记消息已处理完成"""
        fingerprint = self.generate_message_fingerprint(sender_id, content, msg_id, session_id, timestamp)
        
        # 从正在处理列表中移除
        self.processing_store.delete(fingerprint)
        
        # 记录到去重列表，设置去重窗口
        self.dedup_store.set(fingerprint, {
            'sender_id': sender_id,
            'content': content,
            'timestamp': time.time(),
            'msg_id': msg_id,
            'session_id': session_id
        }, expire_seconds=self.dedup_window)
        
        

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
        # 用于标记消息是否已处理
        message_processed = False
        sender_id = None
        original_content = None
        msg_id = None
        session_id = None
        message_timestamp = None
        
        try:
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            
            # 获取发送人信息
            sender_id = incoming_message.sender_staff_id
            user_nick = incoming_message.sender_nick
            
            # 获取消息内容
            original_content = getattr(incoming_message.text, 'content', '')
            
            # 尝试多种方式获取msgId
            msg_id = None
            
            # 方法1：从消息对象属性获取
            msg_id = getattr(incoming_message, 'msgId', None)
            if not msg_id:
                msg_id = getattr(incoming_message, 'messageId', None)
            
            # 方法2：从原始数据字典获取
            if not msg_id and isinstance(callback.data, dict):
                msg_id = callback.data.get('msgId')
                if not msg_id:
                    msg_id = callback.data.get('messageId')
                if not msg_id:
                    # 尝试深入数据结构查找
                    if 'message' in callback.data and isinstance(callback.data['message'], dict):
                        msg_id = callback.data['message'].get('msgId')
            
            # 方法3：从incoming_message的字典表示中获取
            if not msg_id:
                try:
                    msg_dict = incoming_message.to_dict() if hasattr(incoming_message, 'to_dict') else vars(incoming_message)
                    if isinstance(msg_dict, dict):
                        msg_id = msg_dict.get('msgId') or msg_dict.get('messageId')
                except Exception as e:
                    pass
            
            # 获取会话ID和时间戳
            session_id = getattr(incoming_message, 'conversationId', None)
            message_timestamp = getattr(incoming_message, 'createAt', None) or getattr(incoming_message, 'timestamp', time.time())
            

            
            # 如果消息为空，直接返回
            if not original_content:
                self.logger.info(f"Process {self.process_id} empty message content, skipping processing")
                return AckMessage.STATUS_OK, 'OK'
            
            # 消息去重检查 - 在日志记录之前进行
            if message_dedup.is_duplicate_or_processing(sender_id, original_content, msg_id, session_id, message_timestamp):
                self.logger.info(f"Process {self.process_id} duplicate or processing message ignored - Sender: {sender_id}, MsgID: {msg_id}")
                return AckMessage.STATUS_OK, 'OK'
            
            # 控制台打印收到的消息信息
            self.logger.info(f"Process {self.process_id} received message - Sender: {sender_id}, MsgID: {msg_id}, Session: {session_id}")                       
            
            # 防止消息循环：检查是否是机器人本身发送的消息
            if hasattr(incoming_message, 'chatbot_user_id') and incoming_message.sender_staff_id == incoming_message.chatbot_user_id:
                self.logger.info(f"Process {self.process_id} ignoring message sent by the robot itself to prevent loop")
                # 标记消息已处理
                message_dedup.mark_message_processed(sender_id, original_content, msg_id, session_id, message_timestamp)
                message_processed = True
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
                "platform": "DingTalk"
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
                self.logger.error(f"Process {self.process_id} reply content is empty")
            
            # 获取access_token用于发送钉钉回复
            access_token = get_token(self.options)
            if not access_token:
                self.logger.error(f"Process {self.process_id} failed to get access_token, unable to reply message")
                # 标记消息已处理（即使失败也要标记，避免重复处理）
                message_dedup.mark_message_processed(sender_id, original_content, msg_id, session_id, message_timestamp)
                message_processed = True
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
                        'session_id': session_id,
                        'msg_id': msg_id,
                        'message_timestamp': message_timestamp
                    }
                    
                    # 使用去重窗口作为过期时间，确保在去重期间数据有效
                    memory_store.set(preview_id, preview_data, expire_seconds=message_dedup.dedup_window)
                    self.logger.info(f"Process {self.process_id} stored preview data for preview_id: {preview_id}, waiting for confirmation")
                    
                    # 标记消息已处理（预览模式下，等待确认后再发送）
                    message_dedup.mark_message_processed(sender_id, original_content, msg_id, session_id, message_timestamp)
                    message_processed = True
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
                result = send_robot_private_message(
                    access_token, 
                    self.options, 
                    [sender_id], 
                    reply_content
                )
                
                if result:
                    if timeout_auto_sent:
                        self.logger.info(f"Process {self.process_id} auto-sent reply to user due to timeout")
                    else:
                        self.logger.info(f"Process {self.process_id} successfully sent reply to user")
                else:
                    self.logger.error(f"Process {self.process_id} failed to send reply to user")
                
                # 标记消息已处理
                message_dedup.mark_message_processed(sender_id, original_content, msg_id, session_id, message_timestamp)
                message_processed = True
                
        except Exception as e:
            self.logger.error(f"Process {self.process_id} exception occurred while processing message: {e}")
        finally:
            # 确保在异常情况下也标记消息已处理
            if not message_processed and sender_id and original_content:
                try:
                    message_dedup.mark_message_processed(sender_id, original_content, msg_id, session_id, message_timestamp)
                except Exception as e:
                    self.logger.error(f"Process {self.process_id} failed to mark message as processed: {e}")
        
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
        
        # 如果数据不存在，可能是已经处理过或者过期了
        if not message_data:
            logger.error(f"Process {current_process_id} no data found for preview_id: {preview_id}, may have expired or already processed")
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
            logger.error(f"Process {current_process_id} missing critical fields for preview_id {preview_id}: sender_id={sender_id}, sender_name={sender_name}")
            # 清理无效数据
            memory_store.delete(preview_id)
            return False
        
        # 使用默认的options配置，如果没有提供
        if not options_dict:
            options_dict = {
                'robot_code': Config.ROBOT_CODE,
                'client_id': Config.CLIENT_ID,
                'client_secret': Config.CLIENT_SECRET
            }
        
        # 创建options对象
        options = Options()
        for key, value in options_dict.items():
            setattr(options, key, value)
        
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
            
            result = send_robot_private_message(
                current_access_token,
                options,
                [sender_id],
                content_to_send
            )
        except Exception as e:
            logger.error(f"Process {current_process_id} exception when sending message: {e}")
            result = False
        
        # 无论成功与否，都清理存储中的数据，防止重复处理
        memory_store.delete(preview_id)
        
        if result:
            logger.info(f"Process {current_process_id} successfully sent reply to user after preview confirmation")
        else:
            logger.error(f"Process {current_process_id} failed to send reply to user after preview confirmation")
        
        return result
    except Exception as e:
        logger.error(f"Process {current_process_id} unexpected error in send_reply_after_preview_confirm: {e}")
        # 确保异常时也清理数据
        memory_store.delete(preview_id)
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