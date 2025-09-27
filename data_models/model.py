import logging
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from mysql.connector import Error
from core.database.database import get_db_connection

class Model(ABC):
    """
    与数据库交互的基类，供其他类继承使用
    """
    def __init__(self):
        """
        初始化Model基类
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connection = None
        self.cursor = None
        
    def __del__(self):
        """
        析构函数，确保关闭数据库连接
        """
        self._close_connection()
        
    @abstractmethod
    def get_table_name(self) -> str:
        """
        获取表名的抽象方法，子类必须实现此方法
        
        Returns:
            str: 数据库表名
        """
        pass
        
    def _get_connection(self):
        """
        获取数据库连接
        
        Returns:
            mysql.connector.connection.MySQLConnection: 数据库连接对象
        """
        if not self.connection or not self.connection.is_connected():
            self.connection = get_db_connection()
        return self.connection
        
    def _get_cursor(self, dictionary: bool = True):
        """
        获取数据库游标
        
        Args:
            dictionary: 是否返回字典形式的结果
        
        Returns:
            mysql.connector.cursor.MySQLCursor: 数据库游标对象
        """
        try:
            # 确保获取有效的数据库连接
            connection = self._get_connection()
            
            # 不重复使用游标，每次都创建新的游标以避免连接问题
            self.cursor = connection.cursor(dictionary=dictionary)
            
            return self.cursor
        except Exception as e:
            self.logger.error(f"Failed to get cursor: {e}")
            # 发生异常时，重新获取连接并创建游标
            self.connection = None  # 重置连接以强制获取新连接
            connection = self._get_connection()
            self.cursor = connection.cursor(dictionary=dictionary)
            return self.cursor
        
    def _close_connection(self):
        """
        关闭数据库连接和游标
        """
        if hasattr(self, 'cursor') and self.cursor:
            try:
                self.cursor.close()
            except Exception as e:
                self.logger.error(f"Failed to close cursor: {e}")
            self.cursor = None
            
        if hasattr(self, 'connection') and self.connection and self.connection.is_connected():
            try:
                self.connection.close()
            except Exception as e:
                self.logger.error(f"Failed to close connection: {e}")
            self.connection = None
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        执行SQL查询（INSERT、UPDATE、DELETE）
        
        Args:
            query: SQL查询语句
            params: 查询参数（用于参数化查询，防止SQL注入）
        
        Returns:
            int: 受影响的行数
        
        Raises:
            Error: 数据库操作错误
        """
        try:
            cursor = self._get_cursor(dictionary=False)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # 提交事务
            self.connection.commit()
            # 为execute_query添加更详细的信息，包含操作类型标识和部分SQL语句
            # 提取SQL语句的前30个字符作为标识，避免日志过长
            query_summary = query.strip().split('\n')[0][:30] + ('...' if len(query.strip()) > 30 else '')
            # 检查是哪种操作类型
            operation_type = "OTHER"
            query_upper = query.strip().upper()
            if query_upper.startswith("INSERT INTO messages"):
                operation_type = "INSERT_MESSAGE"
            elif query_upper.startswith("INSERT"):
                operation_type = "INSERT"
            elif query_upper.startswith("UPDATE"):
                operation_type = "UPDATE"
            elif query_upper.startswith("DELETE"):
                operation_type = "DELETE"
            elif query_upper.startswith("SELECT"):
                operation_type = "SELECT"
            
            self.logger.info(f"[EXECUTE_{operation_type}] Query executed, affected rows: {cursor.rowcount}, query: {query_summary}")
            return cursor.rowcount
        except Error as e:
            self.logger.error(f"Database execute failed: {e}")
            if self.connection:
                self.connection.rollback()
            raise
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """
        执行SQL查询并返回单行结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
        
        Returns:
            Optional[Dict[str, Any]]: 查询结果字典，无结果时返回None
        """
        try:
            cursor = self._get_cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchone()
            
            found_status = "Found" if result else "Not found"
            # 将fetch_one的日志降低为debug级别，避免与其他查询操作的info日志重复
            self.logger.debug(f"[FIND_ONE] {found_status} record from {self.get_table_name()}")
            return result
        except Error as e:
            self.logger.error(f"Database fetch one failed: {e}")
            raise
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        执行SQL查询并返回所有结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
        
        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        try:
            cursor = self._get_cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchall()
            # 更新fetch_all方法日志格式，与fetch_one保持一致
            self.logger.info(f"[FETCH_ALL] Fetched {len(result)} records from {self.get_table_name()}")
            return result
        except Error as e:
            self.logger.error(f"Database fetch all failed: {e}")
            raise
    
    def find_by_id(self, id_value: Any, id_column: str = 'id') -> Optional[Dict[str, Any]]:
        """
        根据ID查找记录
        
        Args:
            id_value: ID值
            id_column: ID列名，默认为'id'
        
        Returns:
            Optional[Dict[str, Any]]: 查询到的记录，无结果时返回None
        """
        query = f"SELECT * FROM {self.get_table_name()} WHERE {id_column} = %s"
        return self.fetch_one(query, (id_value,))
    
    def find_all(self) -> List[Dict[str, Any]]:
        """
        查询表中的所有记录
        
        Returns:
            List[Dict[str, Any]]: 所有记录列表
        """
        query = f"SELECT * FROM {self.get_table_name()}"
        return self.fetch_all(query)
    
    def insert(self, data: Dict[str, Any]) -> int:
        """
        插入一条记录
        
        Args:
            data: 要插入的数据字典
        
        Returns:
            int: 插入的ID（如果表有自增主键）
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {self.get_table_name()} ({columns}) VALUES ({placeholders})"
        
        try:
            cursor = self._get_cursor(dictionary=False)
            cursor.execute(query, tuple(data.values()))
            self.connection.commit()
            
            # 将insert的详细日志降低为debug级别，避免与execute_query的info日志重复
            # execute_query已经记录了主要的执行信息
            self.logger.debug(f"[INSERT] Successfully inserted record into {self.get_table_name()}, new ID: {cursor.lastrowid}")
            return cursor.lastrowid
        except Error as e:
            self.logger.error(f"Database insert failed: {e}")
            if self.connection:
                self.connection.rollback()
            raise
    
    def update(self, id_value: Any, data: Dict[str, Any], id_column: str = 'id') -> int:
        """
        更新一条记录
        
        Args:
            id_value: 要更新记录的ID
            data: 要更新的数据字典
            id_column: ID列名，默认为'id'
        
        Returns:
            int: 受影响的行数
        """
        # 排除ID列
        if id_column in data:
            del data[id_column]
            
        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
        query = f"UPDATE {self.get_table_name()} SET {set_clause} WHERE {id_column} = %s"
        
        params = tuple(data.values()) + (id_value,)
        
        affected_rows = self.execute_query(query, params)
        
        # 将update的详细日志降低为debug级别，避免与execute_query的info日志重复
        # execute_query已经记录了主要的执行信息
        self.logger.debug(f"[UPDATE] Completed update operation on {self.get_table_name()}, id: {id_value}, columns: {list(data.keys())}")
        return affected_rows
    
    def delete(self, id_value: Any, id_column: str = 'id') -> int:
        """
        删除一条记录
        
        Args:
            id_value: 要删除记录的ID
            id_column: ID列名，默认为'id'
        
        Returns:
            int: 受影响的行数
        """
        query = f"DELETE FROM {self.get_table_name()} WHERE {id_column} = %s"
        return self.execute_query(query, (id_value,))
    
    def begin_transaction(self):
        """
        开始事务
        """
        try:
            connection = self._get_connection()
            # MySQL默认是自动提交的，这里关闭自动提交以开始事务
            connection.autocommit = False
            self.logger.info("Transaction began")
        except Error as e:
            self.logger.error(f"Begin transaction failed: {e}")
            raise
    
    def commit_transaction(self):
        """
        提交事务
        """
        try:
            if self.connection and not self.connection.autocommit:
                self.connection.commit()
                self.connection.autocommit = True  # 恢复自动提交
                self.logger.info("Transaction committed")
        except Error as e:
            self.logger.error(f"Commit transaction failed: {e}")
            raise
    
    def rollback_transaction(self):
        """
        回滚事务
        """
        try:
            if self.connection and not self.connection.autocommit:
                self.connection.rollback()
                self.connection.autocommit = True  # 恢复自动提交
                self.logger.info("Transaction rolled back")
        except Error as e:
            self.logger.error(f"Rollback transaction failed: {e}")
            raise