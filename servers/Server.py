import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

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

    def parse_date_range(self, date_range: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析时间范围字符串为开始和结束日期

        Args:
            date_range: 时间范围，支持: all, today, week, month, year, 7days, 30days, 1year

        Returns:
            tuple: (start_date_str, end_date_str)
        """
        now = datetime.now()

        if date_range == "all":
            return None, None
        elif date_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "7days":
            start = now - timedelta(days=7)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "30days":
            start = now - timedelta(days=30)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        elif date_range == "1year":
            start = now - timedelta(days=365)
            return start.strftime('%Y-%m-%d %H:%M:%S'), None
        else:
            return None, None

    def create_paginated_response(self, data: List[Dict], total: int, page: int, limit: int) -> Dict[str, Any]:
        """
        标准的分页响应格式

        Args:
            data: 数据列表
            total: 总记录数
            page: 当前页码
            limit: 每页记录数

        Returns:
            dict: 标准分页响应格式
        """
        return {
            'data': data,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit
        }

    def handle_list_request(self, model_instance, page: int = 1, limit: int = 20,
                           user_nick: str = None, date_range: str = "all",
                           search: str = None, additional_filters: Dict = None):
        """
        通用的列表请求处理器

        Args:
            model_instance: 数据模型实例
            page: 页码
            limit: 每页记录数
            user_nick: 用户筛选
            date_range: 时间范围
            search: 搜索关键词
            additional_filters: 额外的筛选条件

        Returns:
            JSONResponse: 分页响应
        """
        try:
            # 解析时间范围
            start_date_str, end_date_str = self.parse_date_range(date_range)

            # 构建查询参数
            query_params = {
                'page': page,
                'limit': limit,
                'user_nick': user_nick,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'search': search
            }

            # 添加额外筛选条件
            if additional_filters:
                query_params.update(additional_filters)

            # 调用模型的分页方法
            if hasattr(model_instance, 'get_previews_paginated'):
                result = model_instance.get_previews_paginated(**query_params)
            elif hasattr(model_instance, 'get_timeout_messages_paginated'):
                result = model_instance.get_timeout_messages_paginated(**query_params)
            else:
                # 通用分页方法调用
                paginated_method = getattr(model_instance, 'get_paginated_data', None)
                if paginated_method:
                    result = paginated_method(**query_params)
                else:
                    raise ValueError(f"Model {model_instance.__class__.__name__} does not have a paginated method")

            return JSONResponse(result)

        except Exception as e:
            self.logger.error(f"Failed to handle list request: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    def handle_stats_request(self, model_instance, user_nick: str = None,
                           date_range: str = "all", additional_filters: Dict = None):
        """
        通用的统计请求处理器

        Args:
            model_instance: 数据模型实例
            user_nick: 用户筛选
            date_range: 时间范围
            additional_filters: 额外的筛选条件

        Returns:
            JSONResponse: 统计响应
        """
        try:
            # 解析时间范围
            start_date_str, end_date_str = self.parse_date_range(date_range)

            # 构建查询参数
            query_params = {
                'user_nick': user_nick,
                'start_date': start_date_str,
                'end_date': end_date_str
            }

            # 添加额外筛选条件
            if additional_filters:
                query_params.update(additional_filters)

            # 调用模型的统计方法
            if hasattr(model_instance, 'get_previews_count'):
                count = model_instance.get_previews_count(**query_params)
            elif hasattr(model_instance, 'get_timeout_count'):
                count = model_instance.get_timeout_count(**query_params)
            else:
                # 通用统计方法调用
                count_method = getattr(model_instance, 'get_count', None)
                if count_method:
                    count = count_method(**query_params)
                else:
                    raise ValueError(f"Model {model_instance.__class__.__name__} does not have a count method")

            return JSONResponse({"count": count})

        except Exception as e:
            self.logger.error(f"Failed to handle stats request: {e}")
            return JSONResponse({"count": 0})

    def handle_users_request(self, model_instance):
        """
        通用的用户列表请求处理器

        Args:
            model_instance: 数据模型实例

        Returns:
            JSONResponse: 用户列表响应
        """
        try:
            # 调用模型的用户列表方法
            if hasattr(model_instance, 'get_unique_users'):
                users = model_instance.get_unique_users()
            else:
                # 通用用户列表方法调用
                users_method = getattr(model_instance, 'get_users', None)
                if users_method:
                    users = users_method()
                else:
                    raise ValueError(f"Model {model_instance.__class__.__name__} does not have a users method")

            return JSONResponse({"users": users})

        except Exception as e:
            self.logger.error(f"Failed to handle users request: {e}")
            return JSONResponse({"users": []})

    def create_list_route_handler(self, model_instance, route_name: str):
        """
        通用的列表路由处理器

        Args:
            model_instance: 数据模型实例
            route_name: 路由名称（用于日志）

        Returns:
            function: 路由处理函数
        """
        async def list_handler(request, page: int = Query(1, ge=1),
                              limit: int = Query(20, ge=1, le=100),
                              user_nick: str = Query(None),
                              date_range: str = Query("all"),
                              search: str = Query(None)):
            self.log_request(f"/api/{route_name}/list")
            return self.handle_list_request(model_instance, page, limit, user_nick, date_range, search)

        return list_handler

    def create_stats_route_handler(self, model_instance, route_name: str):
        """
        通用的统计路由处理器

        Args:
            model_instance: 数据模型实例
            route_name: 路由名称（用于日志）

        Returns:
            function: 路由处理函数
        """
        async def stats_handler(request, user_nick: str = Query(None),
                               date_range: str = Query("all")):
            self.log_request(f"/api/{route_name}/stats")
            return self.handle_stats_request(model_instance, user_nick, date_range)

        return stats_handler

    def create_users_route_handler(self, model_instance, route_name: str):
        """
        通用的用户列表路由处理器

        Args:
            model_instance: 数据模型实例
            route_name: 路由名称（用于日志）

        Returns:
            function: 路由处理函数
        """
        async def users_handler(request):
            self.log_request(f"/api/{route_name}/users")
            return self.handle_users_request(model_instance)

        return users_handler