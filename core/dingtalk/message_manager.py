import logging
import time
import dingtalk_stream
import httpx
import json
import uuid
import os
import fcntl
import tempfile
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

# 多进程安全的数据存储
class MultiProcessSafeDataStore:
    def __init__(self, storage_file=None):
        self.storage_file = storage_file or os.path.join(tempfile.gettempdir(), 'dingtalk_bot_data.json')
        self._lock_file = self.storage_file + '.lock'
        self._cleanup_interval = 300
        self._last_cleanup = time.time()
        self._init_storage_file()
    
    def _init_storage_file(self):
        if not os.path.exists(self.storage_file):
            with self._get_file_lock():
                if not os.path.exists(self.storage_file):
                    with open(self.storage_file, 'w', encoding='utf-8') as f:
                        json.dump({}, f)
    
    def _get_file_lock(self):
        lock_file = open(self._lock_file, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return lock_file
    
    def _read_data(self):
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_data(self, data):
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def set(self, key: str, value: Any, expire_seconds: int = 300):
        lock = self._get_file_lock()
        try:
            self._auto_cleanup()
            data = self._read_data()
            data[key] = {
                'value': value,
                'expire_time': time.time() + expire_seconds,
                'created_time': time.time()
            }
            self._write_data(data)
        finally:
            lock.close()
    
    def get(self, key: str) -> Optional[Any]:
        lock = self._get_file_lock()
        try:
            self._auto_cleanup()
            data = self._read_data()
            if key in data:
                item = data[key]
                if time.time() < item['expire_time']:
                    return item['value']
                else:
                    del data[key]
                    self._write_data(data)
            return None
        finally:
            lock.close()
    
    def delete(self, key: str) -> bool:
        lock = self._get_file_lock()
        try:
            data = self._read_data()
            if key in data:
                del data[key]
                self._write_data(data)
                return True
            return False
        finally:
            lock.close()
    
    def _auto_cleanup(self):
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        data = self._read_data()
        keys_to_remove = [key for key, item in data.items() if current_time > item['expire_time']]
        
        if keys_to_remove:
            for key in keys_to_remove:
                del data[key]
            self._write_data(data)
        
        self._last_cleanup = current_time

# 超时消息管理器
class TimeoutMessageManager:
    def __init__(self):
        self.timeout_processed_messages = set()
        self.timeout_lock = threading.Lock()
        self.timeout_store = MultiProcessSafeDataStore(
            os.path.join(tempfile.gettempdir(), 'dingtalk_timeout_data.json')
        )
    
    def mark_message_timeout_processed(self, message_id):
        if not message_id:
            return
        with self.timeout_lock:
            self.timeout_processed_messages.add(message_id)
            self.timeout_store.set(f"timeout_{message_id}", {
                'processed': True,
                'timestamp': time.time()
            }, expire_seconds=3600)
    
    def is_message_timeout_processed(self, message_id):
        if not message_id:
            return False
        if message_id in self.timeout_processed_messages:
            return True
        timeout_data = self.timeout_store.get(f"timeout_{message_id}")
        if timeout_data:
            with self.timeout_lock:
                self.timeout_processed_messages.add(message_id)
            return True
        return False

# 消息去重管理器
class MessageDeduplication:
    def __init__(self):
        config = Config()
        self.dedup_window = config.PREVIEW_TIMEOUT + 300
        self.status_store = MultiProcessSafeDataStore(
            os.path.join(tempfile.gettempdir(), 'dingtalk_message_status.json')
        )
        self.lock = threading.Lock()
    
    def check_and_mark_processing(self, msg_id, sender_id, content):
        if not msg_id:
            return False
        with self.lock:
            current_status = self.status_store.get(msg_id)
            if current_status:
                status_type = current_status.get('status')
                if status_type in ['completed', 'timeout_processed']:
                    return True
                elif status_type == 'processing':
                    elapsed = time.time() - current_status.get('timestamp', 0)
                    if elapsed > self.dedup_window:
                        self.status_store.set(msg_id, {
                            'status': 'timeout_failed',
                            'timestamp': time.time()
                        }, self.dedup_window)
                        return False
                    return True
            self.status_store.set(msg_id, {
                'status': 'processing',
                'timestamp': time.time(),
                'sender_id': sender_id,
                'content': content[:100]
            }, self.dedup_window)
            return False
    
    def mark_final_status(self, msg_id, status='completed'):
        if not msg_id:
            return
        with self.lock:
            current = self.status_store.get(msg_id) or {}
            current.update({
                'status': status,
                'final_timestamp': time.time()
            })
            self.status_store.set(msg_id, current, self.dedup_window)

# 全局实例
memory_store = MultiProcessSafeDataStore()
timeout_manager = TimeoutMessageManager()
message_dedup = MessageDeduplication()

# 进程内令牌缓存
_token_cache = {"token": None, "expire": 0}

class Options:
    def __init__(self):
        self.client_id = Config.CLIENT_ID
        self.client_secret = Config.CLIENT_SECRET
        self.robot_code = Config.ROBOT_CODE
        self.msg = 'python-getting-start say：hello'

def get_token(options):
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
            _token_cache["expire"] = now + expire_in - 200
        return token
    except Exception as err:
        logging.error(f"Failed to get token: {err}")
        return None

def send_robot_private_message(access_token: str, options, user_ids: list, custom_msg=None):
    robot_code = options.robot_code
    msg_key = 'sampleText'
    msg_content = custom_msg if custom_msg else options.msg
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
        return response
    except Exception as err:
        logging.error(f"Failed to send private message: {err}")
        return None

class EchoTextHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None, options=None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.options = options
        self.is_preview_callback = False
        self.process_id = os.getpid()

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        msg_id = None
        sender_id = None
        original_content = None
        
        try:
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            sender_id = incoming_message.sender_staff_id
            user_nick = incoming_message.sender_nick
            original_content = getattr(incoming_message.text, 'content', '')
            
            # 获取消息ID
            msg_id = None
            if isinstance(callback.data, dict):
                msg_id = (callback.data.get('msgId') or 
                         callback.data.get('messageId') or 
                         callback.data.get('msgid'))
            if not msg_id:
                msg_id = getattr(incoming_message, 'msgId', None) or getattr(incoming_message, 'messageId', None)
            
            if not original_content:
                return AckMessage.STATUS_OK, 'OK'
            
            # 消息去重检查
            if msg_id and message_dedup.check_and_mark_processing(msg_id, sender_id, original_content):
                return AckMessage.STATUS_OK, 'OK'
            
            self.logger.info(f"Received message from {sender_id}, MsgID: {msg_id}")
            
            # 防止消息循环
            if hasattr(incoming_message, 'chatbot_user_id') and incoming_message.sender_staff_id == incoming_message.chatbot_user_id:
                if msg_id:
                    message_dedup.mark_final_status(msg_id, 'completed')
                return AckMessage.STATUS_OK, 'OK'
            
            # 构建API请求
            request_body = {
                "messages": [{"role": "user", "content": original_content}],
                "model": "default",
                "stream": False,
                "temperature": Config.TEMPERATURE,
                "max_tokens": Config.MAX_LENGTH,
                "top_p": Config.TOP_P,
                "repetition_penalty": Config.REPETITION_PENALTY,
                "sender_id": sender_id,
                "sender_nickname": user_nick,
                "platform": "DingTalk",
                "msg_id": msg_id
            }
            
            # 调用API
            api_response = None
            timeout_auto_sent = False
            reply_content = ""
            
            try:
                async with httpx.AsyncClient() as client:
                    api_url = f"http://localhost:{getattr(Config, 'PORT', 8888)}/v1/chat/completions"
                    response = await client.post(api_url, json=request_body, timeout=message_dedup.dedup_window)
                    
                    if response.status_code == 200:
                        api_response = response.json()
                        if api_response and "choices" in api_response and len(api_response["choices"]) > 0:
                            if "message" in api_response["choices"][0] and "content" in api_response["choices"][0]["message"]:
                                reply_content = api_response["choices"][0]["message"]["content"]
                            else:
                                reply_content = "Sorry, I couldn't generate a response."
                        else:
                            reply_content = "Sorry, I couldn't generate a response."
                        timeout_auto_sent = api_response.get("timeout_auto_sent", False)
                    else:
                        reply_content = f"Error: API returned status code {response.status_code}"
            except httpx.TimeoutException:
                reply_content = "Error: Request timeout"
            except Exception as api_err:
                reply_content = f"Error: {str(api_err)}"
            
            if not reply_content:
                reply_content = "Error: No response content received"
            
            # 检查是否是延迟处理中的消息
            if reply_content == "DELAY_PROCESSING" or api_response and api_response.get("delay_processing"):
                if msg_id:
                    message_dedup.mark_final_status(msg_id, 'delay_processing')
                return AckMessage.STATUS_OK, 'OK'
            
            # 获取token并发送回复
            access_token = get_token(self.options)
            if not access_token:
                if msg_id:
                    message_dedup.mark_final_status(msg_id, 'failed')
                return AckMessage.STATUS_OK, 'OK'
            
            if hasattr(Config, 'NO_THINK') and Config.NO_THINK:
                reply_content = filter_think_content(reply_content)
            
            # 预览模式处理
            if Config.PREVIEW_MODE and not self.is_preview_callback and not timeout_auto_sent:
                request_id = str(uuid.uuid4())
                preview_id = None
                
                if isinstance(api_response, dict):
                    if 'preview_id' in api_response:
                        preview_id = api_response['preview_id']
                    elif 'choices' in api_response:
                        for choice in api_response['choices']:
                            if isinstance(choice, dict) and 'preview_id' in choice:
                                preview_id = choice['preview_id']
                                break
                
                if not preview_id and Config.PREVIEW_MODE:
                    preview_id = f"preview_{int(time.time())}_{sender_id}_{self.process_id}"
                
                if preview_id:
                    preview_data = {
                        'sender': sender_id,
                        'sender_name': user_nick,
                        'original_content': original_content,
                        'request_id': request_id,
                        'content': reply_content,
                        'options': self.options.__dict__,
                        'timestamp': time.time(),
                        'process_id': self.process_id,
                        'msg_id': msg_id
                    }
                    
                    memory_store.set(preview_id, preview_data, expire_seconds=message_dedup.dedup_window)
                    
                    if msg_id:
                        message_dedup.mark_final_status(msg_id, 'preview_pending')
                else:
                    result = send_robot_private_message(access_token, self.options, [sender_id], reply_content)
                    if msg_id:
                        status = 'completed' if result else 'failed'
                        message_dedup.mark_final_status(msg_id, status)
            else:
                # 直接发送回复
                if timeout_auto_sent:
                    timeout_manager.mark_message_timeout_processed(msg_id)
                
                result = send_robot_private_message(access_token, self.options, [sender_id], reply_content)
                
                if msg_id:
                    if timeout_auto_sent:
                        message_dedup.mark_final_status(msg_id, 'timeout_processed')
                    else:
                        status = 'completed' if result else 'failed'
                        message_dedup.mark_final_status(msg_id, status)
        
        except Exception as e:
            self.logger.error(f"Exception processing message: {e}")
            if msg_id:
                message_dedup.mark_final_status(msg_id, 'failed')
        
        return AckMessage.STATUS_OK, 'OK'

async def send_reply_after_preview_confirm(preview_id: str, confirmed_content: str, request_data=None) -> bool:
    logger = logging.getLogger('core.dingtalk.message_manager')
    current_process_id = os.getpid()
    
    try:
        message_data = memory_store.get(preview_id)
        
        if not message_data:
            if request_data and isinstance(request_data, dict):
                message_data = {
                    'content': confirmed_content,
                    'sender': None,
                    'sender_name': 'User'
                }
                
                sender_id_sources = [
                    request_data.get('sender_id'),
                    request_data.get('user_id'),
                    request_data.get('sender'),
                    request_data.get('from_user_id'),
                    request_data.get('user', {}).get('id')
                ]
                
                for sender_id in sender_id_sources:
                    if sender_id:
                        message_data['sender'] = sender_id
                        break
                
                if not message_data['sender'] and '_' in preview_id:
                    parts = preview_id.split('_')
                    if len(parts) >= 3:
                        potential_sender_id = parts[2]
                        if potential_sender_id and not potential_sender_id.isdigit():
                            message_data['sender'] = potential_sender_id
            else:
                return False
        
        sender_id = message_data.get('sender')
        if not sender_id:
            return False
        
        content_to_send = confirmed_content or message_data.get('content', '')
        if hasattr(Config, 'NO_THINK') and Config.NO_THINK:
            content_to_send = filter_think_content(content_to_send)
        
        options = Options()
        current_access_token = get_token(options)
        if not current_access_token:
            return False
        
        msg_id = message_data.get('msg_id')
        if msg_id and message_dedup.status_store.get(msg_id):
            current_status = message_dedup.status_store.get(msg_id)
            if current_status.get('status') in ['completed', 'timeout_processed']:
                memory_store.delete(preview_id)
                return False
        
        result = send_robot_private_message(current_access_token, options, [sender_id], content_to_send)
        memory_store.delete(preview_id)
        
        if msg_id:
            status = 'completed' if result else 'preview_failed'
            message_dedup.mark_final_status(msg_id, status)
        
        return bool(result)
    except Exception as e:
        logger.error(f"Error in send_reply_after_preview_confirm: {e}")
        memory_store.delete(preview_id)
        return False

def register_preview_confirm_callback():
    async def wrapped_confirm_preview(preview_id, content, request_data):
        try:
            success = await send_reply_after_preview_confirm(preview_id, content, request_data)
            if not success:
                logging.error(f"Failed to send reply for preview {preview_id}")
        except Exception as e:
            logging.error(f"Error in preview confirm callback: {e}")
            memory_store.delete(preview_id)
    
    preview_service.register_confirm_callback(wrapped_confirm_preview)
    return wrapped_confirm_preview

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    current_process_id = os.getpid()
    
    if Config.PREVIEW_MODE:
        register_preview_confirm_callback()
    
    options = Options()
    
    if not all([options.client_id, options.client_secret, options.robot_code]):
        logger.error("DingTalk configuration incomplete")
        return
    
    try:
        dingtalk_port = int(Config.DINGTALK_PORT)
    except ValueError:
        logger.error(f"Invalid port: {Config.DINGTALK_PORT}")
        return
    
    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    
    client.register_callback_handler(
        dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
        EchoTextHandler(logger, options)
    )
    
    client.start_forever()