from fastapi import Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from api_models import TextRequest
from core.text_deal.writer import write_content_to_file
from core.text_deal.keywords import process_keywords
import json

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
