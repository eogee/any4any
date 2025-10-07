# any4any: One-stop API service for LLM conversations, content preview and editing, voice recognition, text-to-speech, document reranking, text embedding, knowledge base system, and MCP services 🚀

<div align="center">  
  <a href="../README.md">中文简体 ·  </a>
  English
</div>  

## ✨Features  

**Core Features**: After starting and running this project, you can expose almost all types of models as OpenAI-API compatible interfaces, which can be added to any model management application and track user conversation history. Here's an introduction to each functional module:

- **Conversation Management**: Supports multi-platform LLM conversation management, exposing local models as OpenAI-API compatible interfaces that can be added to any model management application, with user conversation history tracking
- **Preview Mode**: Supports LLM response content preview and editing functionality
- **DingTalk Bot**: Supports DingTalk bot message processing
- **Speech-to-Text**: Convert audio files to text (supports multiple languages)
- **Text-to-Speech**: Convert text to speech files (supports multiple voice styles). Default voice: `zh-CN-XiaoyiNeural`
- **Knowledge Base**: Provides independent embedding and reranking capabilities, can build knowledge base systems based on ChromaDB vector database
- **MCP Service**: Supports building MCP tools, interfaces, and can be invoked by any MCP client
- **API Documentation**: Automatically generated API documentation accessible via browser at: http://localhost:8888/docs#/

## 🎉Updates  

**2025.10.08(V0.1.1): Added Embedding Module**

New Features:
- **Embedding Module**: Complete embedding model support, including document processing, vector storage, retrieval engine, etc.
- **Document Processing**: Support for document parsing, chunking, vectorization and other processing flows
- **Vector Storage**: Efficient vector storage and management mechanism
- **Retrieval Engine**: Document retrieval functionality based on similarity
- **Knowledge Base Server**: Provides knowledge base creation, management and query services
- **OpenAI API Compatible Interface**: Supports calling methods consistent with OpenAI embedding API
- [Knowledge Base System Documentation.md](./KnowledgeBaseSystemDocumentation.md)

**2025.9.26(V0.1.0): Added conversation management and preview mode features**

New Features:
- **Conversation Management**: Supports multi-platform conversation management, tracking user conversation history, and enabling context-aware continuous dialogue
- **Preview Mode**: Supports content preview and editing functionality, allowing users to preview and modify generated content. Access via browser: http://localhost:8888/index/
- **DingTalk Bot Integration**: Supports DingTalk bot message processing, enabling interaction with the system within DingTalk
- **Enhanced User Authentication**: Added API key-based authentication mechanism to improve system security
- **Database Conversation Storage**: Stores conversation data in MySQL database, supporting persistence and querying
- [Conversation Management System Documentation.md](./ConversationManagementSystemDocumentation.md)

Updates:
- **Restructured Project Architecture**: Added data_models module for managing data models, servers module for managing services, and static directory for managing static files

**2025.5.24(V0.0.6): Added support for building MCP services**

New Features:
- **MCP Tool Construction**: You can add any MCP tools in `core/mcp_tools.py`. By default, it provides addition, subtraction, multiplication, and division of two integers.
- **MCP Tool Registration**: Import the corresponding module in `app.py`, such as `from core.mcp_tools import add, sub, mul, div`, and register them in the `mcp.tool()` function.
- **MCP Service Startup**: Run the start command: `python cli.py` or `a4a-run`, and the service will be available at: http://localhost:9999

Example documents for calling in Dify and Cherrystudio can be found at: [mcp_test.md](./docs/mcp_test.md) (to be completed later).

Dify workflow file: [mcp_test.yml](./workflows/mcp_test.yml).



## 🛠️Prerequisites  

- **WSL2 (Windows Subsystem for Linux)**: Required for Windows systems.  
- **Conda (Anaconda or Miniconda)**: For Python environment management.  
- **Docker Desktop**: Docker desktop application for Windows to run Dify services.  
- **MySQL**: For storing conversation data.

## 📥Installation Guide  

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

```bash  
# Ensure git-lfs is installed (https://git-lfs.com) for large file downloads
# You can download models from huggingface.co, modelscoup.com, or hf-mirror.com sites. Here we use huggingface.co as an example
# 您可在huggingface.co, modelscoup.com, hf-mirror.com站点中下载模型，此处以huggingface.co为例
git lfs install  

# Download the speech recognition model: SenseVoiceSmall  
git clone https://huggingface.co/FunAudioLLM/SenseVoiceSmall  

# Download the reranking model: bge-reranker-base    
git clone https://huggingface.co/BAAI/bge-reranker-base  

# Download the LLM model: Qwen3-1.7B  
git clone https://huggingface.co/Qwen/Qwen3-1.7B

# Download the Embedding model: bge-small-zh-v1.5
git clone https://huggingface.co/BAAI/bge-small-zh-v1.5  
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
- Database connection information
- Model paths
- API keys
- Other custom configurations

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

**7.2 Import the TTS Model**  
Start Docker and ensure the Dify service is running.  
Import and install the plugin `langgenius-openai_api_compatible_0.0.16.difypkg` into Dify.  
Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:  
```
Model Type: TTS  
Model Name: edge-tts  
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`  
API Key: EMPTY  
Available Voices (comma-separated): zh-CN-XiaoyiNeural  
Other fields can be left blank.  
```  

**7.3 Import the ASR Model**  
Configure the model path:  
```python  
# config.py  
# .env file
ASR_MODEL_DIR=/mnt/c/models/SenseVoiceSmall  # Replace with your local ASR model path  
```  

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:  
```
Model Type: Speech2text  
Model Name: SenseVoiceSmall  
API Key: EMPTY  
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`  
```  

**7.4 Import the Rerank Model**  
Configure the model path:  
```
# .env file
RERANK_MODEL_DIR=/mnt/c/models/bge-reranker-base  # Replace with your local rerank model path
```  

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:  
```
Model Type: rerank  
Model Name: bge-reranker-base  
API Key: EMPTY  
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`  
```  

**7.5 Import the LLM Model**  
Configure the model path:  
```python  
# .env file
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
# .env file
EMBBEDING_MODEL_DIR = "/mnt/c/models/bge-small-zh-v1.5"  # Replace with your local Embedding model path
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
- **Text-to-Speech Model**: `edge-tts`  
- **Speech-to-Text Model**: `SenseVoiceSmall`  
- **Document Rerank Model**: `bge-reranker-base`  
- **Language Model**: `Qwen3-1.7B`  
- **Embedding Model**: `bge-small-zh-v1.5`
Click `Save Settings`.  

**7.8 Use the Models**  
Add any `chatflow`, enter the workflow, and enable `Text-to-Speech` and `Speech-to-Text` features in the top-right `Functions`. Configure the models you added, turn on `Auto-Play`, and start chatting.  

### 8. Connect to MySQL Database in Dify  

**8.1 Connection Configuration**  
Configure MySQL connection details in `.env` file:  
```
MYSQL_HOST="172.21.48.1"  # Replace with your actual IP address (check using `ipconfig | findstr "IPv4"` in cmd)
MYSQL_PORT=3306
MYSQL_USER="root"
MYSQL_PASSWORD="root"
MYSQL_DATABASE="any4any"  # Replace with your database name
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

## 📁Project Structure

```
any4any/
├── core/                     # Core functionality modules
│   ├── asr/                  # Speech recognition module
│   │   └── transcription.py  # Audio transcription implementation
│   ├── auth/                 # Authentication module
│   │   └── model_auth.py     # Model authentication implementation
│   ├── chat/                 # Chat-related modules
│   │   ├── conversation_database.py  # Conversation database operations
│   │   ├── conversation_manager.py   # Conversation manager
│   │   ├── delay_manager.py          # Delay manager
│   │   ├── llm.py            # Large language model interface
│   │   ├── openai_api.py     # OpenAI API compatible interface
│   │   └── preview.py        # Preview functionality implementation
│   ├── database/             # Database module
│   │   └── database.py       # Database connection and query implementation
│   ├── dingtalk/             # DingTalk bot module
│   │   └── message_manager.py # DingTalk message processing
│   ├── embedding/            # Embedding model module
│   │   ├── document_processor.py     # Document processor
│   │   ├── embedding_manager.py      # Embedding manager
│   │   ├── kb_server.py              # Knowledge base server
│   │   ├── openai_api.py             # OpenAI API interface
│   │   ├── retrieval_engine.py       # Retrieval engine
│   │   └── vector_store.py           # Vector store
│   ├── lifespan.py           # Application lifecycle management
│   ├── log.py                # Log management
│   ├── mcp/                  # MCP protocol module
│   │   └── mcp_tools.py      # MCP tools implementation
│   ├── rerank/               # Document reranking module
│   │   └── rerank.py         # Document reranking implementation
│   ├── tts/                  # Text-to-speech module
│   │   ├── file.py           # Audio file processing
│   │   └── speech.py         # Speech synthesis implementation
│   └── model_manager.py      # Model manager
├── data_models/              # Data model definitions
│   ├── Auth.py               # Authentication related models
│   ├── Preview.py            # Preview related models
│   └── model.py              # Base model class
├── servers/                  # Server modules
├── static/                   # Static resource files
├── utils/                    # Utility modules
├── workflows/                # Workflows and external 
├── app.py                    # Application entry file
├── cli.py                    # Command-line interface
├── config.py                 # Configuration file
├── requirements.txt          # Dependency package list
├── any4any.sql               # Database initialization script
├── a4a-run.sh                # Startup script
└── .env.example              # Environment variable example file
```

## 🌟Related Open-Source Projects  

- edge-tts: https://github.com/rany2/edge-tts
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice
- bge-reranker-base: https://huggingface.co/BAAI/bge-reranker-base
- bge-small-zh-v1.5: https://huggingface.co/BAAI/bge-small-zh-v1.5
- dify: https://github.com/langgenius/dify
- fastapi: https://github.com/fastapi/fastapi
- Qwen3-1.7B: https://huggingface.co/Qwen/Qwen3-1.7B
- Layui: https://github.com/layui/layui
- font-awesome: https://github.com/FortAwesome/Font-Awesome  

## 🚧Roadmap  
- Enhance conversation management functionality
- Support more large language models
- Integrate more instant messaging service providers
- Enhance frontend interface for better user experience
- Support more TTS and ASR models
- Add more APIs and services

## 📞Contact Us  
- Official Website: https://eogee.com  
- Email: eogee@qq.com  
- Bilibili: https://space.bilibili.com/315734619  
- Douyin: [抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC) (Live streaming nightly at 8 PM).