# 启动文件
from fastapi import FastAPI
import uvicorn
from config import Config
from core.log import setup_logging

def main():
    # 初始化日志
    setup_logging()

    # 启动服务
    uvicorn.run(
        "app:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
