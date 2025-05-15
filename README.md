# ANY FOR API 使用说明

## 项目结构
```
.
├── app.py          # FastAPI主应用入口
├── models.py       # 数据模型和配置
├── services.py     # 核心业务逻辑
├── utils.py        # 工具函数
├── requirements.txt # 依赖列表
└── readme.md       # 说明文档
```

## 启动方式

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行服务

#### 方式一：直接运行
```bash
python app.py
```

#### 方式二：使用uvicorn
```bash
uvicorn app:app --host 0.0.0.0 --port 8888
```

### 3. 访问服务
服务启动后，可以通过以下方式访问：
- API文档: http://localhost:8888/api-docs
- 健康检查: http://localhost:8888/health
- 公开测试端点: http://localhost:8888/public-test

## 配置说明
修改config.py中的配置项：
```python
# 认证配置
API_KEY = "your-api-key"  # 设置你的API密钥

# 模型路径配置
MODEL_DIR = "/path/to/your/model"  # ASR模型路径
RERANK_MODEL_PATH = "/path/to/rerank/model"  # Rerank模型路径
```

## 注意事项
1. 确保已安装所有依赖
2. 首次启动会自动初始化模型，可能需要较长时间
3. 生产环境建议使用uvicorn + gunicorn部署
