import signal
import time
import warnings
import gc
import multiprocessing
from multiprocessing import Process
import uvicorn
from config import Config
from app import run_mcp_server
from core.log import setup_logging

warnings.filterwarnings("ignore", message="resource_tracker: There appear to be .* leaked semaphore objects")

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


def signal_handler(sig, frame, fastapi_process, mcp_process):
    """信号处理函数，关闭服务"""
    shutdown_servers(fastapi_process, mcp_process)


def shutdown_servers(fastapi_process, mcp_process):
    """服务器进程"""
    # 终止进程
    if fastapi_process.is_alive():
        fastapi_process.terminate()
    if mcp_process.is_alive():
        mcp_process.terminate()
    
    # 等待进程完全退出，确保资源被释放
    print("waiting for processes to terminate...")
    fastapi_process.join(timeout=5)  # 设置超时，避免无限等待
    mcp_process.join(timeout=5)
    
    # 检查进程是否已终止，如果未终止，尝试强制终止
    if fastapi_process.is_alive():
        print("warning: FastAPI process failed to terminate in time, force termination...")
        fastapi_process.kill()
    if mcp_process.is_alive():
        print("warning: MCP process failed to terminate in time, force termination...")
        mcp_process.kill()
    
    # 等待一段时间，确保强制终止生效
    time.sleep(0.5)
    
    # 执行垃圾回收
    gc.collect()
    
    print("All resources have been released")

def main():
    # 检查是否已经设置过 start method
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method("spawn")
    
    # 两个进程分别运行 Uvicorn 和 MCP
    fastapi_process = Process(target=run_fastapi_server)
    mcp_process = Process(target=run_mcp_server)

    # 设置信号处理程序
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, fastapi_process, mcp_process))
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, fastapi_process, mcp_process))

    fastapi_process.start()    
    mcp_process.start()

    try:
        # 等待两个进程（Ctrl+C 可终止）
        fastapi_process.join()
        mcp_process.join()
    except KeyboardInterrupt:
        shutdown_servers(fastapi_process, mcp_process)
    except Exception as e:
        print(f"Error: {str(e)}")
        shutdown_servers(fastapi_process, mcp_process)

if __name__ == "__main__":
    main()