import signal
import time
import warnings
import gc
import os
import multiprocessing
import uvicorn
from multiprocessing import Process
from config import Config
def run_mcp_server():
    """运行 MCP 服务"""
    # 确保环境变量设置正确
    os.environ['CURRENT_PORT'] = str(Config.MCP_PORT)
    setup_logging()
    # 调用 app.py 中的 run_mcp_server 函数
    from app import run_mcp_server as app_run_mcp_server
    app_run_mcp_server()
from core.log import setup_logging
def run_dingtalk_server():
    """运行钉钉服务"""
    # 确保环境变量设置正确
    os.environ['CURRENT_PORT'] = str(Config.DINGTALK_PORT)
    setup_logging()
    # 调用钉钉服务的入口函数
    from core.dingtalk.message_manager import main as dingtalk_main
    dingtalk_main()

warnings.filterwarnings("ignore", message="resource_tracker: There appear to be .* leaked semaphore objects")

def run_fastapi_server():
    """运行 FastAPI 服务（Uvicorn）"""

    # 设置环境变量标识当前进程端口
    os.environ['CURRENT_PORT'] = str(Config.PORT)
    setup_logging()
    uvicorn.run(
        "app:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=False,  # 多进程下 reload 可能有问题，建议关闭
        log_level="info"
    )

def signal_handler(sig, frame, fastapi_process, mcp_process, dingtalk_process):
    """信号处理函数，关闭服务"""
    shutdown_servers(fastapi_process, mcp_process, dingtalk_process)

def shutdown_servers(fastapi_process, mcp_process, dingtalk_process):
    """服务器进程"""
    # 终止进程
    if fastapi_process.is_alive():
        fastapi_process.terminate()
    if mcp_process.is_alive():
        mcp_process.terminate()
    if dingtalk_process.is_alive():
        dingtalk_process.terminate()
    
    # 等待进程完全退出，确保资源被释放
    print("waiting for processes to terminate...")
    fastapi_process.join(timeout=5)  # 设置超时，避免无限等待
    mcp_process.join(timeout=5)
    dingtalk_process.join(timeout=5)
    
    # 检查进程是否已终止，如果未终止，尝试强制终止
    if fastapi_process.is_alive():
        print("warning: FastAPI process failed to terminate in time, force termination...")
        fastapi_process.kill()
    if mcp_process.is_alive():
        print("warning: MCP process failed to terminate in time, force termination...")
        mcp_process.kill()
    if dingtalk_process.is_alive():
        print("warning: DingTalk process failed to terminate in time, force termination...")
        dingtalk_process.kill()
    
    # 等待一段时间，确保强制终止生效
    time.sleep(0.5)
    
    # 执行垃圾回收
    gc.collect()
    
    print("All resources have been released")

def main():
    
    # 检查是否已经设置过 start method
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method("spawn")
    
    # 三个进程分别运行 Uvicorn、MCP 和钉钉服务
    # 进程函数内部会设置自己的环境变量
    fastapi_process = Process(target=run_fastapi_server)
    mcp_process = Process(target=run_mcp_server)
    dingtalk_process = Process(target=run_dingtalk_server)

    # 设置信号处理程序
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, fastapi_process, mcp_process, dingtalk_process))
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, fastapi_process, mcp_process, dingtalk_process))

    # 启动所有服务
    print(f"Starting FastAPI server on port {Config.PORT}...")
    fastapi_process.start()
    print(f"Starting MCP server on port {Config.MCP_PORT}...")
    mcp_process.start()
    print(f"Starting DingTalk server on port {Config.DINGTALK_PORT}...")
    dingtalk_process.start()

    try:
        # 等待所有进程（Ctrl+C 可终止）
        fastapi_process.join()
        mcp_process.join()
        dingtalk_process.join()
    except KeyboardInterrupt:
        shutdown_servers(fastapi_process, mcp_process, dingtalk_process)
    except Exception as e:
        print(f"Error: {str(e)}")
        shutdown_servers(fastapi_process, mcp_process, dingtalk_process)

if __name__ == "__main__":
    main()