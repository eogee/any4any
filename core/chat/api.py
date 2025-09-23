from fastapi.responses import JSONResponse
from core.chat.preview import preview_service

async def get_pending_previews():
    """获取所有等待确认的预览列表"""
    try:
        pending_previews = await preview_service.get_pending_previews()
        return JSONResponse(pending_previews)
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

async def get_preview(preview_id: str):
    """获取预览详情"""
    try:
        preview = await preview_service.get_preview(preview_id)
        return JSONResponse({
            "preview_id": preview.preview_id,
            "request": preview.request_data,
            "status": "preview"
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

async def confirm_preview(preview_id: str):
    """确认预览请求并返回最终响应"""
    try:
        response = await preview_service.confirm_preview(preview_id)
        return JSONResponse(response)
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

async def get_preview_data(preview_id: str):
    """获取预览数据"""
    try:
        preview = await preview_service.get_preview(preview_id)
        return JSONResponse({
            "preview_id": preview.preview_id,
            "request": preview.request_data,
            "generated_content": preview.generated_content,
            "edited_content": preview.edited_content,
            "status": "preview"
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)


async def update_preview_content(preview_id: str, request: Request):
    """更新保存预览内容"""
    try:
        data = await request.json()
        edited_content = data.get("content", "")
        await preview_service.update_content(preview_id, edited_content)
        return JSONResponse({
            "status": "success",
            "message": "Content updated successfully"
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)

async def get_final_result(preview_id: str):
    """获取预览确认后的最终结果"""
    try:
        preview = await preview_service.get_preview(preview_id)
        if not preview.confirmed:
            return JSONResponse({
                "status": "waiting",
                "message": "Preview not confirmed yet",
                "preview_url": f"/preview/{preview_id}"
            })
        
        # 返回确认后的最终响应
        return JSONResponse(preview.response_data)
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=400)
