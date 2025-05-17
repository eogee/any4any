# any4any: One-Click API Service for Speech Recognition, Text-to-Speech, Document Reranking, Database Connection, and Knowledge Base Text Processing 🚀  

<div align="center">  
  <a href="../README_EN.md">中文简体 ·  
  English
</div>  

## ✨Features  

- **Speech-to-Text**: Convert audio files to text.  
- **Text-to-Speech**: Convert text to speech files (supports multiple voice styles). Default voice: `zh-CN-XiaoyiNeural`.  
- **Document Reranking**: Sort documents based on relevance to a query.  
- **MySQL Database API**: Connect to a database and execute SQL queries and updates.  
- **Automatic Cleanup**: Temporary audio files are automatically deleted after the response.  
- **Text Processing**: Text chunking, keyword extraction, text appending, and knowledge base processing.  
- **API Documentation**: Automatically generated API documentation accessible via browser at: http://localhost:8888/docs#/  

## 🎉Updates  

**2025.5.18 (V0.0.5): Added Support for Text Keyword Addition (`text_add_keywords`)**  
New Features:  
- **Text Chunking**: Split `.text` or `.md` files into chunks by character count (default: 2000 characters per chunk with 200-character overlap).  
- **Keyword Extraction**: Use large language models to extract keywords from chunked content (default: 10–20 keywords).  
- **Text Appending**: Append the original text and extracted keywords to a new `.text` file (`data/text_add_keywords.txt`).  
- **Knowledge Base Processing**: Use the generated `.text` file in Dify as a knowledge base for text retrieval.  

For detailed API documentation, see: [text_add_keywords.md](./docs/text_add_keywords.md).  

Dify workflow file: [text_add_keywords.yml](./third_party_plugins/text_add_keywords.yml).  

## 🛠️Prerequisites  

- **WSL2 (Windows Subsystem for Linux)**: Required for Windows systems.  
- **Conda (Anaconda or Miniconda)**: For Python environment management.  
- **Docker Desktop**: Docker desktop application for Windows to run Dify services.  

## 📥Installation Guide  

### 1. Clone the Project  

```bash  
git clone https://github.com/eogee/any4any.git  
# Or  
git clone https://gitee.com/eogee/any4any.git  
```  

### 2. Download Models  

```bash  
# Ensure git-lfs is installed (https://git-lfs.com) for large file downloads  
git lfs install  

# Download the speech recognition model: SenseVoiceSmall  
git clone https://hf-mirror.com/FunAudioLLM/SenseVoiceSmall  
# Or  
git clone https://hugginface.co/FunAudioLLM/SenseVoiceSmall  

# Download the reranking model: bge-reranker-base  
git clone https://hf-mirror.com/BAAI/bge-reranker-base  
# Or  
git clone https://hugginface.co/BAAI/bge-reranker-base  
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

### 5. Start the Service  

```bash  
# Start the service directly  
python cli.py  

# Or use the shortcut command (WSL/Linux environments):  
# Permanently install the any4any-run command:  
sudo cp any4any-run.sh /usr/local/bin/any4any-run  
sudo chmod +x /usr/local/bin/any4any-run  
# After installation, use directly:  
any4any-run  
```  
The service will run at: http://localhost:8888  

### 6. Add and Call Models in Dify  

**6.1 Check the Host Machine’s IP Address**  
Run the `ifconfig` command in WSL to check the host machine’s IP address.  
```bash  
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500  
        inet 172.21.56.14  netmask 255.255.240.0  broadcast 172.21.63.255  
```  
Here, `172.21.56.14` is the host machine’s IP address.  

**6.2 Import the TTS Model**  
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

**6.3 Import the ASR Model**  
Configure the model path:  
```python  
# config.py  
ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"  # Replace with your local ASR model path  
```  

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:  
```
Model Type: Speech2text  
Model Name: SenseVoiceSmall  
API Key: EMPTY  
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`  
```  

**6.4 Import the Rerank Model**  
Configure the model path:  
```python  
# config.py  
RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"  # Replace with your local rerank model path  
```  

Open the `OpenAI-API-compatible` plugin, click `Add Model`, and configure as follows:  
```
Model Type: rerank  
Model Name: bge-reranker-base  
API Key: EMPTY  
API Endpoint URL: `http://172.21.56.14:8888/v1` or `http://host.docker.internal:8888/v1`  
```  

**6.5 Set as Default Models**  
In the top-right `System Model Settings`, set:  
- **Text-to-Speech Model**: `edge-tts`  
- **Speech-to-Text Model**: `SenseVoiceSmall`  
- **Document Rerank Model**: `bge-reranker-base`  
Click `Save Settings`.  

**6.6 Use the Models**  
Add any `chatflow`, enter the workflow, and enable `Text-to-Speech` and `Speech-to-Text` features in the top-right `Functions`. Configure the models you added, turn on `Auto-Play`, and start chatting.  

### 7. Connect to MySQL Database in Dify  

**7.1 Connection Configuration**  
Configure MySQL connection details in `config.py`:  
```python  
MYSQL_HOST = "172.17.64.1"  # Replace with your actual IP address (check using `ipconfig | findstr "IPv4"` in cmd)  
MYSQL_PORT = 3306  
MYSQL_USER = "root"  
MYSQL_PASSWORD = "root"  
MYSQL_DATABASE = "any4any"  # Replace with your database name  
```  

**7.2 MySQL Database Configuration**  
Run the following commands in MySQL to allow host machine access (172.21.56.14):  
```mysql  
-- Allow host machine (172.21.56.14) to access databases as root  
-- Replace YOUR_PASSWORD with your database password  
GRANT ALL PRIVILEGES ON *.* TO 'root'@'172.21.56.14' IDENTIFIED BY 'YOUR_PASSWORD';  

-- For MySQL 8.0+, create user and grant privileges separately  
CREATE USER 'root'@'172.21.56.14' IDENTIFIED BY 'YOUR_PASSWORD';  
GRANT ALL PRIVILEGES ON *.* TO 'root'@'172.21.56.14';  
```  

**7.3 Build HTTP Request**  
In Dify, add an `HTTP Request Node` to your workflow or chatflow and configure as follows:  
```
Request Method: POST  
Request URL: http://localhost:8888/v1/db/query  
Form-data Parameter Name: query  
Form-data Parameter Value: SELECT * FROM users LIMIT 1  # Example query  
```  

## ⚙️Configuration  

Modify settings in `config.py`:  
```python  
import os  
import torch  

class Config:  
    # Server Configuration  
    HOST = "0.0.0.0"  
    PORT = 8888  

    # Authentication  
    API_KEY = "EMPTY"  # Replace with your actual API key  

    # Model Configuration  
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"  
    ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"  # Replace with your ASR model path  
    RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"  # Replace with your rerank model path  

    # MySQL Configuration  
    MYSQL_HOST = "172.21.48.1"  # Replace with your IP (check via `ipconfig | findstr "IPv4"` in cmd)  
    MYSQL_PORT = 3306  
    MYSQL_USER = "root"  
    MYSQL_PASSWORD = "root"  
    MYSQL_DATABASE = "any4any"  # Replace with your database name  

    # Feature Toggles  
    NO_THINK = True  # Enable no-think mode  
    QUERY_CLEANING = True  # Enable SQL query sanitization  
    PROMPT = ""  # Custom prompt  

    # Ensure model directories exist  
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)  
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)  
```  

## 📡API Usage Examples  

### Speech-to-Text  
```bash  
curl -X POST "http://localhost:8888/v1/audio/transcriptions" \  
-H "Authorization: Bearer EMPTY" \  
-F "file=@audio.wav" \  
-F "model=whisper-1" \  
-F "language=zh"  
```  

### Text-to-Speech  
```bash  
curl -X POST "http://localhost:8888/v1/audio/speech" \  
-H "Authorization: Bearer EMPTY" \  
-H "Content-Type: application/json" \  
-d '{"input": "Hello, any4any!", "voice": "zh-CN-XiaoyiNeural"}' \  
-o "output.mp3"  
```  

### Document Reranking  
```bash  
curl -X POST "http://localhost:8888/v1/rerank" \  
-H "Authorization: Bearer EMPTY" \  
-H "Content-Type: application/json" \  
-d '{"query": "Hello, any4any!", "documents": ["hello, any4any!", "any4any!", "hello, world!"]}' \  
-o "output.json"  
```  

### MySQL Database Connection  

**Supported Request Formats**:  
1. `application/json`  
2. `multipart/form-data`  

**Security Warning**: The current implementation does not use parameterized queries, posing SQL injection risks.  

**JSON Request**:  
```bash  
curl -X POST "http://localhost:8888/v1/db/query" \  
-H "Content-Type: application/json" \  
-d '{"query":"SELECT * FROM users LIMIT 1"}'  
```  

**Form-data Request**:  
```bash  
curl -X POST "http://localhost:8888/v1/db/query" \  
-F "query=SELECT * FROM users LIMIT 1"  
```  

### Health Check  
```bash  
curl http://localhost:8888/health  
```  

## 🌟Related Open-Source Projects  

- edge-tts: https://github.com/rany2/edge-tts  
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice  
- bge-reranker-base: https://hf-mirror.com/BAAI/bge-reranker-base  
- Dify: https://github.com/langgenius/dify  
- FastAPI: https://github.com/fastapi/fastapi  

## 🚧Roadmap  
- Support more TTS and ASR models.  
- Build a frontend interface for better UX.  
- Add more APIs and services.  

## 📞Contact Us  
- Official Website: https://eogee.com  
- Email: eogee@qq.com  
- Bilibili: https://space.bilibili.com/315734619  
- Douyin: [抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC) (Live streaming nightly at 8 PM).