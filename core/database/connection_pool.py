import logging
import threading
from typing import Dict, Any, Optional
from mysql.connector import pooling
from mysql.connector.connection import MySQLConnection
from config import Config
from .circuit_breaker import CircuitBreaker
from .retry_manager import RetryManager

logger = logging.getLogger(__name__)

class ConnectionPoolManager:
    def __init__(self):
        self.pool = None
        self.circuit_breaker = None
        self.retry_manager = None
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'active_connections': 0
        }
        self._lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        """初始化连接池"""
        try:
            if not Config.DB_POOL_ENABLED:
                logger.info("Database connection pool is disabled")
                return

            pool_config = {
                'pool_name': 'any4any_pool',
                'pool_size': max(Config.DB_POOL_SIZE, 15),  # MySQL连接池大小
                'pool_reset_session': True,
                'autocommit': True,
                'host': Config.MYSQL_HOST,
                'port': Config.MYSQL_PORT,
                'user': Config.MYSQL_USER,
                'password': Config.MYSQL_PASSWORD,
                'database': Config.MYSQL_DATABASE,
                'charset': 'utf8mb4',
                'connect_timeout': Config.DB_POOL_TIMEOUT,
            }

            self.pool = pooling.MySQLConnectionPool(**pool_config)
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=Config.DB_CIRCUIT_BREAKER_THRESHOLD,
                recovery_timeout=Config.DB_CIRCUIT_BREAKER_TIMEOUT
            )
            self.retry_manager = RetryManager(
                max_attempts=Config.DB_RETRY_MAX_ATTEMPTS,
                backoff_factor=Config.DB_RETRY_BACKOFF_FACTOR,
                max_delay=Config.DB_RETRY_MAX_DELAY
            )

            pool_size = pool_config['pool_size']
            logger.info(f"Database connection pool initialized: size={pool_size}")

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    def get_connection(self) -> MySQLConnection:
        """获取数据库连接"""
        with self._lock:
            self.metrics['total_requests'] += 1

        if not self.pool:
            raise Exception("Connection pool not initialized")

        return self.circuit_breaker.call(self._get_connection_internal)

    def _get_connection_internal(self) -> MySQLConnection:
        """内部连接获取方法"""
        try:
            connection = self.pool.get_connection()

            with self._lock:
                self.metrics['active_connections'] += 1

            if Config.DB_POOL_PRE_PING:
                connection.ping(reconnect=True, attempts=3)

            return connection

        except Exception as e:
            with self._lock:
                self.metrics['failed_requests'] += 1
            logger.error(f"Failed to get database connection: {e}")
            raise

    def return_connection(self, connection: MySQLConnection):
        """归还连接到连接池"""
        try:
            if connection:
                # 先减少活跃连接计数
                with self._lock:
                    self.metrics['active_connections'] = max(0, self.metrics['active_connections'] - 1)

                # MySQL Connector的连接池通过close()自动归还连接
                if hasattr(connection, 'close') and connection.is_connected():
                    connection.close()
                    logger.debug("Connection returned to pool")
                else:
                    logger.debug("Connection already closed or invalid")

        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            # 确保计数器正确
            with self._lock:
                self.metrics['active_connections'] = max(0, self.metrics['active_connections'] - 1)

    def get_circuit_breaker(self) -> CircuitBreaker:
        """获取熔断器实例"""
        return self.circuit_breaker

    def get_retry_manager(self) -> RetryManager:
        """获取重试管理器实例"""
        return self.retry_manager

    def record_operation_success(self, operation: str, duration: float):
        """记录操作成功指标"""
        with self._lock:
            self.metrics['successful_requests'] += 1

    def record_operation_error(self, operation: str, error: str):
        """记录操作错误指标"""
        logger.error(f"Database operation failed: {operation}, error: {error}")

    def get_metrics(self) -> Dict[str, Any]:
        """获取连接池指标"""
        with self._lock:
            total_requests = self.metrics['total_requests']
            successful_requests = self.metrics['successful_requests']

            return {
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'failed_requests': self.metrics['failed_requests'],
                'active_connections': self.metrics['active_connections'],
                'success_rate': successful_requests / max(1, total_requests),
                'circuit_breaker_state': self.circuit_breaker.get_state() if self.circuit_breaker else None,
                'retry_config': self.retry_manager.get_config() if self.retry_manager else None
            }

    def close(self):
        """关闭连接池"""
        if self.pool:
            try:
                self.pool.close()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.error(f"Error closing connection pool: {e}")

# 全局连接池管理器实例
_connection_pool_manager = None
_pool_lock = threading.Lock()

def get_connection_pool() -> ConnectionPoolManager:
    """获取连接池管理器单例"""
    global _connection_pool_manager
    if _connection_pool_manager is None:
        with _pool_lock:
            if _connection_pool_manager is None:
                _connection_pool_manager = ConnectionPoolManager()
    return _connection_pool_manager