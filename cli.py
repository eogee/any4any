import multiprocessing
from multiprocessing import Process
from config import Config
import uvicorn
from app import run_mcp_server
from core.log import setup_logging

def run_fastapi_server():
    """运行 FastAPI 服务（Uvicorn）"""
    setup_logging()
    uvicorn.run(
        "app:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=False,  # 多进程下 reload 可能有问题，建议关闭
        log_level="info"
    )

def main():
    # 检查是否已经设置过 start method
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method("spawn")
    
    # 创建两个进程分别运行 Uvicorn 和 MCP
    fastapi_process = Process(target=run_fastapi_server)
    mcp_process = Process(target=run_mcp_server)

    # 启动进程
    fastapi_process.start()
    mcp_process.start()

    try:
        # 等待两个进程（Ctrl+C 可终止）
        fastapi_process.join()
        mcp_process.join()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        fastapi_process.terminate()
        mcp_process.terminate()

if __name__ == "__main__":
    main()