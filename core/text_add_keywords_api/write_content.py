import os
from fastapi import Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from core.api_models import TextRequest

import json

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
    :param filename: 文件名（默认 text_add_keywords.txt）
    :return: 文件路径
    """
    filepath = os.path.join("data", filename)
    with open(filepath, "a", encoding="utf-8") as file:
        file.write(content + "\n")  # 追加内容并换行
    return filepath

async def write_content(
    content: str = Form(None, description="直接传递文本内容或JSON格式的content字段"), 
    keywords: str = Form(None, description="关键词内容，会过滤<think>标签并拼接<<<<<"),
    file: UploadFile = Form(None, description="或通过文件上传内容")
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
        filepath = write_content_to_file(text_content)
        return JSONResponse(
            status_code=200,
            content={"message": "内容已写入文件", "filepath": filepath}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
