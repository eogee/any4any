import logging
from typing import Dict, Any
from config import Config

logger = logging.getLogger(__name__)

class DatabaseMonitoring:
    """数据库连接池监控服务"""

    def __init__(self):
        self.connection_pool = None
        self.enabled = Config.DB_POOL_MONITORING_ENABLED

        if self.enabled:
            try:
                from core.database.connection_pool import get_connection_pool
                self.connection_pool = get_connection_pool()
                logger.info("Database monitoring initialized")
            except ImportError:
                logger.warning("Connection pool not available for monitoring")
                self.enabled = False

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self.enabled or not self.connection_pool:
            return {
                'monitoring_enabled': False,
                'message': 'Database monitoring is disabled'
            }

        try:
            metrics = self.connection_pool.get_metrics()
            return {
                'monitoring_enabled': True,
                'pool_metrics': metrics,
                'timestamp': self._get_timestamp()
            }
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {
                'monitoring_enabled': True,
                'error': str(e),
                'timestamp': self._get_timestamp()
            }

    def health_check(self) -> Dict[str, Any]:
        """执行数据库健康检查"""
        if not self.enabled or not self.connection_pool:
            return {
                'healthy': False,
                'reason': 'Database monitoring is disabled'
            }

        try:
            # 测试连接
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            self.connection_pool.return_connection(connection)

            metrics = self.connection_pool.get_metrics()
            success_rate = metrics.get('success_rate', 0)

            # 健康状态判断
            is_healthy = success_rate >= 0.95  # 成功率95%以上

            return {
                'healthy': is_healthy,
                'success_rate': success_rate,
                'active_connections': metrics.get('active_connections', 0),
                'circuit_breaker_state': metrics.get('circuit_breaker_state', {}).get('state'),
                'timestamp': self._get_timestamp()
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': self._get_timestamp()
            }

    def _get_timestamp(self) -> int:
        """获取当前时间戳"""
        import time
        return int(time.time())

# 全局监控实例
_database_monitoring = None

def get_database_monitoring() -> DatabaseMonitoring:
    """获取数据库监控实例"""
    global _database_monitoring
    if _database_monitoring is None:
        _database_monitoring = DatabaseMonitoring()
    return _database_monitoring