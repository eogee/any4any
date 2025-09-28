import logging
import json
from typing import Dict, Any, Optional
from data_models.model import Model

class Preview(Model):
    """预览数据模型，用于和previews表交互"""
    
    def get_table_name(self) -> str:
        """获取表名"""
        return "previews"
    
    def save_preview_content(self, preview_id: str, saved_content: str, pre_content: str, 
                           full_request: dict, current_request: str, conversation_id: str, 
                           message_id: str, response_time: float, user_id: int) -> int:
        """保存预览编辑内容到数据库"""
        if not conversation_id or not message_id:
            raise ValueError("Invalid conversation_id or message_id")
        
        try:
            full_request_str = json.dumps(full_request) if isinstance(full_request, dict) else str(full_request)
            is_edited = 1 if pre_content != saved_content else 0
            
            data = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "current_request": current_request,
                "saved_content": saved_content,
                "pre_content": pre_content,
                "full_request": full_request_str,
                "response_time": response_time,
                "user_id": user_id,
                "preview_id": preview_id
            }
            
            # 验证消息是否存在
            message_exists = self.fetch_one(
                "SELECT 1 FROM messages WHERE conversation_id = %s AND message_id = %s",
                (conversation_id, message_id)
            )
            
            if not message_exists:
                self.logger.warning(f"Message not found: {conversation_id}, {message_id}")
            else:
                self.logger.debug(f"Message verified: {conversation_id}, {message_id}")
            
            # 检查是否已存在记录
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
                
        except Exception as e:
            self.logger.error(f"Save preview failed: {str(e)}")
            raise
    
    def get_preview_by_id(self, preview_id: str) -> Optional[Dict[str, Any]]:
        """根据preview_id获取预览记录"""
        return self.find_by_id(preview_id, id_column="preview_id")
    
    def get_all_previews(self) -> list:
        """获取所有预览记录"""
        return self.find_all()
    
    def delete_preview(self, preview_id: str) -> int:
        """删除指定的预览记录"""
        return self.delete(preview_id, id_column="preview_id")