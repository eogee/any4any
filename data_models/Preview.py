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
    
    def save_preview_content(self, preview_id: str, edited_content: str, pre_content: str, 
                           full_request: dict, last_request: dict) -> int:
        """
        保存预览编辑内容到数据库
        
        Args:
            preview_id: 预览ID
            edited_content: 编辑后的内容
            pre_content: 编辑前的内容
            full_request: 历史全部请求及响应内容
            last_request: 当前请求内容
        
        Returns:
            int: 插入的ID或更新的行数
        """
        try:
            # 检查是否已存在该preview_id的记录
            existing = self.find_by_id(preview_id, id_column="preview_id")
            
            # 将字典转换为JSON字符串
            full_request_str = json.dumps(full_request) if isinstance(full_request, dict) else str(full_request)
            last_request_str = json.dumps(last_request) if isinstance(last_request, dict) else str(last_request)
            
            # 判断内容是否有变化
            is_edited = 1 if pre_content != edited_content else 0
            
            data = {
                "preview_id": preview_id,
                "edited_content": edited_content,
                "pre_content": pre_content,
                "is_edited": is_edited,
                "full_request": full_request_str,
                "last_request": last_request_str
            }
            
            if existing:
                # 如果记录已存在，则更新
                result = self.update(preview_id, data, id_column="preview_id")
                self.logger.info(f"Updated preview content: {preview_id}")
                return result
            else:
                # 如果记录不存在，则插入
                result = self.insert(data)
                self.logger.info(f"Inserted new preview content: {preview_id}")
                return result
        except Exception as e:
            self.logger.error(f"Database save failed: {str(e)}")
            # 尝试进行内容清理，移除可能导致问题的特殊字符
            try:
                # 对于编辑内容进行特殊处理，保留基本文本
                if edited_content:
                    # 替换4字节UTF-8字符为占位符
                    clean_edited_content = ''.join([c if ord(c) < 0x10000 else '[EMOJI]' for c in edited_content])
                else:
                    clean_edited_content = edited_content
                
                # 更新数据字典中的清理后内容
                data["edited_content"] = clean_edited_content
                
                if existing:
                    result = self.update(preview_id, data, id_column="preview_id")
                    self.logger.info(f"Successfully saved with cleaned content: {preview_id}")
                    return result
                else:
                    result = self.insert(data)
                    self.logger.info(f"Successfully inserted with cleaned content: {preview_id}")
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