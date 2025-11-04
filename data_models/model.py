import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from mysql.connector import Error
from core.database.database import get_db_connection
from config import Config

class Model(ABC):
    """与数据库交互的基类，供其他类继承使用"""

    def __init__(self, use_connection_pool: Optional[bool] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connection = None
        self.cursor = None

        # 连接池配置
        if use_connection_pool is None:
            self.use_connection_pool = Config.DB_POOL_ENABLED
        else:
            self.use_connection_pool = use_connection_pool

        if self.use_connection_pool:
            try:
                from core.database.connection_pool import get_connection_pool
                self.connection_pool = get_connection_pool()
                self.retry_manager = self.connection_pool.get_retry_manager()
            except ImportError:
                self.logger.warning("Connection pool not available, falling back to direct connection")
                self.use_connection_pool = False
        
    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self._close_connection()
        
    @abstractmethod
    def get_table_name(self) -> str:
        """获取表名的抽象方法，子类必须实现此方法"""
        pass
        
    def _get_connection(self):
        """获取数据库连接"""
        if self.use_connection_pool:
            return self.connection_pool.get_connection()
        else:
            if not self.connection or not self.connection.is_connected():
                self.connection = get_db_connection()
            return self.connection
        
    def _get_cursor(self, dictionary: bool = True):
        """获取数据库游标"""
        try:
            connection = self._get_connection()
            # 连接池模式下不保存游标，每次都创建新的
            if self.use_connection_pool:
                return connection.cursor(dictionary=dictionary)
            else:
                self.cursor = connection.cursor(dictionary=dictionary)
                return self.cursor
        except Exception as e:
            self.logger.error(f"Failed to get cursor: {e}")
            if not self.use_connection_pool:
                self.connection = None
            connection = self._get_connection()
            return connection.cursor(dictionary=dictionary)
        
    def _close_connection(self):
        """关闭数据库连接和游标"""
        if self.cursor:
            try:
                self.cursor.close()
            except Exception as e:
                self.logger.error(f"Failed to close cursor: {e}")
            self.cursor = None

        if self.use_connection_pool and self.connection:
            try:
                self.connection_pool.return_connection(self.connection)
            except Exception as e:
                self.logger.error(f"Failed to return connection to pool: {e}")
            finally:
                self.connection = None
        elif self.connection and self.connection.is_connected():
            try:
                self.connection.close()
            except Exception as e:
                self.logger.error(f"Failed to close connection: {e}")
            finally:
                self.connection = None
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行SQL查询（INSERT、UPDATE、DELETE）"""
        def _execute():
            connection = self._get_connection()
            cursor = None

            try:
                cursor = connection.cursor(dictionary=True)

                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                if not self.use_connection_pool:
                    connection.commit()

                query_type = query.strip().upper().split()[0]
                self.logger.info(f"Executed {query_type} query, affected rows: {cursor.rowcount}")

                result = cursor.rowcount

                # 关闭游标
                if cursor:
                    cursor.close()

                # 连接池模式下归还连接
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)

                return result

            except Exception as e:
                # 出错时确保关闭游标和归还连接
                if cursor:
                    cursor.close()
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)
                raise

        try:
            if self.use_connection_pool and hasattr(self, 'retry_manager'):
                result = self.retry_manager.retry_with_backoff(_execute)
            else:
                result = _execute()

            # 记录成功指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_success('execute', 0)

            return result

        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            if not self.use_connection_pool and self.connection:
                self.connection.rollback()

            # 记录错误指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_error('execute', str(e))

            raise
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """执行SQL查询并返回单行结果"""
        def _fetch():
            connection = self._get_connection()
            cursor = None

            try:
                cursor = connection.cursor(dictionary=True)

                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                result = cursor.fetchone()

                # 关闭游标
                if cursor:
                    cursor.close()

                # 连接池模式下归还连接
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)

                return result

            except Exception as e:
                # 出错时确保关闭游标和归还连接
                if cursor:
                    cursor.close()
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)
                raise

        try:
            if self.use_connection_pool and hasattr(self, 'retry_manager'):
                result = self.retry_manager.retry_with_backoff(_fetch)
            else:
                result = _fetch()

            # 记录成功指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_success('fetch_one', 0)

            return result

        except Exception as e:
            self.logger.error(f"Fetch one failed: {e}")

            # 记录错误指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_error('fetch_one', str(e))

            raise
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行SQL查询并返回所有结果"""
        def _fetch():
            connection = self._get_connection()
            cursor = None

            try:
                cursor = connection.cursor(dictionary=True)

                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                result = cursor.fetchall()

                # 关闭游标
                if cursor:
                    cursor.close()

                # 连接池模式下归还连接
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)

                return result

            except Exception as e:
                # 出错时确保关闭游标和归还连接
                if cursor:
                    cursor.close()
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)
                raise

        try:
            if self.use_connection_pool and hasattr(self, 'retry_manager'):
                result = self.retry_manager.retry_with_backoff(_fetch)
            else:
                result = _fetch()

            # 记录成功指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_success('fetch_all', 0)

            self.logger.info(f"Fetched {len(result)} records from {self.get_table_name()}")
            return result

        except Exception as e:
            self.logger.error(f"Fetch all failed: {e}")

            # 记录错误指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_error('fetch_all', str(e))

            raise
    
    def find_by_id(self, id_value: Any, id_column: str = 'id') -> Optional[Dict[str, Any]]:
        """根据ID查找记录"""
        query = f"SELECT * FROM {self.get_table_name()} WHERE {id_column} = %s"
        return self.fetch_one(query, (id_value,))
    
    def find_all(self) -> List[Dict[str, Any]]:
        """查询表中的所有记录"""
        query = f"SELECT * FROM {self.get_table_name()}"
        return self.fetch_all(query)
    
    def insert(self, data: Dict[str, Any]) -> int:
        """插入一条记录"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {self.get_table_name()} ({columns}) VALUES ({placeholders})"

        def _insert():
            connection = self._get_connection()
            cursor = None

            try:
                cursor = connection.cursor(dictionary=False)
                cursor.execute(query, tuple(data.values()))

                if not self.use_connection_pool:
                    connection.commit()

                result = cursor.lastrowid
                self.logger.debug(f"Inserted record into {self.get_table_name()}, ID: {result}")

                # 关闭游标
                if cursor:
                    cursor.close()

                # 连接池模式下归还连接
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)

                return result

            except Exception as e:
                # 出错时确保关闭游标和归还连接
                if cursor:
                    cursor.close()
                if self.use_connection_pool:
                    self.connection_pool.return_connection(connection)
                raise

        try:
            if self.use_connection_pool and hasattr(self, 'retry_manager'):
                result = self.retry_manager.retry_with_backoff(_insert)
            else:
                result = _insert()

            # 记录成功指标
            if self.use_connection_pool:
                self.connection_pool.record_operation_success('insert', 0)

            return result

        except Exception as e:
            self.logger.error(f"Insert failed: {e}")
            if self.use_connection_pool:
                self.connection_pool.record_operation_error('insert', str(e))
            raise
    
    def update(self, id_value: Any, data: Dict[str, Any], id_column: str = 'id') -> int:
        """更新一条记录"""
        if id_column in data:
            del data[id_column]

        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
        query = f"UPDATE {self.get_table_name()} SET {set_clause} WHERE {id_column} = %s"

        params = tuple(data.values()) + (id_value,)
        return self.execute_query(query, params)
    
    def delete(self, id_value: Any, id_column: str = 'id') -> int:
        """删除一条记录"""
        query = f"DELETE FROM {self.get_table_name()} WHERE {id_column} = %s"
        return self.execute_query(query, (id_value,))
    
    def begin_transaction(self):
        """开始事务"""
        try:
            connection = self._get_connection()
            connection.autocommit = False
            self.logger.info("Transaction began")
        except Error as e:
            self.logger.error(f"Begin transaction failed: {e}")
            raise
    
    def commit_transaction(self):
        """提交事务"""
        try:
            if self.connection and not self.connection.autocommit:
                self.connection.commit()
                self.connection.autocommit = True
                self.logger.info("Transaction committed")
        except Error as e:
            self.logger.error(f"Commit transaction failed: {e}")
            raise
    
    def rollback_transaction(self):
        """回滚事务"""
        try:
            if self.connection and not self.connection.autocommit:
                self.connection.rollback()
                self.connection.autocommit = True
                self.logger.info("Transaction rolled back")
        except Error as e:
            self.logger.error(f"Rollback transaction failed: {e}")
            raise