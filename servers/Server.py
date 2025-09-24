import logging
from abc import ABC, abstractmethod
from fastapi import FastAPI

class Server(ABC):
    """
    服务基类，所有其他服务器类都应继承此类
    """
    def __init__(self, log_init: bool = False):
        """
        初始化服务器基类
        
        Args:
            log_init: 是否记录初始化日志，默认为False
        """
        # 设置日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        # 根据参数决定是否记录初始化日志
        if log_init:
            self.logger.info(f"Initializing {self.__class__.__name__}")
        
    @abstractmethod
    def register_routes(self, app: FastAPI):
        """
        注册路由的抽象方法，子类必须实现此方法
        
        Args:
            app: FastAPI应用实例
        """
        pass
        
    def log_request(self, route_path: str):
        """
        记录请求日志
        
        Args:
            route_path: 路由路径
        """
        self.logger.info(f"Handling request: {route_path}")
        
    def log_error(self, route_path: str, error: Exception):
        """
        记录错误日志
        
        Args:
            route_path: 路由路径
            error: 异常对象
        """
        self.logger.error(f"Handling request {route_path} failed: {str(error)}")
        
    def get_server_info(self):
        """
        获取服务器信息
        
        Returns:
            dict: 服务器信息字典
        """
        return {
            "server_name": self.__class__.__name__,
            "server_type": "base_server"
        }