"""
Web搜索工具异常处理
"""


class WebSearchError(Exception):
    """Web搜索基础异常类"""

    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class NetworkError(WebSearchError):
    """网络请求异常"""

    def __init__(self, message: str):
        super().__init__(message, "NETWORK_ERROR")


class ParseError(WebSearchError):
    """HTML解析异常"""

    def __init__(self, message: str):
        super().__init__(message, "PARSE_ERROR")


class TimeoutError(WebSearchError):
    """请求超时异常"""

    def __init__(self, message: str):
        super().__init__(message, "TIMEOUT_ERROR")


class ProxyError(WebSearchError):
    """代理配置异常"""

    def __init__(self, message: str):
        super().__init__(message, "PROXY_ERROR")


class RateLimitError(WebSearchError):
    """请求频率限制异常"""

    def __init__(self, message: str):
        super().__init__(message, "RATE_LIMIT_ERROR")