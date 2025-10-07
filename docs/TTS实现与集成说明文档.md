# ANY4ANY TTS 实现与集成说明文档

## 1. EdgeTTS 实现原理

ANY4ANY项目使用edge-tts库实现文本转语音功能。该实现位于`core/tts/speech.py`文件中，核心功能由`create_speech`函数提供。

### 1.1 工作流程

1. **请求验证**：首先验证请求的Authorization头，确保用户有权限调用TTS服务
2. **输入处理**：获取请求中的文本和声音参数，并过滤特殊字符
3. **语音生成**：直接使用edge-tts生成语音文件
4. **响应返回**：以FileResponse形式返回生成的音频文件，并在响应完成后自动清理临时文件

### 1.2 核心实现

项目使用单一的edge-tts引擎进行语音生成：

```python
# 使用edge-tts生成语音
output_file = f"temp_{uuid.uuid4().hex}.mp3"
communicate = Communicate(text, voice)
await communicate.save(output_file)
```

## 2. 文本分块逻辑

EdgeTTS本身没有显式的文本分块逻辑，它会将整个文本作为一个整体处理。但在处理长文本时，可能会受到API的限制。对于超长文本，可以考虑在客户端进行预处理，将文本分割成适当大小的段落分别转换。

## 3. 请求体与响应体

### 3.1 请求体

TTS API接收JSON格式的请求体，包含以下字段：

```json
{
  "input": "需要转换为语音的文本内容",
  "voice": "zh-CN-XiaoyiNeural"  // 可选，声音标识符
}
```

- `input`：必填，需要转换为语音的文本内容
- `voice`：可选，指定使用的声音，默认为配置中的`DEFAULT_VOICE`（通常为"zh-CN-XiaoyiNeural"）

### 3.2 响应体

API返回一个音频文件，以FileResponse形式响应：

```python
return file_response_with_cleanup(
    output_file,
    media_type=media_type,  # 通常为"audio/mpeg"（MP3格式）
    filename=os.path.basename(output_file),
    cleanup_file=output_file
)
```

- 媒体类型：根据文件扩展名自动设置，MP3文件为"audio/mpeg"
- 自动清理：使用`file_response_with_cleanup`类确保响应完成后自动删除临时文件

## 4. 接入其他TTS模型

要接入其他TTS模型，包括本地的IndexTTS-1.5模型，需要按照以下步骤进行：

### 4.1 创建新的TTS引擎类

#### 4.1.1 IndexTTS-1.5引擎实现

对于本地的IndexTTS-1.5模型，我们可以在`core/tts/`目录下创建`index_tts_engine.py`：

```python
import os
import logging
import asyncio
import sys
from typing import Optional

# 添加IndexTTS模块路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'indextts')))

logger = logging.getLogger(__name__)

class IndexTTSEngine:
    """IndexTTS-1.5模型引擎实现"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.model_path = self.config.get('model_path', '/mnt/c/models/IndexTTS-1.5')
        self.device = self.config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self._initialize()
    
    def _initialize(self):
        """初始化IndexTTS-1.5引擎"""
        try:
            logger.info(f"Initializing IndexTTS-1.5 engine from {self.model_path}")
            
            # 导入必要的模块
            from core.tts.indextts.infer import IndexTTSInference
            
            # 初始化模型
            self.model = IndexTTSInference(
                model_path=self.model_path,
                device=self.device
            )
            
            logger.info("IndexTTS-1.5 engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize IndexTTS-1.5 engine: {str(e)}")
            self.model = None
    
    def generate_speech(self, text, output_path, voice=None):
        """生成语音文件
        
        Args:
            text: 要转换的文本
            output_path: 输出文件路径
            voice: 声音选项（IndexTTS支持的声音ID）
            
        Returns:
            bool: 是否成功生成
        """
        try:
            if not self.model:
                logger.error("IndexTTS model not initialized")
                return False
            
            # 设置默认声音或使用指定的声音
            voice_id = voice or "default"
            
            # 使用IndexTTS生成语音
            logger.info(f"Generating speech with IndexTTS-1.5: text length {len(text)}, voice: {voice_id}")
            
            # 调用模型的推理方法
            self.model.infer(
                text=text,
                output_path=output_path,
                voice=voice_id
            )
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Generated speech with IndexTTS-1.5: {output_path}")
                return True
            else:
                logger.error(f"Generated file is empty or does not exist: {output_path}")
                return False
                
        except Exception as e:
            logger.error(f"IndexTTS-1.5 generation failed: {str(e)}")
            return False
    
    def cleanup(self):
        """清理模型资源"""
        try:
            if self.model:
                # 如果模型有清理方法，调用它
                if hasattr(self.model, 'cleanup'):
                    self.model.cleanup()
                self.model = None
                logger.info("IndexTTS-1.5 engine resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up IndexTTS-1.5 engine: {str(e)}")
```

### 4.2 修改`speech.py`集成新引擎

#### 4.2.1 集成IndexTTS-1.5引擎

在`core/tts/speech.py`中集成IndexTTS-1.5引擎：

```python
# 在文件顶部导入新引擎
from core.tts.index_tts_engine import IndexTTSEngine

# 在create_speech函数中添加对IndexTTS-1.5的支持
async def create_speech(request: Request, authorization: str = Header(None)):
    # ...现有代码...
    
    # 添加IndexTTS-1.5引擎支持
    if Config.INDEX_TTS_ENABLED:
        try:
            # 使用线程池执行同步的IndexTTS生成，避免阻塞事件循环
            from concurrent.futures import ThreadPoolExecutor
            
            # 生成输出文件路径
            output_file = f"temp_{uuid.uuid4().hex}.mp3"
            
            if text:
                # 创建引擎实例
                index_tts_engine = IndexTTSEngine({
                    'model_path': Config.INDEX_TTS_MODEL_PATH,
                    'device': Config.INDEX_TTS_DEVICE
                })
                logger.info("Using IndexTTS-1.5 engine for speech generation")
                
                # 在单独的线程中执行模型推理
                with ThreadPoolExecutor() as executor:
                    success = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        index_tts_engine.generate_speech,
                        text,
                        output_file,
                        voice
                    )
                
                if success and os.path.exists(output_file):
                    return file_response_with_cleanup(
                        output_file,
                        media_type="audio/mpeg",
                        filename=os.path.basename(output_file),
                        cleanup_file=output_file
                    )
            else:
                # 处理空文本情况
                with open(output_file, 'wb') as f:
                    f.write(b'')
                return file_response_with_cleanup(
                    output_file,
                    media_type="audio/mpeg",
                    filename=os.path.basename(output_file),
                    cleanup_file=output_file
                )
        except Exception as e:
            logger.error(f"Error generating speech with IndexTTS-1.5 engine: {str(e)}")
            logger.info("Falling back to edge-tts")
    
    # 继续使用edge-tts...
```

### 4.2.2 在ModelManager中集成IndexTTS-1.5（可选）

如果IndexTTS-1.5引擎需要在应用启动时初始化，可以在`model_manager.py`中扩展：

```python
# 在core/model_manager.py文件末尾添加

def initialize_index_tts_engine():
    """初始化IndexTTS-1.5引擎
    
    注意：此函数不会自动调用，需要在lifespan.py中手动调用
    """
    if Config.INDEX_TTS_ENABLED:
        try:
            from core.tts.index_tts_engine import IndexTTSEngine
            logger.info("Initializing IndexTTS-1.5 engine...")
            
            # 预加载模型到内存中
            index_tts_engine = IndexTTSEngine({
                'model_path': Config.INDEX_TTS_MODEL_PATH,
                'device': Config.INDEX_TTS_DEVICE
            })
            
            # 如果实现了单例模式，可以在这里获取实例
            # IndexTTSEngine.get_instance()
            
            logger.info("IndexTTS-1.5 engine initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize IndexTTS-1.5 engine: {str(e)}")
            return False
    return True
```

### 4.2.3 在lifespan.py中集成IndexTTS-1.5引擎

为了符合项目架构，IndexTTS-1.5引擎应该在`lifespan.py`中进行初始化，与其他模型保持一致的生命周期管理：

```python
# 在core/lifespan.py中添加IndexTTS-1.5引擎初始化

# 全局IndexTTS引擎实例
index_tts_engine_instance = None

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    global index_tts_engine_instance
    
    current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
    load_llm = current_port == str(Config.PORT) and current_port == '8888'
    
    logger.info(f"Initializing - PID: {os.getpid()}, Port: {current_port}, Load LLM: {load_llm}")
    
    # 初始化模型管理器
    await ModelManager.initialize(load_llm=load_llm)
    
    # 初始化IndexTTS-1.5引擎（如果启用）
    if Config.INDEX_TTS_ENABLED:
        try:
            from core.tts.index_tts_engine import IndexTTSEngine
            logger.info("Initializing IndexTTS-1.5 engine from lifespan.py")
            
            # 创建引擎实例
            index_tts_engine_instance = IndexTTSEngine({
                'model_path': Config.INDEX_TTS_MODEL_PATH,
                'device': Config.INDEX_TTS_DEVICE
            })
            
            logger.info("IndexTTS-1.5 engine initialization completed")
        except Exception as e:
            logger.error(f"Error initializing IndexTTS-1.5 engine: {str(e)}")
    
    # 初始化知识库服务
    if Config.KNOWLEDGE_BASE_ENABLED:
        initialize_kb_server_after_model()
        logger.info("KnowledgeBaseServer initialization triggered after ModelManager")
    
    # 其他初始化代码...
    
    yield
    
    # 清理代码...
    # 清理IndexTTS-1.5引擎资源
    if index_tts_engine_instance:
        try:
            index_tts_engine_instance.cleanup()
            index_tts_engine_instance = None
            logger.info("IndexTTS-1.5 engine cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up IndexTTS-1.5 engine: {str(e)}")
    
    # 清理其他资源...
    ModelManager.cleanup()
```

### 4.2.4 IndexTTS-1.5引擎单例模式实现

为了避免重复初始化IndexTTS-1.5引擎，可以实现单例模式：

```python
# 在core/tts/index_tts_engine.py中实现单例

import os
import logging
import asyncio
import sys
from typing import Optional
import threading

# 添加IndexTTS模块路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'indextts')))

logger = logging.getLogger(__name__)

class IndexTTSEngine:
    """IndexTTS-1.5模型引擎实现（单例模式）"""
    _instance: Optional['IndexTTSEngine'] = None
    _lock = threading.Lock()
    
    def __new__(cls, config=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(IndexTTSEngine, cls).__new__(cls)
                cls._instance.config = config or {}
                cls._instance.model_path = cls._instance.config.get('model_path', '/mnt/c/models/IndexTTS-1.5')
                cls._instance.device = cls._instance.config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
                cls._instance.model = None
                cls._instance._initialized = False
                cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化IndexTTS-1.5引擎"""
        if not self._initialized:
            try:
                logger.info(f"Initializing IndexTTS-1.5 engine from {self.model_path}")
                
                # 导入必要的模块
                from core.tts.indextts.infer import IndexTTSInference
                
                # 初始化模型
                self.model = IndexTTSInference(
                    model_path=self.model_path,
                    device=self.device
                )
                
                self._initialized = True
                logger.info("IndexTTS-1.5 engine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize IndexTTS-1.5 engine: {str(e)}")
    
    def generate_speech(self, text, output_path, voice=None):
        """生成语音文件
        
        Args:
            text: 要转换的文本
            output_path: 输出文件路径
            voice: 声音选项（IndexTTS支持的声音ID）
            
        Returns:
            bool: 是否成功生成
        """
        try:
            # 确保模型已初始化
            if not self._initialized:
                self._initialize()
                
            if not self.model:
                logger.error("IndexTTS model not initialized")
                return False
            
            # 设置默认声音或使用指定的声音
            voice_id = voice or "default"
            
            # 使用IndexTTS生成语音
            logger.info(f"Generating speech with IndexTTS-1.5: text length {len(text)}, voice: {voice_id}")
            
            # 调用模型的推理方法
            self.model.infer(
                text=text,
                output_path=output_path,
                voice=voice_id
            )
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Generated speech with IndexTTS-1.5: {output_path}")
                return True
            else:
                logger.error(f"Generated file is empty or does not exist: {output_path}")
                return False
                
        except Exception as e:
            logger.error(f"IndexTTS-1.5 generation failed: {str(e)}")
            return False
    
    @classmethod
    def cleanup(cls):
        """清理资源"""
        with cls._lock:
            if cls._instance is not None:
                try:
                    if cls._instance.model:
                        # 如果模型有清理方法，调用它
                        if hasattr(cls._instance.model, 'cleanup'):
                            cls._instance.model.cleanup()
                        cls._instance.model = None
                    logger.info("IndexTTS-1.5 engine resources cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up IndexTTS-1.5 engine: {str(e)}")
                finally:
                    cls._instance = None
    
    @classmethod
    def get_instance(cls, config=None):
        """获取引擎实例的静态方法
        
        Args:
            config: 引擎配置
            
        Returns:
            IndexTTSEngine: 引擎实例
        """
        if cls._instance is None:
            return cls(config)
        return cls._instance
```

通过这种方式，我们可以：
1. 保持`ModelManager`类的结构稳定，不直接修改它
2. 在`lifespan.py`中统一管理所有模型的生命周期
3. 通过单例模式确保自定义引擎只被初始化一次
4. 提供清晰的资源管理和清理机制

### 4.3 IndexTTS-1.5所需依赖

集成IndexTTS-1.5模型需要安装以下额外的依赖项：

```bash
pip install omegaconf tqdm pyyaml

# 可选：安装DeepSpeed以加速推理（GPU环境推荐）
pip install deepspeed
```

**依赖说明：**
- `omegaconf`：用于加载和管理YAML配置文件
- `tqdm`：用于显示进度条
- `pyyaml`：用于解析YAML配置文件
- `deepspeed`（可选）：优化推理性能，特别是在GPU环境下

### 4.4 更新配置文件

#### 4.4.1 添加IndexTTS-1.5配置选项

在`config.py`中添加IndexTTS-1.5的配置选项：

```python
class Config:
    # ...现有配置...
    
    # IndexTTS-1.5引擎配置
    INDEX_TTS_ENABLED = os.getenv("INDEX_TTS_ENABLED", "False").lower() == "true"
    INDEX_TTS_MODEL_PATH = os.getenv("INDEX_TTS_MODEL_PATH", "/mnt/c/models/IndexTTS-1.5")
    INDEX_TTS_DEVICE = os.getenv("INDEX_TTS_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    INDEX_TTS_MAX_WORKERS = int(os.getenv("INDEX_TTS_MAX_WORKERS", "2"))
    INDEX_TTS_TIMEOUT = int(os.getenv("INDEX_TTS_TIMEOUT", "60"))  # 秒
    
    # 可选：指定支持的声音列表
    INDEX_TTS_SUPPORTED_VOICES = ["default", "female", "male"]  # 根据实际支持情况修改
```

## 5. 与LLM模型的并发处理策略

为了避免在LLM模型生成内容时与TTS服务产生并发排队问题，可以采用以下优化策略：

### 5.1 任务队列

为TTS请求建立独立的任务队列，避免与LLM任务竞争资源。任务队列的初始化和管理应该在lifespan.py中进行：

```python
# 在core/tts/task_queue.py中实现任务队列

import asyncio
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class TTSTaskQueue:
    """TTS任务队列管理"""
    def __init__(self):
        self.queue = asyncio.Queue()
        self.workers = []
        self.max_workers = 3  # 根据系统资源调整
    
    async def start(self):
        """启动工作线程"""
        logger.info(f"Starting TTS task queue with {self.max_workers} workers")
        for _ in range(self.max_workers):
            worker = asyncio.create_task(self._worker())
            self.workers.append(worker)
    
    async def _worker(self):
        """工作线程处理任务"""
        while True:
            try:
                task = await self.queue.get()
                try:
                    # 执行TTS生成任务
                    await self._process_task(task)
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
    
    async def _process_task(self, task: Dict[str, Any]):
        """处理单个TTS任务"""
        from core.tts.speech import create_speech
        
        try:
            # 从任务参数中提取需要的信息
            text = task['text']
            voice = task.get('voice')
            output_path = task['output_path']
            # 执行TTS生成
            result = await create_speech(text, voice=voice, output_path=output_path)
            
            # 通知回调（如果有）
            if 'callback' in task:
                callback = task['callback']
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Callback error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to process TTS task: {str(e)}")
    
    async def add_task(self, task: Dict[str, Any]):
        """添加任务到队列"""
        await self.queue.put(task)
    
    async def stop(self):
        """停止所有工作线程"""
        logger.info("Stopping TTS task queue...")
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("TTS task queue stopped")

# 创建全局任务队列实例
tts_task_queue = TTSTaskQueue()
```

在lifespan.py中初始化和管理TTS任务队列：

```python
# 在core/lifespan.py中添加TTS任务队列管理

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    current_port = os.environ.get('CURRENT_PORT', str(Config.PORT))
    load_llm = current_port == str(Config.PORT) and current_port == '8888'
    
    logger.info(f"Initializing - PID: {os.getpid()}, Port: {current_port}, Load LLM: {load_llm}")
    
    # 初始化模型管理器
    await ModelManager.initialize(load_llm=load_llm)
    
    # 初始化自定义TTS引擎（如果启用）
    if Config.MY_TTS_ENABLED:
        try:
            from core.model_manager import initialize_custom_tts_engine
            initialize_custom_tts_engine()
            logger.info("Custom TTS engine initialization completed")
        except Exception as e:
            logger.error(f"Error initializing custom TTS engine: {str(e)}")
    
    # 初始化TTS任务队列
    try:
        from core.tts.task_queue import tts_task_queue
        await tts_task_queue.start()
        logger.info("TTS task queue initialized")
    except Exception as e:
        logger.error(f"Error initializing TTS task queue: {str(e)}")
    
    # 初始化知识库服务
    if Config.KNOWLEDGE_BASE_ENABLED:
        initialize_kb_server_after_model()
        logger.info("KnowledgeBaseServer initialization triggered after ModelManager")
    
    # 其他初始化代码...
    
    yield
    
    # 清理TTS任务队列
    try:
        from core.tts.task_queue import tts_task_queue
        await tts_task_queue.stop()
        logger.info("TTS task queue cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up TTS task queue: {str(e)}")
    
    # 清理自定义TTS引擎资源
    if Config.MY_TTS_ENABLED:
        try:
            from core.tts.my_tts_engine import MyTTSEngine
            MyTTSEngine.cleanup()
            logger.info("Custom TTS engine cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up custom TTS engine: {str(e)}")
    
    # 清理其他资源...
    ModelManager.cleanup()


### 5.2 优先级队列

为了处理不同优先级的TTS任务，可以实现优先级队列：

```python
# 在core/tts/task_queue.py中扩展优先级队列

import heapq
import asyncio
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    LOW = 3
    NORMAL = 2
    HIGH = 1

class TTSPriorityQueue:
    """带优先级的TTS任务队列"""
    def __init__(self):
        self.queue = []
        self.task_counter = 0
        self.max_workers = 3
        self.workers = []
        self._stop_event = asyncio.Event()
    
    async def start(self):
        """启动工作线程"""
        logger.info(f"Starting TTS priority queue with {self.max_workers} workers")
        self._stop_event.clear()
        for _ in range(self.max_workers):
            worker = asyncio.create_task(self._worker())
            self.workers.append(worker)
    
    def add_task(self, task, priority=TaskPriority.NORMAL):
        """添加任务到队列"""
        task_id = self.task_counter
        self.task_counter += 1
        heapq.heappush(self.queue, (priority.value, task_id, task))
        logger.info(f"Added task with priority {priority.name}: {task.get('text', '')[:20]}...")
    
    async def _worker(self):
        """工作线程处理任务"""
        while not self._stop_event.is_set():
            try:
                # 检查队列是否有任务
                if self.queue:
                    # 获取优先级最高的任务
                    _, _, task = heapq.heappop(self.queue)
                    try:
                        await self._process_task(task)
                    except Exception as e:
                        logger.error(f"Error processing task: {str(e)}")
                else:
                    # 队列为空，等待一会儿或直到收到停止信号
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=0.5)
                    except asyncio.TimeoutError:
                        pass  # 继续循环检查队列
            except asyncio.CancelledError:
                break
    
    async def _process_task(self, task):
        """处理任务"""
        from core.tts.speech import create_speech
        
        try:
            text = task['text']
            voice = task.get('voice')
            output_path = task['output_path']
            result = await create_speech(text, voice=voice, output_path=output_path)
            
            if 'callback' in task:
                callback = task['callback']
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Callback error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to process TTS task: {str(e)}")
    
    async def stop(self):
        """停止所有工作线程"""
        logger.info("Stopping TTS priority queue...")
        self._stop_event.set()
        
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("TTS priority queue stopped")

# 创建全局优先级队列实例
tts_priority_queue = TTSPriorityQueue()
```

在lifespan.py中初始化和管理优先级队列：

```python
# 在core/lifespan.py中使用优先级队列

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    # 初始化代码...
    
    # 初始化TTS优先级队列（替换标准队列）
    try:
        from core.tts.task_queue import tts_priority_queue
        await tts_priority_queue.start()
        logger.info("TTS priority queue initialized")
    except Exception as e:
        logger.error(f"Error initializing TTS priority queue: {str(e)}")
    
    # 其他初始化代码...
    
    yield
    
    # 清理TTS优先级队列
    try:
        from core.tts.task_queue import tts_priority_queue
        await tts_priority_queue.stop()
        logger.info("TTS priority queue cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up TTS priority queue: {str(e)}")
    
    # 其他清理代码...


### 5.3 模型实例池

为了提高性能并避免频繁初始化模型，可以实现模型实例池：

```python
# 在core/tts/model_pool.py中实现模型实例池

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

@dataclass
class ModelInstance:
    """模型实例包装器"""
    instance: Any
    last_used: float
    is_available: bool = True

class ModelInstancePool:
    """TTS模型实例池"""
    def __init__(self, model_class, min_instances=2, max_instances=5, max_idle_time=300):
        """初始化模型实例池
        
        Args:
            model_class: 要实例化的模型类
            min_instances: 最小实例数
            max_instances: 最大实例数
            max_idle_time: 最大空闲时间（秒）
        """
        self.model_class = model_class
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.max_idle_time = max_idle_time
        self.instances: List[ModelInstance] = []
        self._lock = asyncio.Lock()
        self._cleanup_task = None
    
    async def initialize(self):
        """初始化模型池"""
        logger.info(f"Initializing model pool with {self.min_instances} instances")
        
        # 创建最小数量的实例
        for _ in range(self.min_instances):
            try:
                instance = await self._create_instance()
                self.instances.append(ModelInstance(instance=instance, last_used=time.time()))
            except Exception as e:
                logger.error(f"Failed to create model instance: {str(e)}")
        
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_idle_instances())
    
    async def _create_instance(self):
        """创建新的模型实例"""
        # 如果是异步初始化的模型
        if hasattr(self.model_class, 'create') and asyncio.iscoroutinefunction(self.model_class.create):
            return await self.model_class.create()
        # 同步初始化的模型
        return self.model_class()
    
    async def get_instance(self):
        """获取可用的模型实例"""
        async with self._lock:
            # 查找可用实例
            for idx, instance_info in enumerate(self.instances):
                if instance_info.is_available:
                    self.instances[idx].is_available = False
                    self.instances[idx].last_used = time.time()
                    logger.debug(f"Reusing model instance {idx}")
                    return instance_info.instance
            
            # 如果没有可用实例且未达到最大实例数，创建新实例
            if len(self.instances) < self.max_instances:
                try:
                    instance = await self._create_instance()
                    instance_info = ModelInstance(instance=instance, last_used=time.time(), is_available=False)
                    self.instances.append(instance_info)
                    logger.info(f"Created new model instance, total: {len(self.instances)}")
                    return instance
                except Exception as e:
                    logger.error(f"Failed to create new model instance: {str(e)}")
            
            # 所有实例都在使用中，返回None（或者可以实现等待机制）
            logger.warning("No model instances available")
            return None
    
    async def release_instance(self, instance):
        """释放模型实例回池"""
        async with self._lock:
            for idx, instance_info in enumerate(self.instances):
                if instance_info.instance is instance:
                    self.instances[idx].is_available = True
                    self.instances[idx].last_used = time.time()
                    logger.debug(f"Released model instance {idx}")
                    break
    
    async def _cleanup_idle_instances(self):
        """清理空闲时间过长的实例"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                current_time = time.time()
                
                async with self._lock:
                    # 保留最小数量的实例
                    instances_to_keep = max(self.min_instances, len([i for i in self.instances if not i.is_available]))
                    
                    # 按最后使用时间排序
                    sorted_instances = sorted(self.instances, key=lambda x: x.last_used)
                    
                    # 清理空闲实例，保留必要的数量
                    instances_to_remove = []
                    for idx, instance_info in enumerate(sorted_instances):
                        if (instance_info.is_available and 
                            current_time - instance_info.last_used > self.max_idle_time and 
                            len(self.instances) - len(instances_to_remove) > instances_to_keep):
                            instances_to_remove.append(idx)
                    
                    # 从原始列表中删除这些实例
                    for idx in sorted(instances_to_remove, reverse=True):
                        instance_to_remove = self.instances[idx]
                        # 执行清理操作
                        if hasattr(instance_to_remove.instance, 'cleanup'):
                            instance_to_remove.instance.cleanup()
                        self.instances.pop(idx)
                        logger.info(f"Removed idle model instance, total remaining: {len(self.instances)}")
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
    
    async def shutdown(self):
        """关闭模型池并清理所有实例"""
        logger.info("Shutting down model pool")
        
        # 停止清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 清理所有实例
        for instance_info in self.instances:
            if hasattr(instance_info.instance, 'cleanup'):
                instance_info.instance.cleanup()
        
        self.instances.clear()
```

在lifespan.py中初始化和管理模型实例池：

```python
# 在core/lifespan.py中添加模型实例池管理

# 全局模型池实例
from core.tts.model_pool import ModelInstancePool
from core.tts.my_tts_engine import MyTTSEngine

tts_model_pool = None

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    global tts_model_pool
    
    # 初始化代码...
    
    # 初始化自定义TTS引擎的模型实例池（如果启用）
    if Config.MY_TTS_ENABLED:
        try:
            tts_model_pool = ModelInstancePool(
                model_class=MyTTSEngine,
                min_instances=2,
                max_instances=5,
                max_idle_time=300
            )
            await tts_model_pool.initialize()
            logger.info("TTS model pool initialized")
        except Exception as e:
            logger.error(f"Error initializing TTS model pool: {str(e)}")
    
    # 其他初始化代码...
    
    yield
    
    # 清理模型实例池
    if tts_model_pool:
        try:
            await tts_model_pool.shutdown()
            logger.info("TTS model pool cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up TTS model pool: {str(e)}")
    
    # 其他清理代码...
```

### 5.4 资源隔离与优化策略

除了上述方法外，还可以采用以下策略优化与LLM模型的并发处理：

#### 5.4.1 资源限制隔离

为TTS服务和LLM服务设置不同的资源限制，避免互相抢占：

```python
# 在config.py中添加资源限制配置

class Config:
    # 现有配置...
    
    # TTS资源配置
    TTS_MAX_WORKERS = 3
    TTS_CONNECTION_TIMEOUT = 30
    TTS_MAX_RETRY = 2
    
    # LLM资源配置
    LLM_MAX_CONCURRENT_REQUESTS = 4
    LLM_MAX_TOKEN_PER_REQUEST = 4096
    
    # 资源隔离配置
    TTS_CPU_AFFINITY = [0, 1]  # 限制TTS使用CPU核心0和1
    LLM_CPU_AFFINITY = [2, 3]  # 限制LLM使用CPU核心2和3
```

#### 5.4.2 异步API调用优化

优化外部API调用，减少阻塞时间：

```python
# 在core/tts/speech.py中优化API调用

import asyncio
import aiohttp
from typing import Optional

# 创建全局连接池
connector = aiohttp.TCPConnector(
    limit=Config.TTS_MAX_WORKERS,
    keepalive_timeout=60,
    ttl_dns_cache=300
)
http_client = aiohttp.ClientSession(connector=connector)

async def create_speech(text: str, voice: Optional[str] = None, output_path: Optional[str] = None):
    # ... 现有代码 ...
    
    # 使用连接池优化API调用
    async def communicate_with_retry(text, voice, max_retries=Config.TTS_MAX_RETRY):
        for attempt in range(max_retries + 1):
            try:
                # 实现带超时的异步API调用
                return await asyncio.wait_for(
                    communicate_with_edgetts(text, voice),
                    timeout=Config.TTS_CONNECTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.warning(f"API call timeout, attempt {attempt+1}/{max_retries+1}")
                if attempt == max_retries:
                    raise
                await asyncio.sleep(2 ** attempt)  # 指数退避
    
    # ... 调用优化后的函数 ...
```

在lifespan.py中管理HTTP客户端生命周期：

```python
# 在core/lifespan.py中管理HTTP客户端生命周期

from core.tts.speech import http_client

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    # 初始化代码...
    
    yield
    
    # 关闭HTTP客户端
    try:
        await http_client.close()
        logger.info("HTTP client closed")
    except Exception as e:
        logger.error(f"Error closing HTTP client: {str(e)}")
    
    # 其他清理代码...
```

#### 5.4.3 负载均衡与熔断机制

实现简单的负载均衡和熔断机制，保护系统在高负载下的稳定性：

```python
# 在core/tts/circuit_breaker.py中实现熔断机制

import time
import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """熔断断路器模式实现"""
    
    def __init__(self, 
                 failure_threshold=5,
                 recovery_timeout=30,
                 half_open_max_calls=2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failures = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self.state = "CLOSED"
        self._lock = asyncio.Lock()
    
    async def execute(self, func: Callable, *args, **kwargs):
        """在断路器保护下执行函数"""
        if await self._should_allow_execution():
            try:
                result = await func(*args, **kwargs)
                await self._record_success()
                return result
            except Exception as e:
                await self._record_failure()
                raise
        else:
            raise Exception("Circuit breaker is OPEN")
    
    async def _should_allow_execution(self):
        """判断是否允许执行"""
        async with self._lock:
            if self.state == "OPEN":
                # 检查是否可以进入半开状态
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    self.half_open_calls = 0
                    logger.info("Circuit breaker switched to HALF_OPEN")
                else:
                    return False
            elif self.state == "HALF_OPEN":
                # 半开状态下限制调用次数
                if self.half_open_calls >= self.half_open_max_calls:
                    return False
                self.half_open_calls += 1
            return True
    
    async def _record_success(self):
        """记录成功执行"""
        async with self._lock:
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
                logger.info("Circuit breaker switched to CLOSED")
    
    async def _record_failure(self):
        """记录执行失败"""
        async with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.state == "HALF_OPEN":
                self.state = "OPEN"
                logger.info("Circuit breaker switched to OPEN")
            elif self.state == "CLOSED" and self.failures >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failures} failures")
```

在speech.py中使用熔断机制：

```python
# 在core/tts/speech.py中使用熔断机制

from core.tts.circuit_breaker import CircuitBreaker

# 创建全局熔断器实例
tts_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

async def create_speech(text: str, voice: Optional[str] = None, output_path: Optional[str] = None):
    # ... 现有代码 ...
    
    try:
        # 使用熔断器调用TTS服务
        result = await tts_circuit_breaker.execute(
            communicate_with_edgetts,
            text, voice, output_path
        )
        return result
    except Exception as e:
        # 处理异常，可能是熔断触发或其他错误
        logger.error(f"TTS generation failed: {str(e)}")
        raise
### 5.5 负载均衡与模型实例分发
```

对于计算密集型的TTS模型，可以创建多个模型实例，使用轮询或负载均衡方式分发请求：

```python
# 在core/tts/load_balancer.py中实现简单的负载均衡

import asyncio
import logging
from typing import List, Dict, Any, Callable
import random
import time

logger = logging.getLogger(__name__)

class TTSServerLoadBalancer:
    """TTS服务器负载均衡器"""
    
    def __init__(self):
        self.servers = []  # 服务器列表 [{'url': 'http://server1', 'active': True, 'weight': 1, 'last_used': 0}]
        self.health_check_interval = 30  # 健康检查间隔（秒）
        self.health_check_task = None
    
    async def initialize(self, server_configs: List[Dict[str, Any]]):
        """初始化负载均衡器
        
        Args:
            server_configs: 服务器配置列表
        """
        for config in server_configs:
            self.servers.append({
                'url': config.get('url'),
                'active': True,
                'weight': config.get('weight', 1),
                'last_used': 0
            })
        
        # 启动健康检查任务
        self.health_check_task = asyncio.create_task(self._health_check())
        logger.info(f"Initialized load balancer with {len(self.servers)} servers")
    
    async def get_server(self):
        """获取一个服务器（基于权重的轮询）"""
        # 过滤出活跃的服务器
        active_servers = [s for s in self.servers if s['active']]
        
        if not active_servers:
            logger.error("No active servers available")
            return None
        
        # 基于权重选择服务器
        total_weight = sum(s['weight'] for s in active_servers)
        random_value = random.uniform(0, total_weight)
        current_weight = 0
        
        for server in active_servers:
            current_weight += server['weight']
            if random_value <= current_weight:
                # 更新最后使用时间
                server['last_used'] = time.time()
                return server['url']
        
        # 兜底返回第一个服务器
        active_servers[0]['last_used'] = time.time()
        return active_servers[0]['url']
    
    async def _health_check(self):
        """健康检查任务"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                for server in self.servers:
                    # 执行健康检查
                    is_healthy = await self._check_server_health(server['url'])
                    
                    # 更新服务器状态
                    if server['active'] != is_healthy:
                        server['active'] = is_healthy
                        status = "healthy" if is_healthy else "unhealthy"
                        logger.info(f"Server {server['url']} is now {status}")
            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
    
    async def _check_server_health(self, url: str) -> bool:
        """检查单个服务器的健康状态"""
        try:
            # 实现健康检查逻辑
            # 例如：发送一个简单的HTTP请求到健康检查端点
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/health", timeout=5) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Health check for {url} failed: {str(e)}")
            return False
    
    async def shutdown(self):
        """关闭负载均衡器"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Load balancer shutdown completed")
```

在lifespan.py中初始化和管理负载均衡器：

```python
# 在core/lifespan.py中添加负载均衡器管理

from core.tts.load_balancer import TTSServerLoadBalancer

tts_load_balancer = None

async def lifespan(app: FastAPI):
    """模型生命周期管理"""
    global tts_load_balancer
    
    # 初始化代码...
    
    # 初始化负载均衡器（如果配置了多服务器）
    if Config.USE_TTS_LOAD_BALANCER:
        try:
            tts_load_balancer = TTSServerLoadBalancer()
            server_configs = Config.TTS_SERVERS  # 从配置中获取服务器列表
            await tts_load_balancer.initialize(server_configs)
            logger.info("TTS load balancer initialized")
        except Exception as e:
            logger.error(f"Error initializing TTS load balancer: {str(e)}")
    
    # 其他初始化代码...
    
    yield
    
    # 清理负载均衡器
    if tts_load_balancer:
        try:
            await tts_load_balancer.shutdown()
            logger.info("TTS load balancer cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up TTS load balancer: {str(e)}")
    
    # 其他清理代码...
```

## 6. 总结

### 6.1 实现要点

1. **EdgeTTS核心实现**：通过Communicate类与EdgeTTS API交互，处理文本转语音生成
2. **文本分块策略**：建议在客户端进行预处理，避免API请求长度限制
3. **响应处理**：使用file_response_with_cleanup自动返回和清理音频文件
4. **IndexTTS-1.5集成**：实现了本地IndexTTS-1.5模型的完整集成，包括：
   - 自定义引擎类实现（支持单例模式）
   - 生命周期管理（在lifespan.py中初始化和清理）
   - 线程池异步调用（避免阻塞事件循环）
   - 配置驱动的模型路径和设备选择
5. **并发处理优化**：
   - 使用任务队列隔离TTS和LLM请求
   - 通过优先级队列处理不同重要性的任务
   - 实现模型实例池减少初始化开销
   - 配置资源隔离避免服务间竞争
   - 使用熔断机制和负载均衡提高稳定性

### 6.2 最佳实践建议

1. **资源管理**：
   - 所有资源初始化和清理都应在lifespan.py中进行
   - 对本地IndexTTS-1.5模型使用单例模式避免重复加载
   - 实现完整的资源释放逻辑，防止内存泄漏
2. **异常处理**：
   - 实现全面的异常捕获和日志记录
   - 为IndexTTS-1.5添加模型初始化和推理异常的专门处理
   - 支持从本地模型自动降级到云服务（EdgeTTS）
3. **性能优化**：
   - 使用异步API调用和线程池处理同步模型
   - 实现连接池和重试机制
   - 为IndexTTS-1.5添加专门的文本预处理优化
   - 监控本地模型的内存使用和推理时间
   - 设置合理的超时和并发限制
4. **扩展性设计**：
   - 通过配置驱动的方式切换不同的TTS引擎
   - 实现统一的接口抽象，便于集成更多引擎
   - 支持多服务器部署和负载均衡
5. **本地模型优化**：
   - 合理选择设备（CPU/GPU）以平衡性能和资源使用
   - 实现模型加载状态检查和自动恢复机制
   - 针对IndexTTS-1.5的特性优化文本处理和推理过程
通过以上实现和优化，可以构建一个高性能、可靠的TTS服务，有效规避与LLM模型的并发排队问题，同时保持代码的可维护性和扩展性。

## 7. 输入输出示例

### 7.1 输入示例

#### 7.1.1 EdgeTTS输入示例

```bash
# 使用curl调用TTS API
curl -X POST http://localhost:8888/v1/audio/speech \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "这是一段测试文本，用于演示TTS功能。", "voice": "zh-CN-XiaoyiNeural"}' \
  -o output.mp3
```

#### 7.1.2 IndexTTS-1.5输入示例

使用本地IndexTTS-1.5模型生成语音（需要先设置环境变量INDEX_TTS_ENABLED=true）：

```bash
# 使用IndexTTS-1.5默认声音
curl -X POST http://localhost:8888/v1/audio/speech \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "这是使用IndexTTS-1.5生成的语音示例。", "voice": "default"}' \
  -o output_indextts.mp3

# 使用IndexTTS-1.5女性声音
curl -X POST http://localhost:8888/v1/audio/speech \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "这是使用女性声音生成的语音。", "voice": "female"}' \
  -o output_female.mp3
```

### 7.2 输出示例

调用成功后，将生成一个名为`output.mp3`的音频文件，包含转换后的语音。

API响应头示例：

```
HTTP/1.1 200 OK
content-length: 12345
content-type: audio/mpeg
```

## 7. 代码优化建议

### 7.1 文本预处理优化

#### 7.1.1 通用文本预处理

当前的文本预处理较为简单，可以增加更完善的文本规范化处理：

```python
def normalize_text(text: str) -> str:
    """规范化文本以获得更好的TTS效果"""
    # 处理数字（转为中文数字或保留阿拉伯数字）
    # 处理特殊符号（如网址、邮箱等）
    # 处理标点符号（确保适当的停顿）
    # 处理多音字和生僻字
    return processed_text

# 在create_speech函数中使用
text = filter_special_chars(text)
text = normalize_text(text)  # 添加规范化步骤
```

#### 7.1.2 IndexTTS-1.5专用文本预处理

对于本地IndexTTS-1.5模型，建议添加专门的文本预处理优化：

```python
def preprocess_index_tts_text(text: str) -> str:
    """为IndexTTS-1.5模型优化的文本预处理
    
    Args:
        text: 原始文本
        
    Returns:
        str: 优化后的文本
    """
    # 移除多余空格和换行
    text = ' '.join(text.split())
    
    # 确保句子有适当的停顿标记
    if not text.endswith(('.', '!', '?', '。', '！', '？')):
        text += '。'
    
    # 处理标点符号，确保适当的停顿
    text = text.replace('，', '， ').replace('。', '。 ')
    
    # 处理数字和特殊符号（根据IndexTTS-1.5的特点优化）
    # ...
    
    return text

# 在使用IndexTTS-1.5时应用
if Config.INDEX_TTS_ENABLED:
    text = preprocess_index_tts_text(text)
```

### 7.2 错误处理增强

增强错误处理机制，提供更详细的错误信息和恢复策略：

```python
async def create_speech(request: Request, authorization: str = Header(None)):
    try:
        # ...现有代码...
    except ConnectionError as e:
        logger.error(f"TTS service connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="TTS service unavailable")
    except TimeoutError as e:
        logger.error(f"TTS service timeout: {str(e)}")
        raise HTTPException(status_code=504, detail="TTS service timeout")
    except ValueError as e:
        logger.error(f"Invalid TTS input: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected TTS error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal TTS service error")
```

### 7.3 性能监控

#### 7.3.1 通用性能监控

添加性能监控指标，跟踪TTS请求的处理时间、成功率等：

```python
from prometheus_client import Counter, Histogram

# 定义指标
tts_requests_total = Counter('tts_requests_total', 'Total TTS requests')
tts_requests_failed = Counter('tts_requests_failed', 'Failed TTS requests')
tts_request_duration = Histogram('tts_request_duration_seconds', 'TTS request duration in seconds')

async def create_speech(request: Request, authorization: str = Header(None)):
    tts_requests_total.inc()
    start_time = time.time()
    
    try:
        # ...处理逻辑...
        tts_request_duration.observe(time.time() - start_time)
        return response
    except Exception as e:
        tts_requests_failed.inc()
        tts_request_duration.observe(time.time() - start_time)
        raise
```

#### 7.3.2 IndexTTS-1.5专用性能监控

为本地IndexTTS-1.5模型添加专门的性能监控，记录资源使用情况：

```python
import time
import psutil

# IndexTTS专用指标
index_tts_requests_total = Counter('index_tts_requests_total', 'Total IndexTTS requests')
index_tts_requests_failed = Counter('index_tts_requests_failed', 'Failed IndexTTS requests')
index_tts_memory_usage = Histogram('index_tts_memory_usage_mb', 'IndexTTS memory usage in MB')

# 在IndexTTSEngine类中添加性能监控
def generate_speech(self, text, output_path, voice=None):
    process = psutil.Process()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    start_time = time.time()
    
    try:
        # 原有生成逻辑
        # ...
        
        # 记录性能指标
        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_diff = end_memory - start_memory
        
        index_tts_memory_usage.observe(memory_diff)
        logger.info(
            f"IndexTTS-1.5 performance: "
            f"time={end_time-start_time:.2f}s, "
            f"memory={memory_diff:.2f}MB, "
            f"text_length={len(text)}"
        )
        
        return True
    except Exception as e:
        # 异常处理
        # ...
        return False
```

通过以上优化和集成方法，可以有效扩展ANY4ANY项目的TTS功能，同时提高系统的并发处理能力和稳定性。