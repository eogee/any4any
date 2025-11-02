import logging
from typing import Optional, Dict, Any
from mysql.connector import Error
from data_models.model import Model

class AuthModel(Model):
    """用户认证相关的数据库交互模型"""

    def __init__(self):
        super().__init__(use_connection_pool=True)
        self.logger = logging.getLogger('AuthModel')
        
    def get_table_name(self) -> str:
        """获取表名"""
        return 'users'
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户信息"""
        try:
            query = f"SELECT * FROM {self.get_table_name()} WHERE username = %s"
            return self.fetch_one(query, (username,))
        except Exception as e:
            self.logger.error(f"Failed to get user by username: {e}")
            raise
    
    def verify_user_credentials(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户凭据"""
        try:
            user = self.get_user_by_username(username)
            if user:
                # TODO: 使用密码哈希进行验证
                if user['password_hash'] == password:
                    return user
            return None
        except Exception as e:
            self.logger.error(f"Failed to verify credentials: {e}")
            raise