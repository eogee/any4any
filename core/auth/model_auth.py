from typing import Optional
from config import Config
from fastapi import Header, HTTPException

async def verify_token(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authentication required",
                "message": "Please include your API key in the Authorization header",
                "format": "Bearer YOUR_API_KEY",
                "documentation": "https://example.com/api-docs"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid authorization format",
                "message": "Authorization header must start with 'Bearer '",
                "example": "Bearer abc123def456"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    token = authorization[7:]

    # 如果API_KEY为空字符串或"EMPTY"，允许访问（开发模式）
    if Config.API_KEY == "EMPTY" or Config.API_KEY == "":
        return

    if token != Config.API_KEY:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Invalid API key",
                "message": "The provided API key is not valid",
                "solution": "Check your API key or contact support"
            }
        )
