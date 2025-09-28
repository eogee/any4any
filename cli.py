import signal
import time
import warnings
import gc
import os
import multiprocessing
import uvicorn
from multiprocessing import Process
from config import Config
from core.log import setup_logging

def run_mcp_server():
    os.environ['CURRENT_PORT'] = str(Config.MCP_PORT)
    setup_logging()
    from app import run_mcp_server as app_run_mcp_server
    app_run_mcp_server()

def run_dingtalk_server():
    os.environ['CURRENT_PORT'] = str(Config.DINGTALK_PORT)
    setup_logging()
    from core.dingtalk.message_manager import main as dingtalk_main
    dingtalk_main()

def run_fastapi_server():
    os.environ['CURRENT_PORT'] = str(Config.PORT)
    setup_logging()
    uvicorn.run(
        "app:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=False,
        log_level="info"
    )

warnings.filterwarnings("ignore", message="resource_tracker: There appear to be .* leaked semaphore objects")

def shutdown_servers(processes):
    print("Terminating processes...")
    for name, process in processes.items():
        if process.is_alive():
            process.terminate()
    
    for name, process in processes.items():
        process.join(timeout=5)
        if process.is_alive():
            print(f"Force killing {name}...")
            process.kill()
    
    time.sleep(0.5)
    gc.collect()
    print("All processes terminated")

def signal_handler(sig, frame, processes):
    shutdown_servers(processes)

def main():
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method("spawn")
    
    processes = {
        'fastapi': Process(target=run_fastapi_server),
        'mcp': Process(target=run_mcp_server),
        'dingtalk': Process(target=run_dingtalk_server)
    }

    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, processes))
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, processes))

    print(f"Starting servers...")
    for name, process in processes.items():
        process.start()
        print(f"{name.capitalize()} server started")

    try:
        for process in processes.values():
            process.join()
    except KeyboardInterrupt:
        shutdown_servers(processes)
    except Exception as e:
        print(f"Error: {e}")
        shutdown_servers(processes)

if __name__ == "__main__":
    main()