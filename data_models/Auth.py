import logging
from typing import Optional, Dict, Any
from mysql.connector import Error
from data_models.Model import Model

class AuthModel(Model):
    """
    用户认证相关的数据库交互模型
    负责用户登录、验证等数据库操作
    """
    
    def __init__(self):
        """
        初始化AuthModel
        """
        super().__init__()
        self.logger = logging.getLogger('AuthModel')
        
    def get_table_name(self) -> str:
        """
        获取表名
        
        Returns:
            str: 数据库表名
        """
        return 'users'
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            Optional[Dict[str, Any]]: 用户信息字典，如果用户不存在则返回None
        """
        try:
            query = f"SELECT * FROM {self.get_table_name()} WHERE username = %s"
            cursor = self._get_cursor()
            cursor.execute(query, (username,))
            result = cursor.fetchone()
            return result
        except Error as e:
            self.logger.error(f"Error getting user by username: {e}")
            raise
    
    def verify_user_credentials(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        验证用户凭据
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            Optional[Dict[str, Any]]: 用户信息字典，如果验证成功；否则返回None
        """
        try:
            user = self.get_user_by_username(username)
            if user:
                # TODO: 验证密码，这里简单比较密码哈希，后续使用密码哈希进行验证
                if user['password_hash'] == password:
                    return user
            return None
        except Error as e:
            self.logger.error(f"Error verifying user credentials: {e}")
            raise
    
    def __del__(self):
        """
        析构函数，确保关闭数据库连接
        """
        self._close_connection()