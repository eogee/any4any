/**
 * 聊天页面控制器
 * 功能：管理聊天页面的所有交互逻辑，包括消息发送、接收和显示
 */

// 常量定义
const CHAT_CONFIG = {
    API_ENDPOINT: '/v1/chat/completions',
    STREAM_ENDPOINT: '/v1/chat/completions',
    MODEL: 'default',
    TEMPERATURE: 0.7,
    MAX_TOKENS: 2000,
    TIMEOUT: 60000,
    RETRY_ATTEMPTS: 3,
    AUTO_SCROLL_DELAY: 100,
    TYPING_DELAY: 500
};

// 聊天控制器类
class ChatController {
    constructor() {
        // DOM 元素引用
        this.elements = {};

        // 数据状态
        this.messages = [];
        this.isConnected = false;
        this.isTyping = false;
        this.currentStreamController = null;

        // 配置选项
        this.options = {
            stream: true,
            model: CHAT_CONFIG.MODEL,
            temperature: CHAT_CONFIG.TEMPERATURE,
            max_tokens: CHAT_CONFIG.MAX_TOKENS
        };
    }

    /**
     * 初始化聊天控制器
     */
    initialize() {
        this.initializeElements();
        this.setupEventListeners();
        this.checkConnection();
        this.loadChatHistory();
    }

    /**
     * DOM 元素初始化
     */
    initializeElements() {
        this.elements = {
            chatMessages: document.getElementById('chatMessages'),
            chatInput: document.getElementById('chatInput'),
            sendButton: document.getElementById('sendButton'),
            emptyState: document.getElementById('emptyState'),
            typingIndicator: document.getElementById('typingIndicator'),
            connectionStatus: document.getElementById('connectionStatus'),
            newChatBtn: document.getElementById('newChatBtn')
        };
    }

    /**
     * 事件监听器设置
     */
    setupEventListeners() {
        // 发送按钮点击事件
        this.elements.sendButton.addEventListener('click', () => {
            this.handleSendMessage();
        });

        // 输入框事件
        this.elements.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSendMessage();
            }
        });

        // 输入框自动调整高度
        this.elements.chatInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });

        // 新会话按钮
        if (this.elements.newChatBtn) {
            this.elements.newChatBtn.addEventListener('click', () => {
                this.handleNewChat();
            });
        }

        // 页面关闭前清理
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });

        // 错误处理
        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e);
            UiUtils.showMessage('发生未知错误，请刷新页面重试', 'error');
        });
    }

    /**
     * 检查连接状态
     */
    async checkConnection() {
        try {
            const response = await fetch('/health', {
                method: 'GET',
                timeout: 5000
            });

            this.isConnected = response.ok;
            this.updateConnectionStatus(this.isConnected);

        } catch (error) {
            console.error('Connection check failed:', error);
            this.isConnected = false;
            this.updateConnectionStatus(false);
        }
    }

    /**
     * 更新连接状态显示
     */
    updateConnectionStatus(isConnected) {
        const statusElement = this.elements.connectionStatus;
        const indicatorElement = statusElement.previousElementSibling;

        if (isConnected) {
            statusElement.textContent = '已连接';
            indicatorElement.style.background = '#4ade80';
        } else {
            statusElement.textContent = '连接断开';
            indicatorElement.style.background = '#ef4444';
        }
    }

    /**
     * 加载聊天历史（可选功能）
     */
    async loadChatHistory() {
        // 如果需要从本地存储或服务器加载历史记录
        try {
            const history = localStorage.getItem('chatHistory');
            if (history) {
                this.messages = JSON.parse(history);
                this.renderMessages();
            }
        } catch (error) {
            console.error('Failed to load chat history:', error);
        }
    }

    /**
     * 保存聊天历史到本地存储
     */
    saveChatHistory() {
        try {
            // 只保存最近50条消息
            const recentMessages = this.messages.slice(-50);
            localStorage.setItem('chatHistory', JSON.stringify(recentMessages));
        } catch (error) {
            console.error('Failed to save chat history:', error);
        }
    }

    /**
     * 处理发送消息
     */
    async handleSendMessage() {
        const message = this.elements.chatInput.value.trim();

        if (!message) {
            return;
        }

        if (!this.isConnected) {
            UiUtils.showMessage('网络连接已断开，请检查网络后重试', 'error');
            return;
        }

        if (this.isTyping) {
            UiUtils.showMessage('AI正在回复中，请稍候', 'warning');
            return;
        }

        // 创建用户消息
        const userMessage = {
            id: this.generateMessageId(),
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        };

        // 添加消息到列表
        this.addMessage(userMessage);

        // 清空输入框
        this.elements.chatInput.value = '';
        this.autoResizeTextarea();

        // 隐藏空状态
        this.hideEmptyState();

        // 发送消息到服务器
        await this.sendMessageToServer(userMessage);
    }

    /**
     * 发送消息到服务器
     */
    async sendMessageToServer(userMessage) {
        try {
            this.setTypingState(true);

            const requestData = {
                messages: this.messages,
                model: this.options.model,
                stream: this.options.stream,
                temperature: this.options.temperature,
                max_tokens: this.options.max_tokens,
                sender_id: 'web_user',
                sender_nickname: 'Web用户',
                platform: 'web'
            };

            if (this.options.stream) {
                await this.handleStreamResponse(requestData);
            } else {
                await this.handleNormalResponse(requestData);
            }

        } catch (error) {
            console.error('Send message failed:', error);
            this.handleSendError(error);
        } finally {
            this.setTypingState(false);
        }
    }

    /**
     * 处理流式响应
     */
    async handleStreamResponse(requestData) {
        let assistantMessage = null;
        let accumulatedContent = '';

        try {
            const response = await fetch(CHAT_CONFIG.STREAM_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer EMPTY'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    break;
                }

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);

                        if (data === '[DONE]') {
                            continue;
                        }

                        try {
                            const parsed = JSON.parse(data);
                            const content = parsed.choices?.[0]?.delta?.content;

                            if (content) {
                                accumulatedContent += content;

                                if (!assistantMessage) {
                                    assistantMessage = {
                                        id: this.generateMessageId(),
                                        role: 'assistant',
                                        content: '',
                                        timestamp: new Date().toISOString()
                                    };
                                    this.addMessage(assistantMessage);
                                }

                                assistantMessage.content = accumulatedContent;
                                this.updateMessage(assistantMessage);
                            }
                        } catch (parseError) {
                            console.warn('Failed to parse SSE data:', parseError);
                        }
                    }
                }
            }

            // 保存完整消息
            if (assistantMessage) {
                this.saveChatHistory();
            }

        } catch (error) {
            console.error('Stream response error:', error);
            throw error;
        }
    }

    /**
     * 处理普通响应
     */
    async handleNormalResponse(requestData) {
        try {
            const response = await fetch(CHAT_CONFIG.API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer EMPTY'
                },
                body: JSON.stringify({ ...requestData, stream: false })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            const content = data.choices?.[0]?.message?.content || '';

            if (content) {
                const assistantMessage = {
                    id: this.generateMessageId(),
                    role: 'assistant',
                    content: content,
                    timestamp: new Date().toISOString()
                };

                this.addMessage(assistantMessage);
                this.saveChatHistory();
            }

        } catch (error) {
            console.error('Normal response error:', error);
            throw error;
        }
    }

    /**
     * 处理发送错误
     */
    handleSendError(error) {
        let errorMessage = '发送消息失败，请重试';

        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            errorMessage = '网络连接失败，请检查网络设置';
        } else if (error.message.includes('timeout')) {
            errorMessage = '请求超时，请稍后重试';
        }

        UiUtils.showMessage(errorMessage, 'error');

        // 添加错误消息
        const errorAssistantMessage = {
            id: this.generateMessageId(),
            role: 'assistant',
            content: errorMessage,
            timestamp: new Date().toISOString(),
            isError: true
        };

        this.addMessage(errorAssistantMessage);
    }

    /**
     * 添加消息到聊天界面
     */
    addMessage(message) {
        this.messages.push(message);
        this.renderMessage(message);
        this.scrollToBottom();
    }

    /**
     * 更新消息内容（用于流式响应）
     */
    updateMessage(message) {
        const messageElement = document.getElementById(`message-${message.id}`);
        if (messageElement) {
            const textElement = messageElement.querySelector('.message-text');
            if (textElement) {
                textElement.innerHTML = this.formatMessageContent(message.content);
            }
            this.scrollToBottom();
        }
    }

    /**
     * 渲染所有消息
     */
    renderMessages() {
        this.elements.chatMessages.innerHTML = '';

        // 重新添加空状态和输入提示
        this.elements.chatMessages.appendChild(this.elements.emptyState);
        this.elements.chatMessages.appendChild(this.elements.typingIndicator);

        if (this.messages.length === 0) {
            this.showEmptyState();
        } else {
            this.hideEmptyState();
            this.messages.forEach(message => this.renderMessage(message));
            this.scrollToBottom();
        }
    }

    /**
     * 渲染单个消息
     */
    renderMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = `message-item ${message.role}`;
        messageElement.id = `message-${message.id}`;

        const avatar = document.createElement('div');
        avatar.className = `message-avatar ${message.role}`;
        avatar.innerHTML = message.role === 'user' ?
            '<i class="fa fa-user"></i>' :
            '<i class="fa fa-robot"></i>';

        const content = document.createElement('div');
        content.className = 'message-content';

        const text = document.createElement('div');
        text.className = 'message-text';
        text.innerHTML = this.formatMessageContent(message.content);

        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = this.formatTime(message.timestamp);

        content.appendChild(text);
        content.appendChild(time);

        messageElement.appendChild(avatar);
        messageElement.appendChild(content);

        // 插入到输入提示之前
        this.elements.chatMessages.insertBefore(
            messageElement,
            this.elements.typingIndicator
        );
    }

    /**
     * 格式化消息内容
     */
    formatMessageContent(content) {
        if (!content) return '';

        // 转义HTML
        const escapedContent = ContentProcessor.escapeHtml(content);

        // 如果启用了Markdown渲染
        if (window.ContentProcessor && ContentProcessor.renderMarkdown) {
            try {
                return ContentProcessor.renderMarkdown(escapedContent);
            } catch (error) {
                console.warn('Markdown rendering failed:', error);
                return escapedContent.replace(/\n/g, '<br>');
            }
        }

        return escapedContent.replace(/\n/g, '<br>');
    }

    /**
     * 设置输入状态
     */
    setTypingState(isTyping) {
        this.isTyping = isTyping;
        this.elements.sendButton.disabled = isTyping;
        this.elements.chatInput.disabled = isTyping;

        if (isTyping) {
            this.elements.typingIndicator.style.display = 'flex';
            this.scrollToBottom();
        } else {
            this.elements.typingIndicator.style.display = 'none';
        }
    }

    /**
     * 显示空状态
     */
    showEmptyState() {
        this.elements.emptyState.style.display = 'block';
    }

    /**
     * 隐藏空状态
     */
    hideEmptyState() {
        this.elements.emptyState.style.display = 'none';
    }

    /**
     * 自动调整文本框高度
     */
    autoResizeTextarea() {
        const textarea = this.elements.chatInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    /**
     * 滚动到底部
     */
    scrollToBottom() {
        setTimeout(() => {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }, CHAT_CONFIG.AUTO_SCROLL_DELAY);
    }

    /**
     * 生成消息ID
     */
    generateMessageId() {
        return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 格式化时间
     */
    formatTime(timestamp) {
        if (!timestamp) return '';

        try {
            const date = new Date(timestamp);
            return date.toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (error) {
            return '';
        }
    }

    /**
     * 清理资源
     */
    cleanup() {
        // 取消正在进行的流式请求
        if (this.currentStreamController) {
            this.currentStreamController.abort();
            this.currentStreamController = null;
        }

        // 保存聊天历史
        this.saveChatHistory();

        // 清理事件监听器
        this.elements.sendButton.removeEventListener('click', this.handleSendMessage);
        this.elements.chatInput.removeEventListener('keydown', this.handleSendMessage);
        this.elements.chatInput.removeEventListener('input', this.autoResizeTextarea);
    }

    /**
     * 重置聊天
     */
    resetChat() {
        if (confirm('确定要清空所有聊天记录吗？')) {
            this.messages = [];
            this.renderMessages();
            localStorage.removeItem('chatHistory');
            UiUtils.showMessage('聊天记录已清空', 'success');
        }
    }

    /**
     * 切换流式/非流式模式
     */
    toggleStreamMode() {
        this.options.stream = !this.options.stream;
        const mode = this.options.stream ? '流式' : '普通';
        UiUtils.showMessage(`已切换到${mode}模式`, 'success');
    }

    /**
     * 导出聊天记录
     */
    exportChatHistory() {
        if (this.messages.length === 0) {
            UiUtils.showMessage('没有可导出的聊天记录', 'warning');
            return;
        }

        try {
            const dataStr = JSON.stringify(this.messages, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);

            const link = document.createElement('a');
            link.href = url;
            link.download = `chat_history_${new Date().toISOString().split('T')[0]}.json`;
            link.click();

            URL.revokeObjectURL(url);
            UiUtils.showMessage('聊天记录已导出', 'success');
        } catch (error) {
            console.error('Export failed:', error);
            UiUtils.showMessage('导出失败，请重试', 'error');
        }
    }

    /**
     * 处理开启新会话
     */
    handleNewChat() {
        if (this.messages.length === 0) {
            return; // 已经是新会话，无需处理
        }

        // 保存当前会话到历史记录
        this.saveChatHistory();

        // 清空当前消息
        this.messages = [];

        // 重新渲染界面
        this.renderMessages();

        // 重置会话状态
        this.isTyping = false;
        this.currentStreamController = null;

        // 聚焦到输入框
        this.elements.chatInput.focus();
    }
}

// 导出控制器
window.ChatController = ChatController;

// 全局函数，供调试使用
window.chatDebug = {
    toggleStream: () => {
        if (window.chatController) {
            window.chatController.toggleStreamMode();
        }
    },
    exportHistory: () => {
        if (window.chatController) {
            window.chatController.exportChatHistory();
        }
    },
    newChat: () => {
        if (window.chatController) {
            window.chatController.handleNewChat();
        }
    },
    getStatus: () => {
        if (window.chatController) {
            return {
                messageCount: window.chatController.messages.length,
                isConnected: window.chatController.isConnected,
                isTyping: window.chatController.isTyping,
                streamMode: window.chatController.options.stream
            };
        }
        return null;
    }
};