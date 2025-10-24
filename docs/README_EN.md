# any4any: One-stop API service for LLM conversations, content preview and editing, voice recognition, text-to-speech, document reranking, text embedding, knowledge base system, and MCP services 🚀

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/eogee/any4any)

<div align="center">
  <a href="../README.md">中文简体 ·</a>
  English
</div>

## ✨ Features

**Core Features**: After starting and running this project, you can expose almost all types of models as OpenAI-API compatible interfaces, which can be added to any model management application and track user conversation history. Here's an introduction to each functional module:

- **Conversation Management**: Supports multi-platform LLM conversation management, exposing local models as OpenAI-API compatible interfaces that can be added to any model management application, with user conversation history tracking
- **Preview Mode**: Supports LLM response content preview and editing functionality
- **DingTalk Bot**: Supports DingTalk bot message processing
- **Speech-to-Text**: Convert audio files to text (supports multiple languages)
- **Text-to-Speech**: Convert text to speech files, supports edge-tts and IndexTTS-1.5 engines, providing multiple voice styles
- **Intelligent SQL Query**: Natural language to SQL conversion, allowing users to directly query databases in Chinese, automatically generating and executing SQL statements
- **Knowledge Base**: Provides independent embedding and reranking capabilities, can build knowledge base systems based on ChromaDB vector database
- **MCP Service**: Supports building MCP tools, interfaces, and can be invoked by any MCP client
- **API Documentation**: Automatically generated API documentation accessible via browser at: http://localhost:8888/docs#/

## 🎉 Updates

**2025.10.24(V0.1.2): New Intelligent SQL Query and IndexTTS-1.5 Support**

New Features:
- **NL2SQL Intelligent Query System**: LLM-based natural language to SQL conversion functionality
  - Supports users asking questions directly in Chinese, automatically identifies SQL query requirements
  - Intelligently retrieves relevant database table structure information
  - LLM generates accurate SQL query statements based on table structures
  - Secure SQL execution environment, only allows SELECT queries to ensure database security
  - Intelligently formats query results and generates natural language answers
  - Complete 6-step workflow: Question identification → Table structure retrieval → SQL generation → Query execution → Result formatting → Answer generation
  - [NL2SQL Intelligent Query System Documentation](./en/NL2SQL_Intelligent_Query_System_Documentation.md)

- **IndexTTS-1.5 Voice Engine Support**: New high-quality local TTS engine
  - Supports IndexTTS-1.5 model, providing more natural speech synthesis effects
  - Multiple voice and speech style options
  - Coexists with edge-tts engine, users can choose different TTS engines
  - Optimized audio generation and processing workflow
  - [TTS Implementation and Integration Documentation.md](./en/TTSImplementationAndIntegrationDocumentation.md)

**2025.10.08(V0.1.1): Added Embedding Module**

New Features:
- **Embedding Module**: Complete embedding model support, including document processing, vector storage, retrieval engine, etc.
- **Document Processing**: Support for document parsing, chunking, vectorization and other processing flows
- **Vector Storage**: Efficient vector storage and management mechanism
- **Retrieval Engine**: Document retrieval functionality based on similarity
- **Knowledge Base Server**: Provides knowledge base creation, management and query services
- **OpenAI API Compatible Interface**: Supports calling methods consistent with OpenAI embedding API
- [Knowledge Base System Documentation.md](./en/KnowledgeBaseSystemDocumentation.md)

**2025.9.26(V0.1.0): Added conversation management and preview mode features**

New Features:
- **Conversation Management**: Supports multi-platform conversation management, tracking user conversation history, and enabling context-aware continuous dialogue
- **Preview Mode**: Supports content preview and editing functionality, allowing users to preview and modify generated content. Access via browser: http://localhost:8888/index/
- **DingTalk Bot Integration**: Supports DingTalk bot message processing, enabling interaction with the system within DingTalk
- **Enhanced User Authentication**: Added API key-based authentication mechanism to improve system security
- **Database Conversation Storage**: Stores conversation data in MySQL database, supporting persistence and querying
- [Conversation Management System Documentation.md](./en/ConversationManagementSystemDocumentation.md)

Updates:
- **Restructured Project Architecture**: Added data_models module for managing data models, servers module for managing services, and static directory for managing static files

**2025.5.24(V0.0.6): Added support for building MCP services**

New Features:
- **MCP Tool Construction**: You can add any MCP tools in `core/mcp_tools.py`. By default, it provides addition, subtraction, multiplication, and division of two integers.
- **MCP Tool Registration**: Import the corresponding module in `app.py`, such as `from core.mcp_tools import add, sub, mul, div`, and register them in the `mcp.tool()` function.
- **MCP Service Startup**: Run the start command: `python cli.py` or `a4a-run`, and the service will be available at: http://localhost:9999

Dify workflow file: [mcp_test.yml](../workflows/dify_workflows/mcp_test.yml).

## 🛠️ Prerequisites

- **WSL2 (Windows Subsystem for Linux)**: Required for Windows systems.
- **Conda (Anaconda or Miniconda)**: For Python environment management.
- **Docker Desktop**: Docker desktop application for Windows to run Dify services.
- **MySQL**: For storing conversation data.

## 📥 Installation Guide

### 1. Clone the Project

```bash
git clone https://github.com/eogee/any4any.git
# Or
git clone https://gitee.com/eogee/any4any.git
# Or
git clone https://gitcode.com/eogee/any4any.git
```

You can also download the project via cloud storage: https://pan.quark.cn/s/fbe126d5bd75

### 2. Download Models

Recommended to get all models in one place from cloud storage: https://pan.quark.cn/s/c65799f2cb93

```bash
# Ensure git-lfs is installed (https://git-lfs.com) for large file downloads
# You can download models from huggingface.co, modelscoup.com, or hf-mirror.com sites. Here we use huggingface.co as an example
git lfs install

# Download the speech recognition model: SenseVoiceSmall
git clone https://huggingface.co/FunAudioLLM/SenseVoiceSmall

# Download the reranking model: bge-reranker-base
git clone https://huggingface.co/BAAI/bge-reranker-base

# Download the LLM model: Qwen3-1.7B
git clone https://huggingface.co/Qwen/Qwen3-1.7B

# Download the Embedding model: bge-small-zh-v1.5
git clone https://huggingface.co/BAAI/bge-small-zh-v1.5

# Download IndexTTS-1.5 model
https://hf-mirror.com/IndexTeam/IndexTTS-1.5
```

### 3. Create a Conda Environment

```bash
# Create the conda environment
conda create -n any4any python=3.10
# Activate the environment
conda activate any4any
```

### 4. Install Dependencies

```bash
# Install ffmpeg
sudo apt-get install ffmpeg
# Verify ffmpeg installation
ffmpeg -version
# Install other dependencies
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Copy the example configuration file and modify as needed:

```bash
cp .env.example .env
```

Edit the `.env` file to configure:
- Database connection information (including SQL database configuration for NL2SQL functionality)
- Model paths (including IndexTTS-1.5 model path)
- API keys
- Tool system configuration (enable NL2SQL intelligent query functionality)
- Other custom configurations

**Important Configuration Items**:
```bash
# Database configuration (NL2SQL functionality requires)
SQL_DB_TYPE=mysql
SQL_DB_HOST=localhost
SQL_DB_PORT=3306
SQL_DB_USERNAME=root
SQL_DB_PASSWORD=root
SQL_DB_DATABASE=your_database_name

# IndexTTS-1.5 model configuration (optional)
TTS_MODEL_DIR=/path/to/Index-1.5-Voice

# Tool system configuration
TOOLS_ENABLED=true
TOOLS_DEBUG=false
TOOLS_TIMEOUT=30
```

### 6. Start the Service

```bash
# Start the service directly
python cli.py

# Or use the shortcut command (WSL/Linux environments):
# Permanently install the any4any-run command:
sudo cp a4a-run.sh /usr/local/bin/a4a-run
sudo chmod +x /usr/local/bin/a4a-run
# After installation, use directly:
a4a-run
```

The service will run at the following ports:
- Main service: http://localhost:8888
- MCP service: http://localhost:9999
- DingTalk service: http://localhost:6666

### 7. Add and Call Models in Other Model Platform Applications (Dify as an Example)

**7.1 Check the Host Machine's IP Address**
Run the `ifconfig` command in WSL to check the host machine's IP address.
```bash
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.21.56.14  netmask 255.255.240.0  broadcast 172.21.63.255
```
Here, `172.21.56.14` is the host machine's IP address.

**7.2 Import TTS Model**
Start Docker and ensure the Dify service is running.
Import and install the plugin `langgenius-openai_api_compatible_0.0.16.difypkg` into Dify.

**edge-tts engine configuration**:
Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:
```
Model Type: TTS
Model Name: edge-tts
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`
API Key: EMPTY
Available Voices (comma-separated): zh-CN-XiaoyiNeural
Other fields can be left blank.
```

**IndexTTS-1.5 engine configuration** (if you downloaded IndexTTS-1.5 model):
Configure model path:
```
#.env file
TTS_MODEL_DIR=/mnt/c/models/Index-1.5-Voice  # Replace with your local IndexTTS model path
```

Add IndexTTS model:
```
Model Type: TTS
Model Name: IndexTTS-1.5
API Key: EMPTY
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`
```

**7.3 Import ASR Model**
Configure the model path:
```
#.env file
ASR_MODEL_DIR=/mnt/c/models/SenseVoiceSmall  # Replace with your local ASR model path
```

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:
```
Model Type: Speech2text
Model Name: SenseVoiceSmall
API Key: EMPTY
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`
```

**7.4 Import Rerank Model**
Configure the model path:
```
#.env file
RERANK_MODEL_DIR=/mnt/c/models/bge-reranker-base  # Replace with your local rerank model path
```

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:
```
Model Type: rerank
Model Name: bge-reranker-base
API Key: EMPTY
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`
```

**7.5 Import LLM Model**
Configure the model path:
```
#.env file
LLM_MODEL_DIR=/mnt/c/models/Qwen3-1.7B  # Replace with your local LLM model path
```

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:
```
Model Type: LLM
Model Name: Qwen3-1.7B
API Key: EMPTY
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`
```

**7.6 Import Embedding Model**
Configure the model path:
```
#.env file
EMBEDDING_MODEL_DIR = "/mnt/c/models/bge-small-zh-v1.5"  # Replace with your local Embedding model path
```

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:
```
Model Type: Embedding
Model Name: bge-small-zh-v1.5
API Key: EMPTY
API endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`
```

**7.7 Set as Default Models**
In the top-right `System Model Settings`, set:
- **Text-to-Speech Model**: `edge-tts` or `IndexTTS-1.5`
- **Speech-to-Text Model**: `SenseVoiceSmall`
- **Document Rerank Model**: `bge-reranker-base`
- **Language Model**: `Qwen3-1.7B`
- **Embedding Model**: `bge-small-zh-v1.5`
Click `Save Settings`.

**7.8 Use NL2SQL Intelligent Query Functionality**

The system will automatically identify users' SQL query requirements. When you ask data query questions in conversation, the system will:

1. **Automatically identify SQL questions**: Such as "How many orders are there?", "Query average product price", etc.
2. **Intelligently retrieve table structures**: Automatically retrieve relevant database table structure information based on questions
3. **Generate SQL queries**: LLM generates accurate SQL statements based on table structures
4. **Execute queries securely**: Execute SQL in a secure environment, only allowing SELECT queries
5. **Return natural language answers**: Convert query results to natural language answers

**Usage Examples**:
```
User: How many orders are there?
System: Based on the query results, there are currently 15 orders.

User: Query the average price of all products
System: The average price of all products is 258.50 yuan.

User: Count the number of products in each category
System: Product count statistics by category: Electronics have 8 items, Home goods have 12 items, Clothing has 5 items.
```

**7.9 Use the Models**
Add any `chatflow`, enter the workflow, and enable `Text-to-Speech` and `Speech-to-Text` features in the top-right `Functions`. Configure the models you added, turn on `Auto-Play`, and start chatting.

### 8. Connect to MySQL Database in Dify

**8.1 Connection Configuration**
Configure MySQL connection details in `.env` file:
```
MYSQL_HOST=172.21.48.1  # Replace with your actual IP address (check using `ipconfig | findstr "IPv4"` in cmd)
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=any4any  # Replace with your database name
```

**8.2 MySQL Database Configuration**
Run the following commands in MySQL to allow host machine access (172.21.56.14):
```mysql
-- Allow host machine (172.21.56.14) to access databases as root
-- Replace YOUR_PASSWORD with your database password
GRANT ALL PRIVILEGES ON *.* TO 'root'@'172.21.56.14' IDENTIFIED BY 'YOUR_PASSWORD';

-- For MySQL 8.0+, create user and grant privileges separately
CREATE USER 'root'@'172.21.56.14' IDENTIFIED BY 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'172.21.56.14';
```

**8.3 Build HTTP Request**
In Dify, add an `HTTP Request Node` to your workflow or chatflow and configure as follows:
```
Request Method: POST
Request URL: http://localhost:8888/v1/db/query
Form-data Parameter Name: query
Form-data Parameter Value: SELECT * FROM users LIMIT 1  # Example query
```

## 📁 Project Structure

```
any4any/
├── core/                     # Core functionality modules
│   ├── asr/                  # Speech recognition module
│   │   └── transcription.py  # Audio transcription implementation
│   ├── auth/                 # Authentication module
│   ├── chat/                 # Chat-related modules
│   │   ├── conversation_database.py  # Conversation database operations
│   │   ├── conversation_manager.py   # Conversation manager
│   │   ├── delay_manager.py          # Delay manager
│   │   ├── llm.py            # Large language model interface
│   │   ├── openai_api.py     # OpenAI API compatible interface
│   │   ├── preview.py        # Preview functionality implementation
│   │   ├── sql_tools.py      # SQL tool integration
│   │   └── tool_server.py    # Tool server (SQL question identification)
│   ├── database/             # Database module
│   ├── dingtalk/             # DingTalk bot module
│   ├── embedding/            # Embedding model module
│   │   ├── document_processor.py     # Document processor
│   │   ├── embedding_manager.py      # Embedding manager
│   │   ├── kb_server.py              # Knowledge base server
│   │   ├── openai_api.py             # OpenAI API interface
│   │   ├── retrieval_engine.py       # Retrieval engine
│   │   └── vector_store.py           # Vector store
│   ├── lifespan.py           # Application lifecycle management
│   ├── mcp/                  # MCP protocol module
│   ├── rerank/               # Document reranking module
│   ├── tools/                # Tools module
│   │   └── nl2sql/           # NL2SQL intelligent query tools
│   │       ├── table_info.py # Table information retrieval tools
│   │       ├── sql_executor.py # SQL generation and execution tools
│   │       └── workflow.py   # NL2SQL workflow management
│   ├── tts/                  # Text-to-speech module
│   │   ├── indextts/         # IndexTTS-1.5 engine
│   │   │   └── infer.py      # IndexTTS inference implementation
│   │   └── speech.py         # Speech synthesis implementation
│   └── model_manager.py      # Model manager
├── data_models/              # Data model definitions
├── servers/                  # Server modules
├── static/                   # Static resource files
├── utils/                    # Utility modules
├── workflows/                # Workflows and external integration plugins
├── app.py                    # Application entry file
├── cli.py                    # Command-line interface
├── config.py                 # Configuration file
├── any4any.sql               # Database initialization script
└── .env.example              # Environment variable example file
```

## 🌟 Related Open-Source Projects

- edge-tts: https://github.com/rany2/edge-tts
- IndexTTS-1.5: https://huggingface.co/IndexTeam/IndexTTS-1.5
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice
- bge-reranker-base: https://huggingface.co/BAAI/bge-reranker-base
- bge-small-zh-v1.5: https://huggingface.co/BAAI/bge-small-zh-v1.5
- dify: https://github.com/langgenius/dify
- fastapi: https://github.com/fastapi/fastapi
- Qwen3-1.7B: https://huggingface.co/Qwen/Qwen3-1.7B
- Layui: https://github.com/layui/layui
- font-awesome: https://github.com/FortAwesome/Font-Awesome

## 🚧 Roadmap
- Enhance conversation management functionality
- Support more large language models
- Integrate more instant messaging service providers
- Enhance frontend interface for better user experience
- Add more TTS and ASR models support
- Extend NL2SQL functionality, support more database types
- Add more APIs and services

## 📞 Contact Us
- Official Website: https://eogee.com
- Email: eogee@qq.com
- Bilibili: https://space.bilibili.com/315734619
- Douyin: [抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC) (Live streaming nightly at 8 PM).