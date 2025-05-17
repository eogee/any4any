# 文本添加关键词（text_add_keywords）API使用说明

## 服务概述
- 文本分块：将`.text`或`.md`文件按照一定字符数进行分块，并返回分块后的文本，默认按每2000字符分块，允许200字符重叠。
- 文本关键词提取：配合大模型语义理解能力将分块后的内容进行关键字提取，默认提取10-20个关键词。
- 文本追加写入：将原始文本和提取的关键词追加到新的`.text`文件中，文件位于`data/text_add_keywords.txt`。
- 知识库处理：可以在dify使用生成的`.text`文件作为知识库，进行文本检索。

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
- **请求参数**:
  - `chunk_size`: 每块文本大小，默认值可在config.py中配置(DEFAULT_CHUNK_SIZE)
  - `overlap`: 块间重叠区域大小，默认值可在config.py中配置(DEFAULT_OVERLAP)
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
- **使用示例**:
  json请求示例:
  ```bash
  curl -X POST http://localhost:8888/process_text \
    -H "Content-Type: application/json" \
    -d '{"text": "你的长文本内容..."}'
  ```
  form-data请求示例：
  ```bash
  curl -X POST http://localhost:8888/process_text \
    -F "text=你的长文本内容..."
  ```

### 3. 获取指定分块内容
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
  json请求示例:
  ```bash
  curl -X POST http://localhost:8888/get_chunk_content \
    -H "Content-Type: application/json" \
    -d '{"json_data": {"total_chunks":3,"chunks":[{"chunk_number":1,"content":"内容1"}]}, "round_number":1}'
  ```
  form-data请求示例：
  ```bash
  curl -X POST http://localhost:8888/get_chunk_content \
    -F "json_data={\"total_chunks\":3,\"chunks\":[{\"chunk_number\":1,\"content\":\"内容1\"}]}" \
    -F "round_number=1"
  ```

### 4. 写入内容到文件
- **URL**: `/write_content`
- **方法**: POST
- **请求参数**:
  - `content`: 直接传递的文本内容或JSON格式的content字段(如{"content":"文本内容"})
  - `keywords`: 关键词内容(会自动过滤<think>标签并在末尾添加<<<<<)
- **说明**: 
  - 支持四种方式：
    1. 直接传递文本内容(如content=附件)
    2. 传递keywords内容(如keywords=关键词<think>注释</think> → 保存为"关键词<<<<<")
    3. 传递JSON格式的content字段(如content={"content":"附件"})
    4. 上传文件
  - content和keywords不能同时使用
- **响应示例**:
  ```json
  {
    "message": "内容已写入文件",
    "filepath": "data/text_add_keywords.txt"
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