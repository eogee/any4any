import logging
import time
import dingtalk_stream
from config import Config
from dingtalk_stream import AckMessage
from alibabacloud_dingtalk.oauth2_1_0.client import Client as dingtalkoauth2_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.oauth2_1_0 import models as dingtalkoauth_2__1__0_models
from alibabacloud_dingtalk.robot_1_0.client import Client as dingtalkrobot_1_0Client
from alibabacloud_dingtalk.robot_1_0 import models as dingtalkrobot__1__0_models
from alibabacloud_tea_util import models as util_models

_token_cache = {"token": None, "expire": 0}

def setup_logger():
    return logging.getLogger()

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
    msg_param = '{"content":"%s"}' % msg_content

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
        logging.info(f"Private message sent successfully, target users: {user_ids}, response: {response}")
        return response
    except Exception as err:
        logging.error(f"Failed to send private message: {err}")
        return None

class EchoTextHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None, options=None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.logger = logger if logger is not None else logging.getLogger(__name__)
        self.options = options or Options()

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        try:
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            
            # 控制台打印收到的消息信息
            self.logger.info(f"Received message - Sender: {incoming_message.sender_staff_id}, "
                           f"Nickname: {incoming_message.sender_nick}, "
                           f"Content: {getattr(incoming_message.text, 'content', 'No text content')}")
            
            # 防止消息循环：检查是否是机器人本身发送的消息
            if hasattr(incoming_message, 'chatbot_user_id') and incoming_message.sender_staff_id == incoming_message.chatbot_user_id:
                self.logger.info("Ignoring message sent by the robot itself to prevent loop")
                return AckMessage.STATUS_OK, 'OK'
            
            # 获取发送人信息
            user_id = incoming_message.sender_staff_id
            user_nick = incoming_message.sender_nick
            
            # 获取access_token
            access_token = get_token(self.options)
            if not access_token:
                self.logger.error("Failed to get access_token, unable to reply message")
                return AckMessage.STATUS_OK, 'OK'  # Still return OK to avoid DingTalk retry
            
            # 构建个性化回复消息
            original_content = getattr(incoming_message.text, 'content', '')
            reply_content = f"Hello {user_nick}!\nI received your message: {original_content}\n\nThis is an auto-reply: {self.options.msg if self.options else 'Default message'}"
            
            # 发送回复消息
            result = send_robot_private_message(
                access_token, 
                self.options, 
                [user_id], 
                reply_content  # 使用自定义消息内容
            )
            
            if result:
                self.logger.info(f"Successfully sent reply to user {user_nick}({user_id})")
            else:
                self.logger.error(f"Failed to send reply to user {user_nick}({user_id})")
                
        except Exception as e:
            self.logger.error(f"Exception occurred while processing message: {e}")
        
        return AckMessage.STATUS_OK, 'OK'

def main():
    logger = setup_logger()
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
    # 创建钉钉流客户端（注意：dingtalk_stream库不支持通过ws_port参数设置WebSocket端口，使用默认连接方式）
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