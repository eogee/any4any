import logging
import time
import dingtalk_stream
import httpx
import json
import uuid
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

# 使用内存字典来存储必要的信息
class MemoryDataStore:
    def __init__(self):
        self._data = {}
        
    def set(self, key, value):
        """存储数据到内存"""
        self._data[key] = value
        
    def get(self, key):
        """从内存获取数据"""
        return self._data.get(key)
        
    def delete(self, key):
        """删除内存中的数据"""
        if key in self._data:
            del self._data[key]
            logging.info(f"Deleted data for key: {key}")
            return True
        return False

# 创建全局内存数据存储实例
memory_store = MemoryDataStore()

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
            logging.info(f"Successfully obtained access_token, valid until: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_token_cache['expire']))}")
        return token
    except Exception as err:
        logging.error(f"Failed to get token: {err}")
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
        return response
    except Exception as err:
        logging.error(f"Failed to send private message: {err}")
        return None

class EchoTextHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None, options=None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.options = options
        # 标记是否为预览模式的回调请求
        self.is_preview_callback = False

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        try:
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            
            # 控制台打印收到的消息信息
            self.logger.info(f"Received message - Sender: {incoming_message.sender_staff_id}, " )                       
            
            # 防止消息循环：检查是否是机器人本身发送的消息
            if hasattr(incoming_message, 'chatbot_user_id') and incoming_message.sender_staff_id == incoming_message.chatbot_user_id:
                self.logger.info("Ignoring message sent by the robot itself to prevent loop")
                return AckMessage.STATUS_OK, 'OK'
            
            # 获取发送人信息
            user_id = incoming_message.sender_staff_id
            user_nick = incoming_message.sender_nick
            
            # 获取消息内容
            original_content = getattr(incoming_message.text, 'content', '')
            
            # 如果消息为空，直接返回
            if not original_content:
                self.logger.info("Empty message content, skipping processing")
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
                "sender_id": user_id,  # 发送者ID作为附加信息
                "sender_nickname": user_nick,  # 发送者昵称作为附加信息
                "platform": "DingTalk"  # 平台标识
            }
            
            # 发送请求到app.py中的/v1/chat/completions接口
            self.logger.info(f"Forwarding message to OpenAI API: {original_content}")
            
            try:
                # 使用httpx发送异步HTTP请求
                async with httpx.AsyncClient() as client:
                    # 使用配置文件中的端口设置
                    api_url = f"http://localhost:{getattr(Config, 'PORT', 8888)}/v1/chat/completions"
                    response = await client.post(
                        api_url,
                        json=request_body,
                        timeout=60  # 设置超时时间为60秒
                    )
                    
                    # 检查响应状态
                    if response.status_code == 200:
                        # 解析响应内容
                        api_response = response.json()
                        
                        # 从响应中提取assistant的回复
                        if api_response and "choices" in api_response and len(api_response["choices"]) > 0:
                            reply_content = api_response["choices"][0]["message"]["content"]
                            self.logger.info(f"Received response from OpenAI.")
                        else:
                            reply_content = "Sorry, I couldn't generate a response."
                            self.logger.error(f"Invalid response format from OpenAI API: {api_response}")
                    else:
                        reply_content = f"Error: API returned status code {response.status_code}"
                        self.logger.error(f"API request failed with status {response.status_code}: {response.text}")
            except Exception as api_err:
                reply_content = f"Error: {str(api_err)}"
                self.logger.error(f"Exception occurred while calling OpenAI API: {api_err}")
            
            # 获取access_token用于发送钉钉回复
            access_token = get_token(self.options)
            if not access_token:
                self.logger.error("Failed to get access_token, unable to reply message")
                return AckMessage.STATUS_OK, 'OK'
            
            # 根据配置中的NO_THINK设置，过滤掉</think>和</think>之间的内容
            if hasattr(Config, 'NO_THINK') and Config.NO_THINK:
                reply_content = filter_think_content(reply_content)
            
            # 如果是预览模式，不直接发送回复
                if Config.PREVIEW_MODE and not self.is_preview_callback:
                    # 为这个请求生成一个唯一ID
                    request_id = str(uuid.uuid4())
                    
                    # 尝试从API响应中提取preview_id，考虑不同的响应格式
                    preview_id = None
                    
                    # 检查直接在响应根级别是否有preview_id
                    if isinstance(api_response, dict):
                        if 'preview_id' in api_response:
                            preview_id = api_response['preview_id']
                        # 检查在choices数组中是否有preview_id
                        elif 'choices' in api_response:
                            for choice in api_response['choices']:
                                if isinstance(choice, dict) and 'preview_id' in choice:
                                    preview_id = choice['preview_id']
                                    break
                        # 检查在response对象中是否有preview_id
                        elif 'response' in api_response:
                            response_obj = api_response['response']
                            if isinstance(response_obj, dict) and 'preview_id' in response_obj:
                                preview_id = response_obj['preview_id']
                    
                    # 如仍然没找到preview_id，生成一个并使用
                    if not preview_id and Config.PREVIEW_MODE:
                        # 生成一个基于时间戳的预览ID
                        preview_id = f"preview_{int(time.time())}"
                        self.logger.warning(f"No preview_id found in response, generating one: {preview_id}")
                    
                    if preview_id:                        
                        # 存储必要的信息到内存中
                        memory_store.set(preview_id, {
                            'sender': user_id,             # 发送者ID
                            'sender_name': user_nick,      # 发送者昵称
                            'original_content': original_content,  # 原始消息内容
                            'request_id': request_id,      # 请求ID
                            'content': reply_content,      # 生成的回复内容
                            'options': self.options.__dict__,  # 将options对象转换为字典
                            'timestamp': time.time()       # 时间戳
                        })
                        
                    else:
                        self.logger.error("Failed to get preview_id")
                        self.logger.warning(f"Preview mode enabled but no preview_id found in response: {json.dumps(api_response, ensure_ascii=False)[:200]}...")
            else:
                # 非预览模式或预览确认后的回调，直接发送回复消息
                result = send_robot_private_message(
                    access_token, 
                    self.options, 
                    [user_id], 
                    reply_content  # 使用API返回的结果作为回复内容
                )
                
                if result:
                    self.logger.info(f"Successfully sent reply to user {user_nick}({user_id})")
                else:
                    self.logger.error(f"Failed to send reply to user {user_nick}({user_id})")
                
        except Exception as e:
            self.logger.error(f"Exception occurred while processing message: {e}")
        
        return AckMessage.STATUS_OK, 'OK'

async def send_reply_after_preview_confirm(preview_id: str, confirmed_content: str, request_data=None) -> bool:
    """
    预览确认后发送回复给钉钉用户
    
    Args:
        preview_id: 预览ID
        confirmed_content: 确认后的内容
        request_data: 请求数据，包含所需的字段信息
    
    Returns:
        bool: 是否成功发送消息
    """
    # 创建专用logger
    logger = logging.getLogger('core.dingtalk.message_manager')
    
    try:
        # 从内存存储中获取消息数据
        message_data = memory_store.get(preview_id)
        
        # 如果内存中没有数据，尝试从request_data中获取所需字段
        sender_id = None
        sender_name = None
        original_content = None
        request_id = None
        options_dict = None
        
        # 首先尝试从内存存储获取
        if message_data:
            logger.info(f"Found message data in memory store for preview_id: {preview_id}")
            sender_id = message_data.get('sender')
            sender_name = message_data.get('sender_name')
            original_content = message_data.get('original_content')
            request_id = message_data.get('request_id')
            options_dict = message_data.get('options', {})
        
        # 如果内存中没有，尝试从request_data中获取
        if not all([sender_id, sender_name, original_content, request_id]) and request_data:
            
            # 尝试不同可能的字段名
            sender_id = sender_id or request_data.get('sender_id') or request_data.get('sender') or request_data.get('user_id')
            sender_name = sender_name or request_data.get('sender_name') or request_data.get('username') or request_data.get('sender_nickname')
            original_content = original_content or request_data.get('original_content') or request_data.get('content')
            request_id = request_id or request_data.get('request_id') or request_data.get('id')
        
        # 检查是否获取到关键字段
        # 发送ID和发送者名称是必须的，但request_id可以生成一个
        if not all([sender_id, sender_name]):
            logger.error(f"Missing critical fields for preview_id {preview_id}: sender_id={sender_id}, sender_name={sender_name}")
            return False
        
        # 如果没有request_id，生成一个新的
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # 使用默认的options配置，如果没有提供
        if not options_dict:
            options_dict = {
                'robot_code': Config.ROBOT_CODE,
                'client_id': Config.CLIENT_ID,
                'client_secret': Config.CLIENT_SECRET
            }
        
        # 创建options对象
        options = Options()
        # 更新options对象的属性
        for key, value in options_dict.items():
            setattr(options, key, value)
        
        # 确定要发送的内容
        content_to_send = confirmed_content
        if message_data and not confirmed_content:
            content_to_send = message_data.get('content', '')
        
        # 根据配置中的NO_THINK设置，过滤掉</think>和</think>之间的内容
        if hasattr(Config, 'NO_THINK') and Config.NO_THINK:
            content_to_send = filter_think_content(content_to_send)
            logger.info(f"Filtered think content, new content length: {len(content_to_send)}")
        
        logger.info(f"Confirmed content to send: {content_to_send[:100]}...")
        
        result = False
        try:
            # 获取最新的access_token
            current_access_token = get_token(options)
            if not current_access_token:
                logger.error("Failed to get access_token, cannot send message")
                return False
            
            result = send_robot_private_message(
                current_access_token,
                options,
                [sender_id],
                content_to_send
            )
        except Exception as e:
            logger.error(f"Exception when sending message: {e}")
            result = False
        
        # 清理内存存储中的数据
        memory_store.delete(preview_id)
        
        if result:
            logger.info(f"Successfully sent reply to user {sender_name}({sender_id}) after preview confirmation")
        else:
            logger.error(f"Failed to send reply to user {sender_name}({sender_id}) after preview confirmation")
        
        return result
    except Exception as e:
        logger.error(f"Unexpected error in send_reply_after_preview_confirm: {e}")
        # 出错时也尝试清理数据
        memory_store.delete(preview_id)
        return False

# 注册预览确认回调
def register_preview_confirm_callback():
    """
    注册预览确认回调函数到preview_service，用于在用户确认预览后发送钉钉消息
    """
    
    async def wrapped_confirm_preview(preview_id, content, request_data):
        """包装的预览确认回调函数"""
        try:
            # 使用send_reply_after_preview_confirm发送消息，并传递request_data用于获取所需字段
            success = await send_reply_after_preview_confirm(preview_id, content, request_data)
            
        except Exception as e:
            logging.error(f"Error in preview confirm callback: {e}")
            # 出错时尝试清理内存数据
            memory_store.delete(preview_id)
            logging.info(f"Cleaned memory data for preview_id: {preview_id} after error")
    
    # 注册回调到preview_service
    preview_service.register_confirm_callback(wrapped_confirm_preview)
    logging.info("Preview confirm callback registered with preview_service")
    return wrapped_confirm_preview

def main():
    # 使用全局日志配置
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 注册预览确认回调
    if Config.PREVIEW_MODE:
        register_preview_confirm_callback()
        logging.info("Preview confirm callback registered with preview_service")
    options = define_options()
    
    # 检查配置是否完整
    if not all([options.client_id, options.client_secret, options.robot_code]):
        logger.error("DingTalk robot configuration is incomplete. Please check CLIENT_ID, CLIENT_SECRET and ROBOT_CODE in .env file")
        return
    
    # 获取并验证端口配置
    try:
        dingtalk_port = int(Config.DINGTALK_PORT)
    except ValueError:
        logger.error(f"Invalid DingTalk port configuration: {Config.DINGTALK_PORT}")
        return
    
    # 打印启动信息
    logger.info(f"Starting DingTalk robot, Robot Code: {options.robot_code}, Listening on port: {dingtalk_port}")
    
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
    
    logger.info("DingTalk robot started successfully, begin listening for messages...")
    client.start_forever()