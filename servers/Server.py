import logging
from abc import ABC, abstractmethod
from fastapi import FastAPI

class Server(ABC):
    """服务基类，所有其他服务器类都应继承此类"""
    
    def __init__(self, log_init: bool = False):
        """初始化服务器基类"""
        self.logger = logging.getLogger(self.__class__.__name__)
        if log_init:
            self.logger.info(f"{self.__class__.__name__} initialized")
        
    @abstractmethod
    def register_routes(self, app: FastAPI):
        """注册路由的抽象方法，子类必须实现此方法"""
        pass
        
    def log_request(self, route_path: str):
        """记录请求日志"""
        self.logger.info(f"Request: {route_path}")
        
    def log_error(self, route_path: str, error: Exception):
        """记录错误日志"""
        self.logger.error(f"Request {route_path} failed: {str(error)}")