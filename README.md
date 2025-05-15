# any4any: 语音识别、文本转语音、文档重排和数据库连接的一键式API服务

<div align="center">
  中文简体 ·
  <a href="./README_EN.md">English</a>
</div>

## 目的

- 快速、便捷地部署语音识别模型（ASR）、文本转语音模型（TTS）和重排序模型（Rerank）供Dify等应用调用
- 避免Xinference等框架、应用及依赖库的安装，降低部署难度
- 使用开源模型edge-tts模型提升文字转语音速度
- 使用开源模型SenseVoice模型提升语音识别准确度
- 使用开源模型bge-reranker-base实现知识库检索的重排序
- 提供MySQL数据库API，可进行数据库连接并执行SQL查询和更新操作

## 功能特性

- 语音转录：将音频文件转换为文本。
- 文本转语音：将文本转换为语音文件（支持多种语音风格）：默认使用`zh-CN-XiaoyiNeural`音色。
- 文档重排：基于查询对文档进行相关性排序。
- MySQL数据库API：数据库连接并执行SQL查询和更新操作。
- 自动清理：生成的临时音频文件会在响应后自动删除。
- API文档：自动生成API使用说明，可通过浏览器访问：http://localhost:8888/docs#/

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

## 前置环境要求

- wsl2 (Windows Subsystem for Linux)：windows系统下的必要条件。
- Conda (Anaconda or Miniconda)：用于管理Python环境。
- Docker-desktop：windows系统下的Docker桌面应用，用于运行dify服务。

## 安装指南

### 1.克隆本项目

```bash
git clone https://github.com/AnyForAny.git
# 或
git clone https://gitee.com/AnyForAny.git
```

### 2.下载模型

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

### 2. 创建conda环境

```bash
# 创建conda环境
conda create -n any4any python=3.10
# 激活环境
conda activate any4any
```

3. 安装依赖

```bash
# 安装ffmpeg
sudo apt-get install ffmpeg
# 验证ffmpeg是否安装成功
ffmpeg -version
# 安装其他依赖
pip install -r requirements.txt
```

4. 启动服务

```bash
python app.py
# 或
uvicorn app:app --host 0.0.0.0 --port 8888
```
服务将运行在: http://localhost:8888

### 5. dify内添加并调用模型

**5.1查看宿主机的ip地址**

在linux命令行中执行`ifconfig`命令，查看宿主机的ip地址。
```bash
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.21.56.14  netmask 255.255.240.0  broadcast 172.21.63.255
```
其中`inet 172.21.56.14`即为宿主机的ip地址。

**5.2导入TTS模型**

启动Docker并保证dify服务正常运行。
将插件`langgenius-openai_api_compatible_0.0.16.difypkg`导入并安装至dify中。
打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：TTS
模型名称：edge-tts
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
API Key：EMPTY
可用声音（用英文逗号分隔）：zh-CN-XiaoyiNeural
其他可空余不填
```

**5.3导入ASR模型**

同样打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：Speech2text
模型名称：SenseVoiceSmall
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```
**5.4导入ASR模型**

同样打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：rerank
模型名称：bge-reranker-base
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```

**5.5设置为默认模型**

在右上角`系统模型设置`中的最下方，将`文本转语音模型`设置为`edge-tts`，将`语音识别模型`设置为`SenseVoiceSmall`，将`文档重排模型`设置为`bge-reranker-base`，点击，保存设置。

**5.6使用模型**

添加任意一个`chatflow`，进入工作流内容后在右上角`功能`，找到`文字转语音`和`语音转文字`功能，配置我们添加好的模型，将`自动播放`打开，然后对话即可。

### 6. dify中连接MySQL数据库

在`config.py`中配置MySQL数据库连接信息，启动服务后，即可使用MySQL数据库API。

在dify中的`workflow`或`chatflow`中添加`http请求节点`，配置信息如下：
```
请求方式：POST
请求地址：http://localhost:8888/v1/db/query
form-data参数名：query
form-data参数值：SELECT * FROM users LIMIT 1
```

## 配置说明

在`config.py`中修改以下配置：

```python
import os
import torch
class Config:
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8888
    
    # 认证配置
    API_KEY = "EMPTY"           # 替换为你的实际API密钥
    
    # 模型配置
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"       # 替换为你本地ASR模型路径
    RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"  # 替换为你本地rerank模型路径

    # MySQL数据库配置
    MYSQL_HOST = "172.21.48.1"  # 替换为你的实际的IP地址 可以使用ipconfig | findstr "IPv4" 查看
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "root"
    MYSQL_DATABASE = "any4any"  # 替换为你的数据库名称

    # 功能开关配置
    NO_THINK = True             # 是否开启nothink
    QUERY_CLEANING = True       # 是否开启SQL查询清洗功能
    PROMPT = ""                 # 自定义提示词
    
    # 确保模型目录存在
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)
```

## API使用示例

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

### 连接MySQL数据库
支持两种请求格式：
1. application/json
2. multipart/form-data
**安全警告**：当前实现未使用参数化查询，存在SQL注入风险

**JSON格式请求**:
```bash
curl -X POST "http://localhost:8888/v1/db/query" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer YOUR_API_KEY" \
-d '{"query":"SELECT * FROM users LIMIT 1"}'
```

**form-data格式请求**:
```bash
curl -X POST "http://localhost:8888/v1/db/query" \
-H "Authorization: Bearer YOUR_API_KEY" \
-F "query=SELECT * FROM users LIMIT 1"
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
- fastapi：https://github.com/fastapi/fastapi

## 更新计划
- 增加更多TTS和ASR模型的支持
- 构建前端界面，提供更友好的用户体验
- 增加其他接口和服务

## 联系我们
- 官方网站：https://eogee.com
- 邮箱：eogee@qq.com
- B站：https://space.bilibili.com/315734619
- 抖音：[抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC)，每晚8点直播