import logging
from typing import Dict, Any, Optional
from data_models.Auth import AuthModel

logger = logging.getLogger(__name__)

class UserContextEnhancer:
    """用户上下文增强器 - 为NL2SQL提供用户元数据支持"""

    def __init__(self):
        self.auth_model = AuthModel()
        self.logger = logging.getLogger(__name__)

    async def get_user_context(self, user_id: str, question: str) -> str:
        """
        获取用户相关的上下文信息

        Args:
            user_id: 用户标识符 (username或user_id)
            question: 用户问题

        Returns:
            格式化的用户上下文信息
        """
        try:
            # 获取用户信息
            user_info = await self._get_user_info(user_id)
            if not user_info:
                self.logger.warning(f"User not found: {user_id}")
                return ""

            # 检查问题是否需要用户上下文
            if not self._needs_user_context(question):
                return ""

            # 构建用户上下文
            context_parts = ["当前用户信息:"]

            if user_info.get('username'):
                context_parts.append(f"- 用户名: {user_info['username']}")

            if user_info.get('nickname') and user_info['nickname'] != user_info.get('username'):
                context_parts.append(f"- 昵称: {user_info['nickname']}")

            if user_info.get('company'):
                context_parts.append(f"- 公司: {user_info['company']}")

            if user_info.get('id'):
                context_parts.append(f"- 用户ID: {user_info['id']}")

            user_context = "\n".join(context_parts)

            return user_context

        except Exception as e:
            self.logger.error(f"Failed to get user context for {user_id}: {e}")
            return ""

    async def _get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            user_id: 用户标识符

        Returns:
            用户信息字典
        """
        try:
            # 首先尝试通过用户名获取
            user = self.auth_model.get_user_by_username(user_id)
            if user:
                return {
                    'id': user.get('id'),
                    'username': user.get('username'),
                    'nickname': user.get('nickname'),
                    'company': user.get('company')
                }

            # 这里可以添加其它查询逻辑
            self.logger.info(f"User not found by username: {user_id}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting user info for {user_id}: {e}")
            return None

    def _needs_user_context(self, question: str) -> bool:
        """
        判断问题是否需要用户上下文

        Args:
            question: 用户问题

        Returns:
            是否需要用户上下文
        """
        # 个人化关键词列表
        personal_keywords = [
            '我的', '我', 'mine', 'my', '本人', '自己',
            '订单', 'account', 'profile', '信息', '记录',
            '购买', '下单', '支付', '配送', '收货',
            '我的订单', '我的信息', '我的账户', '我的历史',
            '我的购买', '我的记录', '我的数据', '我的状态'
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in personal_keywords)

# 全局实例
_user_context_enhancer = None

def get_user_context_enhancer() -> UserContextEnhancer:
    """获取用户上下文增强器单例"""
    global _user_context_enhancer
    if _user_context_enhancer is None:
        _user_context_enhancer = UserContextEnhancer()
    return _user_context_enhancer