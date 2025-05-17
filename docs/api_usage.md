# 文本分块处理API使用说明

## 服务概述
本服务提供文本分块处理功能，将长文本分割为指定大小的块，支持重叠区域设置。

## API端点

### 1. 获取服务信息
- **URL**: `/`
- **方法**: GET
- **响应**: 
  ```json
  {
    "message": "文本分块处理服务",
    "usage": "发送POST请求到/process_text端点，包含JSON数据: {'text': '你的长文本内容...'}"
  }
  ```

### 2. 文本分块处理
- **URL**: `/process_text`
- **方法**: POST
- **请求体**:
  ```json
  {
    "text": "需要分块的长文本内容..."
  }
  ```
- **响应示例**:
  ```json
  {
    "total_chunks": 3,
    "chunk_size": 2000,
    "overlap": 200,
    "chunks": [
      {
        "chunk_number": 1,
        "content": "第一块文本内容...",
        "length": 2000
      },
      {
        "chunk_number": 2,
        "content": "第二块文本内容...",
        "length": 2000
      }
    ]
  }
  ```

## 使用示例

### JSON请求示例
```bash
curl -X POST http://localhost:8888/process_text \
  -H "Content-Type: application/json" \
  -d '{"text": "你的长文本内容..."}'
```

### form-data请求示例
```bash
curl -X POST http://localhost:8888/process_text \
  -F "text=你的长文本内容..."
```

### Python示例 (JSON)
```python
import requests

url = "http://localhost:8888/process_text"
data = {"text": "你的长文本内容..."}
response = requests.post(url, json=data)
print(response.json())
```

### Python示例 (form-data)
```python
import requests

url = "http://localhost:8888/process_text"
data = {"text": "你的长文本内容..."}
response = requests.post(url, files=data)
print(response.json())
```

## 参数说明
- `chunk_size`: 每块文本大小，默认值可在config.py中配置(DEFAULT_CHUNK_SIZE)
- `overlap`: 块间重叠区域大小，默认值可在config.py中配置(DEFAULT_OVERLAP)

## 3. 获取指定分块内容
- **URL**: `/get_chunk_content/`
- **方法**: POST
- **请求参数**:
  - `json_data`: JSON字符串格式的chunks数据(来自/process_text响应)
  - `round_number`: 要获取的chunk编号
- **响应示例**:
  ```json
  {
    "content": "指定编号的文本内容..."
  }
  ```
- **使用示例**:
  ```bash
  curl -X POST http://localhost:8888/get_chunk_content \
    -F "json_data={\"total_chunks\":3,\"chunks\":[{\"chunk_number\":1,\"content\":\"内容1\"}]}" \
    -F "round_number=1"
  ```

## 4. 写入内容到文件
- **URL**: `/write_content`
- **方法**: POST
- **请求参数**:
  - `content`: 直接传递的文本内容或JSON格式的content字段(如{"content":"文本内容"})
    - 会自动将双换行符(\n\n)替换为单换行符(\n)
    - 会自动过滤掉'# '字符串
  - `keywords`: 关键词内容(会自动过滤<think>标签并在末尾添加<<<<<)
  - `file`: 上传的文件内容
- **说明**: 
  - 支持四种方式：
    1. 直接传递文本内容(如content=附件)
    2. 传递keywords内容(如keywords=关键词<think>注释</think> → 保存为"关键词<<<<<")
    3. 传递JSON格式的content字段(如content={"content":"附件"})
    4. 上传文件
  - content和keywords不能同时使用
  - content字段会进行以下处理：
    - 将连续的两个换行符替换为一个
    - 删除所有出现的'# '字符串
- **响应示例**:
  ```json
  {
    "message": "内容已写入文件",
    "filepath": "data/fixed_knowledge.txt"
  }
  ```
- **使用示例**:
  ```bash
  # 方式1：直接传文本
  curl -X POST http://localhost:8888/write_content \
    -F "content=这是要保存的文本内容"

  # 方式2：上传文件
  curl -X POST http://localhost:8888/write_content \
    -F "file=@test.txt"
  ```
- **Python示例**:
  ```python
  import requests

  # 方式1：直接传文本
  response = requests.post(
      "http://localhost:8888/write_content",
      files={"content": (None, "这是要保存的文本内容")}
  )

  # 方式2：上传文件
  with open("test.txt", "rb") as f:
      response = requests.post(
          "http://localhost:8888/write_content",
          files={"file": ("test.txt", f)}
      )
  
  print(response.json())
  ```
