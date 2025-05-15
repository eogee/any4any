# any4any: One-Click API Service for Speech Recognition, Text-to-Speech, Document Reranking, and Database Connectivity  

<div align="center">
  <a href="./README.md">中文简体</a> ·
  English
</div>


## Purpose  

- Quickly and easily deploy speech recognition (ASR), text-to-speech (TTS), and reranking models (Rerank) for applications like Dify  
- Avoid complex installations of frameworks like Xinference and dependencies to simplify deployment  
- Improve text-to-speech speed using the open-source edge-tts model  
- Enhance speech recognition accuracy with the open-source SenseVoice model  
- Implement knowledge base retrieval reranking using the open-source bge-reranker-base model  
- Provide MySQL database APIs for executing SQL queries and updates  

## Features  

- **Speech Transcription**: Convert audio files to text.  
- **Text-to-Speech**: Convert text to speech files (supports multiple voice styles). Default voice: `zh-CN-XiaoyiNeural`.  
- **Document Reranking**: Rank documents by relevance based on queries.  
- **MySQL Database API**: Connect to databases and execute SQL queries/updates.  
- **Auto-Cleanup**: Temporary audio files are automatically deleted after responses.  
- **API Documentation**: Auto-generated docs accessible at: http://localhost:8888/docs#/  

## Project Structure  

```
├── api_models.py          # API data models & configurations  
├── app.py                 # FastAPI main application  
├── config.py              # Configuration file  
├── core_services.py       # Core utilities  
├── langgenius-openai_api_compatible_0.0.16.difypkg  
├                          # Dify plugin for model imports  
├── services.py            # Business logic implementation  
├── model.py               # Speech transcription model (from SenseVoiceSmall)  
├── requirements.txt       # Dependency list  
├── README.md              # Project documentation  
└── utils/                 # Utility modules (from SenseVoiceSmall)  
    ├── ctc_alignment.py  
    ├── export_utils.py  
    └── ...  
```  

## Prerequisites  

- **WSL2 (Windows Subsystem for Linux)**: Required for Windows systems.  
- **Conda (Anaconda or Miniconda)**: For Python environment management.  
- **Docker Desktop**: Required for Windows to run Dify services.  

## Installation Guide  

### 1. Clone the Project  

```bash  
git clone https://github.com/AnyForAny.git  
# OR  
git clone https://gitee.com/AnyForAny.git  
```  

### 2. Download Models  

```bash  
# Ensure git-lfs is installed (https://git-lfs.com) for large files  
git lfs install  

# Download ASR model: SenseVoiceSmall  
git clone https://hf-mirror.com/FunAudioLLM/SenseVoiceSmall  
# OR  
git clone https://hugginface.co/FunAudioLLM/SenseVoiceSmall  

# Download rerank model: bge-reranker-base  
git clone https://hf-mirror.com/BAAI/bge-reranker-base  
# OR  
git clone https://hugginface.co/BAAI/bge-reranker-base  
```  

### 3. Create Conda Environment  

```bash  
conda create -n any4any python=3.10  
conda activate any4any  
```  

### 4. Install Dependencies  

```bash  
# Install ffmpeg  
sudo apt-get install ffmpeg  
# Verify installation  
ffmpeg -version  
# Install other dependencies  
pip install -r requirements.txt  
```  

### 5. Start the Service  

```bash  
python app.py  
# OR  
uvicorn app:app --host 0.0.0.0 --port 8888  
```  
Service runs at: http://localhost:8888  

### 6. Add & Call Models in Dify  

**6.1 Check Host Machine IP**  
Run `ifconfig` in Linux to find the IP (e.g., `inet 172.21.56.14`).  

**6.2 Import TTS Model**  
1. Ensure Docker and Dify are running.  
2. Import the plugin `langgenius-openai_api_compatible_0.0.16.difypkg`.  
3. In the `OpenAI-API-compatible` plugin, add a model:  
   ```
   Model Type: TTS  
   Model Name: edge-tts  
   API Endpoint URL: `http://172.21.56.14:8888/v1` OR `http://host.docker.internal:8888/v1`  
   API Key: EMPTY  
   Available Voices (comma-separated): zh-CN-XiaoyiNeural  
   ```  

**6.3 Import ASR Model**  
Add another model:  
   ```
   Model Type: Speech2text  
   Model Name: SenseVoiceSmall  
   API Key: EMPTY  
   API Endpoint URL: Same as above  
   ```  

**6.4 Import Rerank Model**  
Add another model:  
   ```
   Model Type: rerank  
   Model Name: bge-reranker-base  
   API Key: EMPTY  
   API Endpoint URL: Same as above  
   ```  

**6.5 Set Default Models**  
In Dify’s `System Model Settings`, set:  
- TTS: `edge-tts`  
- ASR: `SenseVoiceSmall`  
- Rerank: `bge-reranker-base`  

**6.6 Use Models**  
In any `chatflow`, enable `Text-to-Speech` and `Speech-to-Text` under `Features`, configure the models, and enable `Auto-Play`.  

### 7. Connect MySQL in Dify  

Configure MySQL in `config.py`, then use the API in Dify workflows:  
1. Add an `HTTP Request Node` with:  
   ```
   Method: POST  
   URL: http://localhost:8888/v1/db/query  
   Form-data Key: query  
   Form-data Value: SELECT * FROM users LIMIT 1  
   ```  

## Configuration  

Edit `config.py`:  

```python  
import os  
import torch  

class Config:  
    # Server  
    HOST = "0.0.0.0"  
    PORT = 8888  

    # Auth  
    API_KEY = "EMPTY"  # Replace with your key  

    # Models  
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"  
    ASR_MODEL_DIR = "/mnt/c/models/SenseVoiceSmall"       # Replace with your path  
    RERANK_MODEL_DIR = "/mnt/c/models/bge-reranker-base"  # Replace with your path  

    # MySQL  
    MYSQL_HOST = "172.21.48.1"  # Replace with your IP (use `ipconfig | findstr "IPv4"`)  
    MYSQL_PORT = 3306  
    MYSQL_USER = "root"  
    MYSQL_PASSWORD = "root"  
    MYSQL_DATABASE = "any4any"  # Replace with your DB name  

    # Features  
    NO_THINK = True             # Enable no-think mode  
    QUERY_CLEANING = True       # Enable SQL query sanitization  
    PROMPT = ""                 # Custom prompts  

    # Ensure model dirs exist  
    os.makedirs(ASR_MODEL_DIR, exist_ok=True)  
    os.makedirs(RERANK_MODEL_DIR, exist_ok=True)  
```  

## API Examples  

### Speech Transcription  
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
-d '{"input": "Hello,any4any!", "voice": "zh-CN-XiaoyiNeural"}' \  
-o "output.mp3"  
```  

### Document Reranking  
```bash  
curl -X POST "http://localhost:8888/v1/rerank" \  
-H "Authorization: Bearer EMPTY" \  
-H "Content-Type: application/json" \  
-d '{"query": "你好，any4any！", "documents": ["hello,any4any!", "any4any!", "heello,world!"]}' \  
-o "output.json"  
```  

### MySQL Query  
**JSON Request**:  
```bash  
curl -X POST "http://localhost:8888/v1/db/query" \  
-H "Content-Type: application/json" \  
-H "Authorization: Bearer YOUR_API_KEY" \  
-d '{"query":"SELECT * FROM users LIMIT 1"}'  
```  

**Form-data Request**:  
```bash  
curl -X POST "http://localhost:8888/v1/db/query" \  
-H "Authorization: Bearer YOUR_API_KEY" \  
-F "query=SELECT * FROM users LIMIT 1"  
```  

### Health Check  
```bash  
curl http://localhost:8888/health  
```  

## Open-Source Credits  

- edge-tts: https://github.com/rany2/edge-tts  
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice  
- bge-reranker-base: https://hf-mirror.com/BAAI/bge-reranker-base  
- dify: https://github.com/langgenius/dify  
- FastAPI: https://github.com/fastapi/fastapi  

## Roadmap  
- Support more TTS/ASR models  
- Build a frontend for better UX  
- Expand APIs/services  

## Contact  
- Official: https://eogee.com  
- Email: eogee@qq.com  
- Bilibili: https://space.bilibili.com/315734619  
- Douyin: [抖音eogee](https://www.douyin.com/user/MS4wLjABAAAAdH5__CXhFJtSrDQKNuI_vh4mI4-LdyQ_LPKB4d9gR3gISMC_Ak0ApCjFYy_oxhfC) (Live at 8 PM daily)