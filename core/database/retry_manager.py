import logging
import time
from typing import Callable, Any
import mysql.connector

logger = logging.getLogger(__name__)

class RetryManager:
    def __init__(self, max_attempts: int = 3, backoff_factor: float = 2.0, max_delay: int = 30):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

    def should_retry(self, error: Exception) -> bool:
        """判断是否应该重试"""
        retryable_errors = [
            mysql.connector.errors.OperationalError,
            mysql.connector.errors.InterfaceError,
            mysql.connector.errors.DatabaseError
        ]
        return any(isinstance(error, error_type) for error_type in retryable_errors)

    def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """带退避策略的重试执行"""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == self.max_attempts - 1:
                    break

                if not self.should_retry(e):
                    break

                delay = min(self.backoff_factor ** attempt, self.max_delay)
                logger.warning(f"Database operation failed, retrying in {delay}s (attempt {attempt + 1}/{self.max_attempts})")
                time.sleep(delay)

        raise last_exception

    def get_config(self) -> dict:
        """获取重试配置"""
        return {
            'max_attempts': self.max_attempts,
            'backoff_factor': self.backoff_factor,
            'max_delay': self.max_delay
        }