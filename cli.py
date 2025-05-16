#!/usr/bin/env python
from fastapi import FastAPI
import uvicorn
from config import Config
import services
import core_services

def main():
    # 初始化日志
    core_services.setup_logging()

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
