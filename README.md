# ANY FOR ANY

## 目的
- 快速、便捷地部署语音识别模型（ASR）、文本转语音模型（TTS）和重排序模型（Rerank）供Dify等其他应用调用。
- 避免Xinference等框架应用及依赖库的安装，降低部署难度。
- 使用开源模型edge-tts模型提升文字转语音速度。
- 使用开源模型SenseVoice模型提升语音识别准确度。
- 使用开源模型bge-reranker-base实现知识库检索的重排序。

## 功能特性

- 语音转录：将音频文件转换为文本
- 文本转语音：将文本转换为语音文件（支持多种语音风格）：默认使用`zh-CN-XiaoyiNeural`音色
- 文档重排：基于查询对文档进行相关性排序
- 自动清理：生成的临时音频文件会在响应后自动删除
- API文档：自动生成API使用说明，可通过浏览器访问http://localhost:8888/docs#/

## 项目结构

```
├── api_models.py          # API数据模型和配置
├── app.py                 # FastAPI主应用
├── config.py              # 配置文件
├── core_services.py       # 核心工具类
├── langgenius-openai_api_compatible_0.0.16.difypkg
├                          # Dify插件，用于导入模型   
├── services.py            # 业务逻辑实现
├── model.py               # 语音转录模型实现（源自SenseVoiceSmall项目）
├── requirements.txt       # 依赖列表
├── README.md              # 项目文档
└── utils/                 # 工具模块（源自SenseVoiceSmall项目）
    ├── ctc_alignment.py
    ├── export_utils.py
    └── ...
```
## 前置环境
- wsl2 (Windows Subsystem for Linux):windows系统下的必要条件。
- Conda (Anaconda or Miniconda)：用于管理Python环境。
- Docker-desktop：windows系统下的Docker桌面应用，用于运行dify服务。

## 安装指南

1. 克隆本项目
```bash
git clone https://github.com/AnyForAny.git
# 或
git clone https://gitee.com/AnyForAny.git
```
2. 下载模型
```bash
# 确认已安装git-lfs (https://git-lfs.com)，用于下载大文件
git lfs install

# 下载语音识别模型：SenseVoiceSmall
git clone https://hf-mirror.com/FunAudioLLM/SenseVoiceSmall
# 或
git clone https://hugginface.co/FunAudioLLM/SenseVoiceSmall

# 下载重排序模型：bge-reranker-base
git clone https://hf-mirror.com/BAAI/bge-reranker-base
# 或
git clone https://hugginface.co/BAAI/bge-reranker-base
```

2. 创建conda环境
```bash
# 创建conda环境
conda create -n any4any python=3.10
# 激活环境
conda activate any4any
```

3. 安装依赖

安装具体依赖前，确认在wsl中安装了`ffmpeg`。
```bash
# 安装ffmpeg
sudo apt-get install ffmpeg
# 验证ffmpeg是否安装成功
ffmpeg -version
```
在本项目根目录下执行以下命令安装依赖：
```bash
pip install -r requirements.txt
```

4. 启动服务
```bash
python app.py
# 或
uvicorn app:app --host 0.0.0.0 --port 8888
```
服务将运行在: http://localhost:8888

## 配置说明

在`config.py`中修改以下配置：

```python
class Config:
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8888
    
    # 认证配置
    API_KEY = "EMPTY"  # 替换为你的实际API密钥
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"  # 本地ASR模型路径
    RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"  # 本地rerank模型路径

    # 是否开启nothink，目前仅有qwen3系列LLM模型支持
    NO_THINK = True

    # 提示词
    PROMPT = "" # 自定义提示词，会在语音转文字识别结果后面显示，建议使用中文，留空则无内容
```

## 使用示例

### 语音转录
```bash
curl -X POST "http://localhost:8888/v1/audio/transcriptions" \
-H "Authorization: Bearer EMPTY" \
-F "file=@audio.wav" \
-F "model=whisper-1" \
-F "language=zh"
```

### 文本转语音
```bash
curl -X POST "http://localhost:8888/v1/audio/speech" \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{"input": "Hello,any4any!", "voice": "zh-CN-XiaoyiNeural"}' \
-o "output.mp3"
```

### 文档重排
```bash
curl -X POST "http://localhost:8888/v1/rerank" \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{"query": "你好，any4any！", "documents": ["hello,any4any!", "any4any!", "heello,world!"]}' \
-o "output.json"
```

### 健康检查
```bash
curl http://localhost:8888/health
```

## 相关开源项目

- edge-tts：https://github.com/rany2/edge-tts
- SenseVoice：https://github.com/FunAudioLLM/SenseVoice
- bge-reranker-base：https://hf-mirror.com/BAAI/bge-reranker-base
- dify：https://github.com/langgenius/dify

## 更新计划
- 增加更多TTS和ASR模型的支持
- 构建前端界面，提供更友好的用户体验
- 增加其他接口和服务

## 联系我们
- 官方网站：https://eogee.com
- 邮箱：eogee@qq.com
- B站：https://space.bilibili.com/315734619
- 抖音：[抖音主页](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC)，每晚8点直播