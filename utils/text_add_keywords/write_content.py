import os
import re
import json
import logging
from fastapi import Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

def process_keywords(keywords: str) -> str:
    """
    处理关键词内容
    :param keywords: 原始关键词内容
    :return: 处理后的文本内容
    """
    # 过滤各种形式的<think>标签并拼接<<<<<
    return re.sub(r'<think\b[^>]*>.*?</think>', '', keywords, flags=re.DOTALL) + "<<<<<"

def write_content_to_file(content: str, filename: str = "text_add_keywords.txt") -> str:
    """
    将内容写入文件（如果文件不存在则创建）
    :param content: 要写入的文本内容
    :param filename: 文件名（默认text_add_keywords.txt）
    :return: 文件路径
    """
    try:
        # 确保data目录存在
        os.makedirs("data", exist_ok=True)
        
        # 强制使用.txt扩展名
        base_name = os.path.splitext(filename)[0]
        filename = f"{base_name}.txt"
        
        filepath = os.path.join("data", filename)
        # 安全检查：确保路径在data目录下
        if not os.path.abspath(filepath).startswith(os.path.abspath("data")):
            raise ValueError("Invalid file path")
            
        with open(filepath, "a", encoding="utf-8") as file:
            file.write(content)
        return filepath
    except Exception as e:
        logger.error(f"Failed to write to file {filename}: {str(e)}")
        raise

async def write_content(
    content: str = Form(None, description="直接传递文本内容或JSON格式的content字段"), 
    keywords: str = Form(None, description="关键词内容，会过滤<think>标签并拼接<<<<<"),
    file: UploadFile = Form(None, description="或通过文件上传内容"),
    filename: str = Form("text_add_keywords.txt", description="要写入的文件名，默认为text_add_keywords.txt")
):
    """
    接收 form-data 格式的 POST 请求，支持多种方式提交内容：
    1. 直接传递 `content` 字段的文本
    2. 传递 `keywords` 字段的文本(会过滤<think>标签并拼接<<<<<)
    3. 传递JSON格式的content字段，如 {"content":"文本内容"}
    4. 通过文件上传（文件内容作为文本）
    """
    try:
        # 处理传入的内容
        if keywords:
            text_content = process_keywords(keywords)
        elif content:
            try:
                # 尝试解析JSON格式的content
                content_json = json.loads(content)
                if isinstance(content_json, dict) and "content" in content_json:
                    text_content = content_json["content"]
                else:
                    text_content = content
            except json.JSONDecodeError:
                text_content = content
            # 对content字段进行额外处理
            text_content = text_content
        elif file:
            text_content = (await file.read()).decode("utf-8")
        else:
            raise HTTPException(status_code=400, detail="必须提供 content、keywords 或 file 字段")
        
        # 写入文件
        filepath = write_content_to_file(text_content, filename)
        return JSONResponse(
            status_code=200,
            content={"message": "内容已写入文件", "filepath": filepath}
        )
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid JSON format: {str(e)}"
        )
    except IOError as e:
        logger.error(f"File write error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"File write error: {str(e)}. Please check file permissions."
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )