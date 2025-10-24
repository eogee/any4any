# 聊天页面使用说明

## 功能特性

### 核心功能
- **实时聊天对话**：支持与 AI 助手进行实时对话
- **流式响应**：支持 SSE 流式输出，实时显示 AI 回复过程
- **Markdown 渲染**：支持 Markdown 格式的消息内容渲染
- **消息历史**：自动保存聊天记录到本地存储
- **连接状态监控**：实时显示与服务器的连接状态

### 交互特性
- **智能输入框**：支持自动调整高度，Enter 发送，Shift+Enter 换行
- **响应式设计**：适配桌面端和移动端
- **错误处理**：完善的错误提示和重试机制
- **键盘快捷键**：支持快捷键操作

## 使用方法

### 访问页面
- 直接访问：`http://localhost:8888/chat`
- 根路径重定向：`http://localhost:8888/`

### 基本操作
1. **发送消息**：
   - 在输入框中输入问题
   - 按 Enter 键或点击发送按钮
   - Shift+Enter 可以换行

2. **查看回复**：
   - AI 回复会实时显示（流式模式）
   - 支持 Markdown 格式渲染

3. **管理聊天**：
   - 消息自动保存到本地存储
   - 支持导出聊天记录

## 技术实现

### 前端架构
```
static/js/index/chat/
├── chat.js              # 主聊天控制器
└── README.md           # 使用说明
```

### 后端集成
- **API 端点**：`/v1/chat/completions`
- **流式支持**：Server-Sent Events (SSE)
- **认证方式**：Bearer Token (EMPTY)

### 核心类和方法

#### ChatController 类
```javascript
class ChatController {
    // 初始化方法
    initialize()

    // 消息处理
    handleSendMessage()
    sendMessageToServer()

    // 流式响应处理
    handleStreamResponse()
    handleNormalResponse()

    // UI 操作
    addMessage()
    updateMessage()
    renderMessages()

    // 工具方法
    formatMessageContent()
    autoResizeTextarea()
    scrollToBottom()
}
```

## 配置选项

### API 配置
```javascript
const CHAT_CONFIG = {
    API_ENDPOINT: '/v1/chat/completions',
    STREAM_ENDPOINT: '/v1/chat/completions',
    MODEL: 'default',
    TEMPERATURE: 0.7,
    MAX_TOKENS: 2000,
    TIMEOUT: 60000
};
```

### 功能开关
- `stream`: 是否启用流式响应（默认：true）
- `autoSave`: 是否自动保存聊天历史（默认：true）

## 调试功能

### 控制台命令
打开浏览器控制台，可以使用以下调试命令：

```javascript
// 重置聊天
window.chatDebug.resetChat()

// 切换流式/非流式模式
window.chatDebug.toggleStream()

// 导出聊天记录
window.chatDebug.exportHistory()

// 查看当前状态
window.chatDebug.getStatus()
```

### 状态信息
- 消息数量
- 连接状态
- 输入状态
- 流式模式开关

## 样式定制

### CSS 变量
```css
:root {
    --primary: #16baaa;           /* 主色调 */
    --bg-color: #f8fafc;          /* 背景色 */
    --text-primary: #1e293b;      /* 主文字色 */
    --text-secondary: #64748b;    /* 次要文字色 */
    --border-color: #e2e8f0;      /* 边框色 */
}
```

### 响应式断点
- 桌面端：> 768px
- 移动端：≤ 768px

## 错误处理

### 常见错误类型
1. **网络连接失败**：检查网络设置和服务器状态
2. **请求超时**：网络延迟或服务器响应慢
3. **认证失败**：检查 API Key 配置
4. **模型未初始化**：检查后端模型加载状态

### 错误恢复机制
- 自动重试（最多3次）
- 错误消息提示
- 连接状态实时监控

## 性能优化

### 前端优化
- 消息虚拟滚动（大量消息时）
- 图片懒加载
- 事件防抖和节流
- 内存泄漏防护

### 后端优化
- 流式响应减少延迟
- 消息截断控制 token 数量
- 连接池管理
- 缓存机制

## 浏览器兼容性

### 支持的浏览器
- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

### 必需特性
- Fetch API
- Async/Await
- ES6 Classes
- Server-Sent Events

## 安全考虑

### 前端安全
- XSS 防护（HTML 转义）
- CSRF 防护
- 输入验证
- 敏感信息保护

### 数据安全
- 本地存储加密（可选）
- HTTPS 传输
- 会话管理
- 访问控制

## 更新日志

### v1.0.0 (当前版本)
- ✅ 基础聊天功能
- ✅ 流式响应支持
- ✅ Markdown 渲染
- ✅ 响应式设计
- ✅ 本地存储
- ✅ 错误处理

### 计划功能
- 🔄 多轮对话上下文管理
- 🔄 文件上传支持
- 🔄 聊天室/会话管理
- 🔄 主题切换
- 🔄 插件系统

## 支持

### 问题反馈
如果遇到问题，请检查：
1. 浏览器控制台错误信息
2. 网络连接状态
3. 服务器运行状态

### 开发建议
- 遵循现有的代码规范
- 添加必要的注释和文档
- 进行充分测试
- 保持向后兼容