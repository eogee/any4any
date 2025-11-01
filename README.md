# any4any: 企业级多模态AI平台 - 大模型会话、数字人、智能查询、语音处理与知识库系统

<div align="center">
    <a href="https://zread.ai/eogee/any4any"><img src="https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff"></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-dfd.svg"></a>
    <a href=""><img src="https://img.shields.io/badge/python-3.10+-aff.svg"></a>
    <a href=""><img src="https://img.shields.io/badge/os-linux%2C%20win%2C%20mac-pink.svg"></a>
    <a href="https://github.com/eogee/any4any/releases"><img src="https://img.shields.io/github/v/release/eogee/any4any?display_name=tag&include_prereleases"></a>
</div>

<div align="center">
  中文简体 ·
  <a href="docs/README_EN.md">English</a>
</div>

## 项目概述

any4any是一个企业级多模态AI平台，提供完整的智能交互解决方案。集成了大语言模型对话、数字人系统、智能SQL查询、语音处理、知识库系统等核心功能，支持OpenAI兼容API接口，可无缝集成到各类AI应用中。

**核心特色**：
- **多模态AI交互**：支持文本、语音、视频的全方位智能交互
- **数字人系统**：实时唇形同步、语音驱动的数字人交互
- **智能查询**：自然语言到SQL的智能数据库查询
- **知识库系统**：基于向量检索的智能知识管理和问答
- **语音处理**：高质量的语音识别和合成
- **统一接口**：OpenAI兼容API，支持各类模型管理应用

## 功能特性

### 核心功能模块

#### Any4DH数字人系统
- **实时数字人交互**：基于WebRTC的实时音视频流处理
- **智能唇形同步**：Wav2Lip技术实现精准的音视频同步
- **统一接口支持**：与LLM系统深度集成，支持语音知识库
- **多传输协议**：支持WebRTC、RTMP等多种传输方式
- **会话管理**：支持多用户并发数字人交互

#### 智能对话系统
- **Web聊天界面**：完整的Web聊天界面，支持流式和非流式响应
- **外部LLM集成**：支持OpenAI、通义千问等兼容API
- **会话管理**：多平台会话历史追踪和上下文连续对话
- **预览模式**：支持内容预览和编辑功能
- **Markdown渲染**：实时消息显示与历史记录管理

#### NL2SQL智能查询系统
- **上下文感知查询**：基于会话历史的智能上下文检索
- **8步骤工作流程**：完整的自然语言到SQL转换流程
- **追问识别**：支持"分别"、"都"、"谁"等追问关键词
- **安全查询**：多层SQL安全验证，仅允许SELECT查询
- **智能结果生成**：基于查询结果的自然语言回答

#### 知识库系统
- **BGE模型集成**：使用BGE-Small-ZH和重排序模型
- **多格式文档处理**：支持PDF、DOCX、TXT等多种格式
- **语义检索**：基于ChromaDB的高效向量检索
- **OpenAI兼容API**：提供标准的嵌入API接口
- **智能问答**：结合检索结果的智能问答生成

#### 语音处理系统
- **双引擎支持**：EdgeTTS云服务和IndexTTS-1.5本地模型
- **智能文本过滤**：13层过滤策略，移除影响语音合成的特殊内容
- **高性能处理**：支持IndexTTS-1.5快速模式和流式音频生成
- **智能文件管理**：全局临时文件管理器，支持自动清理
- **异步处理**：基于FastAPI的高并发语音合成

#### 工具系统与MCP服务
- **工具管理器**：统一的工具识别、注册和执行框架
- **语音知识库**：基于语义匹配的智能语音回复
- **MCP协议支持**：构建MCP工具和接口，支持MCP客户端调用
- **钉钉机器人**：支持钉钉机器人消息处理和智能回复

## 更新日志

### V0.1.3 (2025.11.01) - 重大功能升级

#### 数字人系统全新上线
- **Any4DH数字人系统**：完整的实时数字人交互平台
  - WebRTC传输协议支持
  - 实时语音处理和唇形同步
  - 流媒体处理和人脸检测
  - 统一接口和会话管理

#### 智能对话系统全面升级
- **Web聊天功能**：完整的Web聊天界面
  - 实时消息显示与历史记录管理
  - Markdown格式渲染
  - 预览模式和延迟模式支持
  - 用户身份验证和会话管理

- **外部LLM API集成**：支持OpenAI、通义千问等兼容API
  - API密钥管理和重试机制
  - 流式和非流式响应支持

#### NL2SQL智能查询系统增强
- **上下文感知查询**：SQLContextManager智能上下文管理
  - 会话历史记录智能分析
  - 相关性评分算法
  - 上下文自动构建
  - 追问机制支持

- **工作流程优化**：8步骤完整工作流程
  - 自动上下文增强
  - 错误处理和容错机制

#### 语音知识库系统
- **语音检索功能**：基于语义匹配的智能语音回复
  - 语音数据管理
  - 语义检索引擎
  - 语音工作流程
  - 多语言语音库支持

#### 技术架构升级
- **前端架构重构**：新增聊天界面、数字人控制面板
- **后端服务扩展**：聊天服务器、数字人服务器
- **工具系统重构**：工具管理逻辑重构和SQL问题识别增强
- **TTS系统优化**：统一临时文件管理、流式TTS处理

#### 其他重要更新
- **智能文本过滤**：新增13层过滤策略，包括思考内容过滤
- **统一模型管理**：ModelManager实现模型按需加载和统一管理
- **配置管理升级**：新增数字人、语音知识库、外部LLM等配置
- **文档完善**：新增Any4DH、NL2SQL、语音知识库等详细文档

---

**历史版本更新**：

**V0.1.2 (2025.10.24)：新增智能SQL查询和IndexTTS-1.5支持**
- NL2SQL智能查询系统：自然语言到SQL转换功能
- IndexTTS-1.5语音引擎：高质量本地TTS引擎支持

**V0.1.1 (2025.10.08)：新增嵌入模型模块**
- Embedding模块：完整的嵌入模型支持，包括文档处理、向量存储、检索引擎
- 知识库系统：基于ChromaDB向量数据库的知识库构建和管理

**V0.1.0 (2025.9.26)：新增会话管理和预览模式功能**
- 会话管理：多平台会话管理和历史追踪
- 预览模式：内容预览和编辑功能
- 钉钉机器人集成：支持钉钉机器人消息处理

## 环境要求

### 基础环境
- **Python**: 3.10+
- **操作系统**: Linux, Windows, macOS
- **内存**: 建议8GB+ (AI模型运行需要)
- **存储**: 额外20GB用于模型文件
- **GPU**: 推荐用于AI模型加速 (可选)

### 依赖环境
- **WSL2**: Windows系统下的必要条件
- **Conda**: Python环境管理
- **MySQL**: 数据库服务 (会话存储和NL2SQL功能)
- **FFmpeg**: 音频处理库

## 安装指南

### 1. 克隆项目

```bash
git clone https://github.com/eogee/any4any.git
# 或
git clone https://gitee.com/eogee/any4any.git
# 或
git clone https://gitcode.com/eogee/any4any.git
```

> 网盘下载：https://pan.quark.cn/s/fbe126d5bd75

### 2. 下载AI模型

> 推荐网盘一站式获取：https://pan.quark.cn/s/c65799f2cb93

```bash
# 确认已安装git-lfs
git lfs install

# 下载语音识别模型：SenseVoiceSmall
git clone https://huggingface.co/FunAudioLLM/SenseVoiceSmall

# 下载重排序模型：bge-reranker-base
git clone https://huggingface.co/BAAI/bge-reranker-base

# 下载LLM模型：Qwen3-0.6B
git clone https://huggingface.co/Qwen/Qwen3-0.6B

# 下载Embedding模型：bge-small-zh-v1.5
git clone https://huggingface.co/BAAI/bge-small-zh-v1.5

# 下载IndexTTS-1.5模型
git clone https://hf-mirror.com/IndexTeam/IndexTTS-1.5

# 下载Wav2Lip模型（数字人功能）
git clone https://huggingface.co/charlesXu/wav2lip
```

### 3. 创建Python环境

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

# 验证ffmpeg安装
ffmpeg -version

# 安装Python依赖
pip install -r requirements.txt
```

### 5. 配置环境变量

```bash
# 复制配置文件
cp .env.example .env
```

**重要配置项**：
```bash
# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=any4any

# SQL数据库配置（NL2SQL功能）
SQL_DB_TYPE=mysql
SQL_DB_HOST=localhost
SQL_DB_PORT=3306
SQL_DB_USERNAME=root
SQL_DB_PASSWORD=root
SQL_DB_DATABASE=your_database_name

# 模型路径配置
LLM_MODEL_DIR=/path/to/Qwen3-0.6B
ASR_MODEL_DIR=/path/to/SenseVoiceSmall
RERANK_MODEL_DIR=/path/to/bge-reranker-base
EMBEDDING_MODEL_DIR=/path/to/bge-small-zh-v1.5
INDEX_TTS_MODEL_DIR=/path/to/IndexTTS-1.5

# 数字人系统配置
ANY4DH_ENABLED=true
ANY4DH_TRANSPORT=webrtc
ANY4DH_MODEL=wav2lip

# 工具系统配置
TOOLS_ENABLED=true
```

### 6. 启动服务

```bash
# 直接启动服务
python cli.py

# 或使用快捷命令(WSL/Linux环境)
sudo cp a4a-run.sh /usr/local/bin/a4a-run
sudo chmod +x /usr/local/bin/a4a-run
# 安装后可直接使用
a4a-run
```

**服务端口**：
- **主服务**: http://localhost:8888
- **MCP服务**: http://localhost:9999
- **钉钉服务**: http://localhost:6666

### 7. 功能验证

#### 数字人系统
访问：http://localhost:8888/dh/dashboard
- 实时数字人交互
- 音视频流控制
- 参数实时调节

#### 智能对话系统
访问：http://localhost:8888/index/
- Web聊天界面
- 会话历史管理
- Markdown渲染

#### NL2SQL智能查询
在对话中直接使用自然语言查询数据库：
```
用户: 有多少订单？
系统: 根据查询结果，目前共有15个订单。

用户: 统计每个分类的产品数量
系统: 各分类产品数量统计如下：电子产品有8个，家居用品有12个，服装类有5个。
```

## API接口使用

### OpenAI兼容接口

项目提供完整的OpenAI兼容API接口，可被任何模型管理应用添加使用。

#### 主要接口端点
- **LLM对话**: `/v1/chat/completions`
- **语音合成**: `/v1/audio/speech`
- **语音识别**: `/v1/audio/transcriptions`
- **文本嵌入**: `/v1/embeddings`
- **文档重排**: `/v1/rerank`
- **API文档**: http://localhost:8888/docs

### 模型集成示例

#### TTS模型配置
```bash
# edge-tts引擎
模型类型：TTS
模型名称：edge-tts
API endpoint URL：http://host.docker.internal:8888/v1
API Key：EMPTY
可用声音：zh-CN-XiaoyiNeural

# IndexTTS-1.5引擎
模型类型：TTS
模型名称：IndexTTS-1.5
API endpoint URL：http://host.docker.internal:8888/v1
API Key：EMPTY
```

#### ASR模型配置
```bash
模型类型：Speech2text
模型名称：SenseVoiceSmall
API Key：EMPTY
API endpoint URL：http://host.docker.internal:8888/v1
```

#### LLM模型配置
```bash
模型类型：LLM
模型名称：Qwen3-0.6B
API Key：EMPTY
API endpoint URL：http://host.docker.internal:8888/v1
```

#### Embedding模型配置
```bash
模型类型：Embedding
模型名称：bge-small-zh-v1.5
API Key：EMPTY
API endpoint URL：http://host.docker.internal:8888/v1
```

#### Rerank模型配置
```bash
模型类型：rerank
模型名称：bge-reranker-base
API Key：EMPTY
API endpoint URL：http://host.docker.internal:8888/v1
```

## 项目架构

```
any4any/
├── core/                           # 核心功能模块
│   ├── any4dh/                     # 数字人系统模块
│   │   ├── any4dh_server.py        # 数字人服务器
│   │   ├── live_talking/           # 实时语音处理
│   │   ├── wav2lip/                # Wav2Lip唇形同步
│   │   └── streaming_utils.py      # 流媒体处理
│   ├── asr/                        # 语音识别模块
│   ├── auth/                       # 认证模块
│   ├── chat/                       # 智能对话模块
│   │   ├── conversation_manager.py # 会话管理器
│   │   ├── external_llm.py         # 外部LLM集成
│   │   ├── openai_api.py           # OpenAI API兼容接口
│   │   └── tool_manager.py         # 工具管理器
│   ├── database/                   # 数据库模块
│   ├── dingtalk/                   # 钉钉机器人模块
│   ├── embedding/                  # 知识库系统模块
│   │   ├── document_processor.py   # 文档处理器
│   │   ├── embedding_manager.py    # 嵌入管理器
│   │   ├── retrieval_engine.py     # 检索引擎
│   │   └── vector_store.py          # 向量存储
│   ├── tools/                      # 工具模块
│   │   ├── nl2sql/                 # NL2SQL智能查询
│   │   └── voice_kb/               # 语音知识库
│   ├── tts/                        # 语音合成模块
│   │   ├── index_tts_engine.py     # IndexTTS-1.5引擎
│   │   ├── filter.py               # 文本过滤器
│   │   └── temp_file_manager.py    # 临时文件管理器
│   └── model_manager.py            # 模型管理器
├── servers/                        # 网络服务模块
│   ├── ChatServer.py               # 聊天服务器
│   └── DHServer.py                  # 数字人服务器
├── static/                         # 前端资源
│   ├── index/                      # 主界面
│   │   └── chat/                   # 聊天界面
│   └── js/                         # JavaScript模块
├── data_models/                    # 数据模型定义
├── docs/                           # 项目文档
├── workflows/                      # 工作流配置
├── app.py                          # 应用入口
├── cli.py                          # 命令行接口
├── config.py                       # 配置文件
└── .env.example                    # 环境变量示例
```

## 详细文档

- [会话管理系统说明文档](./docs/zh/会话管理系统说明文档.md)
- [NL2SQL智能查询系统说明文档](./docs/zh/NL2SQL智能查询系统说明文档.md)
- [知识库系统说明文档](./docs/zh/知识库系统说明文档.md)
- [TTS实现与集成说明文档](./docs/zh/TTS实现与集成说明文档.md)
- [Any4DH系统说明文档](./docs/zh/any4dh系统说明文档.md)
- [版本发布更新文档](./docs/version_notes/zh/V0.1.3_release_notes.md)

## 相关开源项目

- **edge-tts**: Microsoft Edge TTS API - https://github.com/rany2/edge-tts
- **IndexTTS-1.5**: 高质量中文语音合成 - https://huggingface.co/IndexTeam/IndexTTS-1.5
- **SenseVoice**: 多语言语音识别 - https://github.com/FunAudioLLM/SenseVoice
- **Wav2Lip**: 唇形同步技术 - https://github.com/Rudrabha/Wav2Lip
- **bge-reranker-base**: 文档重排序模型 - https://huggingface.co/BAAI/bge-reranker-base
- **bge-small-zh-v1.5**: 中文文本嵌入 - https://huggingface.co/BAAI/bge-small-zh-v1.5
- **Qwen3-0.6B**: 高性能语言模型 - https://huggingface.co/Qwen/Qwen3-0.6B
- **FastAPI**: 现代Web框架 - https://github.com/fastapi/fastapi
- **ChromaDB**: 向量数据库 - https://github.com/chroma-core/chroma

## 未来规划

### 短期计划 (V0.1.4)
- 性能监控和优化系统
- 用户反馈收集和处理机制
- 文档完善和示例补充
- 单元测试覆盖提升

### 中期计划 (V0.2.0)
- 移动端应用支持
- 更多AI模型集成
- 企业级功能扩展
- 云原生部署支持

### 长期规划 (V1.0.0)
- 分布式架构支持
- 多租户管理系统
- 高级分析仪表板
- 生态系统建设

## 技术支持

- **官方网站**: https://eogee.com
- **邮箱**: eogee@qq.com
- **B站**: https://space.bilibili.com/315734619
- **抖音**: [抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC)，每晚8点直播
- **GitHub Issues**: 项目问题反馈和功能建议

## 许可证

本项目采用 [MIT License](./LICENSE) 开源协议。

---

<div align="center">
  <strong>感谢您对any4any项目的关注！</strong><br>
  <em>ANY FOR ANY，广受开发者和企业用户信赖的多模态AI开源平台！</em>
</div>