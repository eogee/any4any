# any4any: 大模型会话、对话内容预览与修改、语音识别、文本转语音、文档重排、文本嵌入、知识库系统和MCP服务的一键式API服务

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/eogee/any4any)

<div align="center">
  中文简体 ·
  <a href="docs/README_EN.md">English</a>
</div>

## 功能特性

**核心功能**：启动运行本项目后，您可以将几乎所有类型模型以openai-api兼容接口形式暴露，可被任何模型管理应用添加，可追踪用户对话历史，具体功能模块介绍如下：

- 会话管理：支持多平台与LLM会话管理，可将本地模型以openai-api兼容接口形式暴露，可被任何模型管理应用添加，可追踪用户对话历史
- 预览模式：支持LLM响应内容预览和编辑功能
- 钉钉机器人：支持钉钉机器人消息处理
- 语音转录：将音频文件转换为文本（支持多种语言）
- 文本转语音：将文本转换为语音文件，支持edge-tts和IndexTTS-1.5引擎，提供多种语音风格
- **智能SQL查询**：自然语言到SQL转换，用户可用中文直接查询数据库，系统自动生成并执行SQL语句
- 知识库：提供独立的embedding和rerank能力，可基于ChromaDB向量数据库构建知识库系统
- MCP服务：支持构建MCP工具、接口，可在任意MCP客户端调用
- API文档：自动生成API使用说明，可通过浏览器访问：http://localhost:8888/docs#/

## 更新内容

**2025.10.24(V0.1.2)：新增智能SQL查询和IndexTTS-1.5支持**

新增：
- **NL2SQL智能查询系统**：基于LLM的自然语言到SQL转换功能
  - 支持用户用中文直接提问，系统自动识别SQL查询需求
  - 智能获取相关数据库表结构信息
  - LLM基于表结构生成准确的SQL查询语句
  - 安全的SQL执行环境，仅允许SELECT查询确保数据库安全
  - 智能格式化查询结果并生成自然语言回答
  - 完整的6步工作流程：问题识别→表结构获取→SQL生成→查询执行→结果格式化→回答生成
  - [NL2SQL智能查询系统说明文档](./docs/zh/NL2SQL智能查询系统说明文档.md)

- **IndexTTS-1.5语音引擎支持**：新增高质量的本地TTS引擎
  - 支持IndexTTS-1.5模型，提供更自然的语音合成效果
  - 多种音色和语音风格选择
  - 与edge-tts引擎并存，用户可选择不同的TTS引擎
  - 优化的音频生成和处理流程
  - [TTS实现与集成说明文档.md](./docs/zh/TTS实现与集成说明文档.md)

**2025.10.08(V0.1.1)：新增嵌入模型（Embedding）模块**

新增：
- Embedding模块：完整的嵌入模型支持，包括文档处理、向量存储、检索引擎等功能
- 文档处理：支持文档解析、分块、向量化等处理流程
- 向量存储：高效的向量存储和管理机制
- 检索引擎：基于相似度的文档检索功能
- 知识库服务器：提供知识库的创建、管理和查询服务
- OpenAI API兼容接口：支持与OpenAI嵌入API一致的调用方式
- [知识库系统说明文档.md](./docs/zh/知识库系统说明文档.md)

**2025.9.26(V0.1.0)：新增会话管理和预览模式功能**

新增：
- 会话管理：支持多平台会话管理，可追踪用户对话历史，实现上下文连续对话
- 预览模式：支持内容预览和编辑功能，用户可在内容生成后进行预览和修改，浏览器访问：http://localhost:8888/index/ 可进行预览
- 钉钉机器人集成：支持钉钉机器人消息处理，可在钉钉中与系统交互
- 用户认证增强：增加了基于API密钥的认证机制，提高系统安全性
- 数据库会话存储：将会话数据存储到MySQL数据库，支持持久化和查询
- [会话管理系统说明文档.md](./docs/zh/会话管理系统说明文档.md)

更新：
- 重塑了项目结构，新增data_models模块用于管理数据模型，新增servers模块用于管理服务，新增static目录用于管理静态文件

## 前置环境要求

- WSL2 (Windows Subsystem for Linux)：Windows系统下的必要条件
- Conda (Anaconda or Miniconda)：用于管理Python环境
- Docker-desktop：Windows系统下的Docker桌面应用，用于运行dify服务
- MySQL：用于存储会话数据

## 安装指南

### 1.克隆本项目

```bash
git clone https://github.com/eogee/any4any.git
# 或
git clone https://gitee.com/eogee/any4any.git
# 或
git clone https://gitcode.com/eogee/any4any.git
```

你也可以通过网盘下载本项目：https://pan.quark.cn/s/fbe126d5bd75

### 2.下载模型

推荐前往网盘一站式获取所有模型：https://pan.quark.cn/s/c65799f2cb93

```bash
# 确认已安装git-lfs (https://git-lfs.com)，用于下载大文件
# 您可在huggingface.co/modelscoup.com/hf-mirror.com站点中下载模型，此处以huggingface.co为例
git lfs install

# 下载语音识别模型：SenseVoiceSmall
git clone https://huggingface.co/FunAudioLLM/SenseVoiceSmall

# 下载重排序模型：bge-reranker-base
git clone https://huggingface.co/BAAI/bge-reranker-base

# 下载LLM模型：Qwen3-1.7B
git clone https://huggingface.co/Qwen/Qwen3-1.7B

# 下载Embedding模型：bge-small-zh-v1.5
git clone https://huggingface.co/BAAI/bge-small-zh-v1.5

# 下载IndexTTS-1.5模型
https://hf-mirror.com/IndexTeam/IndexTTS-1.5
```

### 3. 创建conda环境

```bash
# 创建conda环境
conda create -n any4any python=3.10
# 激活环境
conda activate any4any
```

### 4. 安装依赖

```bash
# 安装ffmpeg
sudo apt-get install ffmpeg
# 验证ffmpeg是否安装成功
ffmpeg -version
# 安装其他依赖
pip install -r requirements.txt
```

### 5. 配置环境变量

复制示例配置文件并根据需要修改：

```bash
cp .env.example .env
```

编辑`.env`文件，配置以下内容：
- 数据库连接信息（包括SQL数据库配置用于NL2SQL功能）
- 模型路径（包括IndexTTS-1.5模型路径）
- API密钥
- 工具系统配置（启用NL2SQL智能查询功能）
- 其他自定义配置

**重要配置项**：
```bash
# 数据库配置（NL2SQL功能需要）
SQL_DB_TYPE=mysql
SQL_DB_HOST=localhost
SQL_DB_PORT=3306
SQL_DB_USERNAME=root
SQL_DB_PASSWORD=root
SQL_DB_DATABASE=your_database_name

# IndexTTS-1.5模型配置（可选）
TTS_MODEL_DIR=/path/to/Index-1.5-Voice

# 工具系统配置
TOOLS_ENABLED=true
TOOLS_DEBUG=false
TOOLS_TIMEOUT=30
```

### 6. 启动服务

```bash
# 直接启动服务
python cli.py

# 或使用快捷命令(WSL/Linux环境),永久安装a4a-run命令:
sudo cp a4a-run.sh /usr/local/bin/a4a-run
sudo chmod +x /usr/local/bin/a4a-run
# 安装后可直接使用:
a4a-run
```

服务将运行在以下端口：
- 主服务: http://localhost:8888
- MCP服务: http://localhost:9999
- 钉钉服务: http://localhost:6666

### 7. 其他模型平台应用内容添加并调用模型（此处以Dify为例）

**7.1查看宿主机的ip地址**

在wsl命令行中执行`ifconfig`命令，查看宿主机的ip地址。
```bash
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.21.56.14  netmask 255.255.240.0  broadcast 172.21.63.255
```
其中`172.21.56.14`即为宿主机的ip地址。

**7.2导入TTS模型**

启动Docker并保证dify服务正常运行。
将插件`langgenius-openai_api_compatible_0.0.16.difypkg`导入并安装至dify中。

**edge-tts引擎配置**：
打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：TTS
模型名称：edge-tts
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
API Key：EMPTY
可用声音（用英文逗号分隔）：zh-CN-XiaoyiNeural
其他可空余不填
```

**IndexTTS-1.5引擎配置**（如果下载了IndexTTS-1.5模型）：
配置模型路径：
```
#.env文件
TTS_MODEL_DIR=/mnt/c/models/Index-1.5-Voice  # 替换为你本地IndexTTS模型路径
```

添加IndexTTS模型：
```
模型类型：TTS
模型名称：IndexTTS-1.5
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```

**7.3导入ASR模型**

配置模型路径：
```
#.env文件
ASR_MODEL_DIR=/mnt/c/models/SenseVoiceSmall  # 替换为你本地ASR模型路径
```

打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：Speech2text
模型名称：SenseVoiceSmall
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```

**7.4导入Rerank模型**

配置模型路径：
```
#.env文件 
RERANK_MODEL_DIR=/mnt/c/models/bge-reranker-base  # 替换为你本地rerank模型路径
```

同样打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：rerank
模型名称：bge-reranker-base
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```

**7.5导入LLM模型**

配置模型路径：
```
#.env文件
LLM_MODEL_DIR=/mnt/c/models/Qwen3-1.7B  # 替换为你本地LLM模型路径
```

同样打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：LLM
模型名称：Qwen3-1.7B
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```

**7.6导入Embbding模型**

配置模型路径：
```
#.env文件
EMBEDDING_MODEL_DIR = "/mnt/c/models/bge-small-zh-v1.5"  # 替换为你本地Embbding模型路径
```

同样打开`OpenAI-API-compatible`插件，点击`添加模型`，配置内容如下：
```
模型类型：Embbding
模型名称：bge-small-zh-v1.5
API Key：EMPTY
API endpoint URL：`http://172.21.56.14:8888/v1` 或 `http://host.docker.internal:8888/v1`
```

**7.7设置为默认模型**

在右上角`系统模型设置`中的最下方，将：
- `文本转语音模型`设置为`edge-tts`或`IndexTTS-1.5`
- `语音识别模型`设置为`SenseVoiceSmall`
- `文档重排模型`设置为`bge-reranker-base`
- `语言模型`设置为`Qwen3-1.7B`
- `嵌入模型`设置为`bge-small-zh-v1.5`

保存设置。

**7.8使用NL2SQL智能查询功能**

系统会自动识别用户的SQL查询需求，当您在对话中提出数据查询问题时，系统将：

1. **自动识别SQL问题**：如"有多少订单？"、"查询产品平均价格"等
2. **智能获取表结构**：根据问题自动获取相关的数据库表结构信息
3. **生成SQL查询**：LLM基于表结构生成准确的SQL语句
4. **安全执行查询**：在安全环境中执行SQL，仅允许SELECT查询
5. **返回自然语言回答**：将查询结果转换为自然语言回答

**使用示例**：
```
用户: 有多少订单？
系统: 根据查询结果，目前共有15个订单。

用户: 查询所有产品的平均价格
系统: 所有产品的平均价格为258.50元。

用户: 统计每个分类的产品数量
系统: 各分类产品数量统计如下：电子产品有8个，家居用品有12个，服装类有5个。
```

**7.9使用模型**

添加任意一个`chatflow`，进入工作流内容后在右上角`功能`，找到`文字转语音`和`语音转文字`功能，配置我们添加好的模型，将`自动播放`打开，然后对话即可。

### 8. dify中连接MySQL数据库

**8.1连接配置**

在`.env`文件中配置MySQL数据库连接信息:
```
MYSQL_HOST=172.21.48.1  # 在cmd中使用ipconfig | findstr "IPv4" 查看并替换为你的实际的IP地址
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=any4any  # 替换为你的数据库名称
```

**8.2MySQL数据库配置**

在MySQL服务中运行以下命令，允许wsl中的宿主机（172.21.56.14）访问数据库：
```mysql
-- 允许 wsl中的宿主机（172.21.56.14）访问数据库 使用 root 用户连接所有数据库（*.*）
-- YOUR_PASSWORD 替换为你的数据库密码
GRANT ALL PRIVILEGES ON *.* TO 'root'@'172.21.56.14' IDENTIFIED BY 'YOUR_PASSWORD';

-- 如果 MySQL 8.0+，可能需要分开创建用户并授权
CREATE USER 'root'@'172.21.56.14' IDENTIFIED BY 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'172.21.56.14';
```

**8.3构建http请求**

在dify中的`workflow`或`chatflow`中添加`http请求节点`，配置信息如下：
```
请求方式：POST
请求地址：http://localhost:8888/v1/db/query
form-data参数名：query
form-data参数值：SELECT * FROM users LIMIT 1  # 示例查询语句
```

## 工程结构

```
any4any/
├── core/                     # 核心功能模块
│   ├── asr/                  # 语音识别模块
│   │   └── transcription.py  # 音频转录实现
│   ├── auth/                 # 认证模块
│   ├── chat/                 # 聊天相关模块
│   │   ├── conversation_database.py  # 会话数据库操作
│   │   ├── conversation_manager.py   # 会话管理器
│   │   ├── delay_manager.py          # 延迟管理器
│   │   ├── llm.py            # 大语言模型接口
│   │   ├── openai_api.py     # OpenAI API兼容接口
│   │   ├── preview.py        # 预览功能实现
│   │   ├── sql_tools.py      # SQL工具集成
│   │   └── tool_server.py    # 工具服务器（SQL问题识别）
│   ├── database/             # 数据库模块
│   ├── dingtalk/             # 钉钉机器人模块
│   ├── embedding/           # 嵌入模型模块
│   │   ├── document_processor.py # 文档处理器
│   │   ├── embedding_manager.py  # 嵌入管理器
│   │   ├── kb_server.py          # 知识库服务器
│   │   ├── openai_api.py         # OpenAI API接口
│   │   ├── retrieval_engine.py   # 检索引擎
│   │   └── vector_store.py       # 向量存储
│   ├── lifespan.py           # 应用生命周期管理
│   ├── mcp/                  # MCP协议模块
│   ├── rerank/               # 文档重排模块
│   ├── tools/                # 工具模块
│   │   └── nl2sql/           # NL2SQL智能查询工具
│   │       ├── table_info.py # 表信息获取工具
│   │       ├── sql_executor.py # SQL生成和执行工具
│   │       └── workflow.py   # NL2SQL工作流程管理
│   ├── tts/                  # 文本转语音模块
│   │   ├── indextts/         # IndexTTS-1.5引擎
│   │   │   └── infer.py      # IndexTTS推理实现
│   │   └── speech.py         # 语音合成实现
│   └── model_manager.py      # 模型管理器
├── data_models/              # 数据模型定义
├── servers/                  # 网络服务模块
├── static/                   # 静态资源文件
├── utils/                    # 工具模块
├── workflows/                # 工作流和外部衔接插件
├── app.py                    # 应用入口文件
├── cli.py                    # 命令行接口
├── config.py                 # 配置文件
├── any4any.sql               # 数据库初始化脚本
└── .env.example              # 环境变量示例文件

```

## 相关开源项目

- edge-tts：https://github.com/rany2/edge-tts
- IndexTTS-1.5：https://huggingface.co/IndexTeam/IndexTTS-1.5
- SenseVoice：https://github.com/FunAudioLLM/SenseVoice
- bge-reranker-base：https://huggingface.co/BAAI/bge-reranker-base
- bge-small-zh-v1.5：https://huggingface.co/BAAI/bge-small-zh-v1.5
- dify：https://github.com/langgenius/dify
- fastapi：https://github.com/fastapi/fastapi
- Qwen3-1.7B：https://huggingface.co/Qwen/Qwen3-1.7B
- Layui：https://github.com/layui/layui
- font-awesome：https://github.com/FortAwesome/Font-Awesome

## 更新计划
- 增强会话管理功能
- 支持更多大语言模型
- 接入更多即时通讯服务商
- 增强前端界面，提供更友好的用户体验
- 增加更多TTS和ASR模型的支持
- 扩展NL2SQL功能，支持更多数据库类型
- 增加其他接口和服务

## 联系我们
- 官方网站：https://eogee.com
- 邮箱：eogee@qq.com
- B站：https://space.bilibili.com/315734619
- 抖音：[抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC)，每晚8点直播