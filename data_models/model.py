import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from mysql.connector import Error
from core.database.database import get_db_connection

class Model(ABC):
    """与数据库交互的基类，供其他类继承使用"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connection = None
        self.cursor = None
        
    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self._close_connection()
        
    @abstractmethod
    def get_table_name(self) -> str:
        """获取表名的抽象方法，子类必须实现此方法"""
        pass
        
    def _get_connection(self):
        """获取数据库连接"""
        if not self.connection or not self.connection.is_connected():
            self.connection = get_db_connection()
        return self.connection
        
    def _get_cursor(self, dictionary: bool = True):
        """获取数据库游标"""
        try:
            connection = self._get_connection()
            self.cursor = connection.cursor(dictionary=dictionary)
            return self.cursor
        except Exception as e:
            self.logger.error(f"Failed to get cursor: {e}")
            self.connection = None
            connection = self._get_connection()
            self.cursor = connection.cursor(dictionary=dictionary)
            return self.cursor
        
    def _close_connection(self):
        """关闭数据库连接和游标"""
        if self.cursor:
            try:
                self.cursor.close()
            except Exception as e:
                self.logger.error(f"Failed to close cursor: {e}")
            self.cursor = None
            
        if self.connection and self.connection.is_connected():
            try:
                self.connection.close()
            except Exception as e:
                self.logger.error(f"Failed to close connection: {e}")
            self.connection = None
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行SQL查询（INSERT、UPDATE、DELETE）"""
        try:
            cursor = self._get_cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            self.connection.commit()
            
            # 简化日志输出
            query_type = query.strip().upper().split()[0]
            self.logger.info(f"Executed {query_type} query, affected rows: {cursor.rowcount}")
            return cursor.rowcount
        except Error as e:
            self.logger.error(f"Query execution failed: {e}")
            if self.connection:
                self.connection.rollback()
            raise
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """执行SQL查询并返回单行结果"""
        try:
            cursor = self._get_cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchone()
            self.logger.debug(f"Fetched one record from {self.get_table_name()}")
            return result
        except Error as e:
            self.logger.error(f"Fetch one failed: {e}")
            raise
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行SQL查询并返回所有结果"""
        try:
            cursor = self._get_cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchall()
            self.logger.info(f"Fetched {len(result)} records from {self.get_table_name()}")
            return result
        except Error as e:
            self.logger.error(f"Fetch all failed: {e}")
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
        
        try:
            cursor = self._get_cursor(dictionary=False)
            cursor.execute(query, tuple(data.values()))
            self.connection.commit()
            self.logger.debug(f"Inserted record into {self.get_table_name()}, ID: {cursor.lastrowid}")
            return cursor.lastrowid
        except Error as e:
            self.logger.error(f"Insert failed: {e}")
            if self.connection:
                self.connection.rollback()
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