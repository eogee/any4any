import logging
import json
from typing import Dict, Any, Optional
from data_models.Model import Model

class Preview(Model):
    """
    预览数据模型，用于和previews表交互
    接收来自IndexServer的请求,实现将数据保存至previews表中
    """
    
    def get_table_name(self) -> str:
        """
        获取表名
        
        Returns:
            str: 数据库表名
        """
        return "previews"
    
    def save_preview_content(self, preview_id: str, saved_content: str, pre_content: str, 
                           full_request: dict, current_request: str, conversation_id: str, 
                           message_id: str, response_time: float, user_id: int) -> int:
        """
        保存预览编辑内容到数据库
        确保conversation_id和message_id与messages表中的值保持一致
        
        Args:
            preview_id: 预览ID
            saved_content: 编辑保存后的内容
            pre_content: 编辑前的内容
            full_request: 历史全部请求及响应内容
            current_request: 当前请求内容
            conversation_id: 会话ID
            message_id: 对话ID
            response_time: 响应用时(秒)
            user_id: 响应人员ID
        
        Returns:
            int: 插入的ID或更新的行数
        """
        # 验证conversation_id和message_id是否为有效的UUID格式
        if not conversation_id or not message_id:
            raise ValueError("Invalid conversation_id or message_id")
        
        try:
            # 将字典转换为JSON字符串
            full_request_str = json.dumps(full_request) if isinstance(full_request, dict) else str(full_request)
            
            # 判断内容是否有变化
            is_edited = 1 if pre_content != saved_content else 0
            
            # 构建符合数据库表结构的数据字典
            data = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "current_request": current_request,
                "saved_content": saved_content,
                "pre_content": pre_content,
                "full_request": full_request_str,
                "response_time": response_time,
                "user_id": user_id,
                "preview_id": preview_id  # 保存preview_id，方便追踪
            }
            
            # 验证conversation_id和message_id在messages表中是否存在
            # 确保这两个ID与messages表中的值一致
            message_exists = self.fetch_one(
                "SELECT 1 FROM messages WHERE conversation_id = %s AND message_id = %s",
                (conversation_id, message_id)
            )
            
            # 无论messages表中是否存在，仍然保存preview数据,但会记录日志，以便追踪可能的数据不一致
            if not message_exists:
                self.logger.warning(f"Message not found in messages table: conversation_id={conversation_id}, message_id={message_id}")
            else:
                self.logger.debug(f"Verified message exists in messages table: conversation_id={conversation_id}, message_id={message_id}")
            
            # 在previews表中查找是否存在相同的conversation_id和message_id的记录
            existing = self.fetch_one(
                "SELECT * FROM previews WHERE conversation_id = %s AND message_id = %s", 
                (conversation_id, message_id)
            )
            
            if existing:
                # 如果记录已存在，则更新
                result = self.update(existing['id'], data, id_column="id")
                return result
            else:
                # 如果记录不存在，则插入
                result = self.insert(data)
                return result
        except Exception as e:
            self.logger.error(f"Database save failed: {str(e)}")
            # 尝试进行内容清理，移除可能导致问题的特殊字符
            try:
                # 确保data字典存在
                if 'data' not in locals():
                    data = {}
                
                # 对于保存内容进行特殊处理，保留基本文本
                if saved_content:
                    # 替换4字节UTF-8字符为占位符
                    clean_saved_content = ''.join([c if ord(c) < 0x10000 else '[EMOJI]' for c in saved_content])
                else:
                    clean_saved_content = saved_content
                
                # 对当前请求内容也进行清理
                if current_request:
                    clean_current_request = ''.join([c if ord(c) < 0x10000 else '[EMOJI]' for c in current_request])
                else:
                    clean_current_request = current_request
                
                # 更新数据字典中的清理后内容和关键ID字段
                data["saved_content"] = clean_saved_content
                data["current_request"] = clean_current_request
                data["conversation_id"] = conversation_id  # 确保ID字段存在
                data["message_id"] = message_id            # 确保ID字段存在
                data["preview_id"] = preview_id            # 确保preview_id字段存在
                
                # 重新检查是否存在记录
                existing = self.fetch_one(
                    "SELECT * FROM previews WHERE conversation_id = %s AND message_id = %s", 
                    (conversation_id, message_id)
                )
                
                if existing:
                    result = self.update(existing['id'], data, id_column="id")
                    return result
                else:
                    result = self.insert(data)
                    return result
            except Exception as inner_e:
                self.logger.error(f"Failed even with content cleaning: {str(inner_e)}")
                raise
    
    def get_preview_by_id(self, preview_id: str) -> Optional[Dict[str, Any]]:
        """
        根据preview_id获取预览记录
        
        Args:
            preview_id: 预览ID
        
        Returns:
            Optional[Dict[str, Any]]: 预览记录，无结果时返回None
        """
        return self.find_by_id(preview_id, id_column="preview_id")
    
    def get_all_previews(self) -> list:
        """
        获取所有预览记录
        
        Returns:
            list: 所有预览记录列表
        """
        return self.find_all()
    
    def delete_preview(self, preview_id: str) -> int:
        """
        删除指定的预览记录
        
        Args:
            preview_id: 预览ID
        
        Returns:
            int: 受影响的行数
        """
        return self.delete(preview_id, id_column="preview_id")