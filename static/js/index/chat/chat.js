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
        this.isTyping = false;
        this.currentStreamController = null;
        this.isPreviewMode = false;
        this.isDelayMode = false;
        this.delayTime = 3;
        this.isToolsEnabled = false;

        // 用户信息
        this.currentUser = null;

        // 会话信息
        this.currentConversationId = null;

        // 历史记录
        this.conversationHistory = [];
        this.currentHistoryPage = 0;
        this.historyPageSize = 20;
        this.isLoadingHistory = false;

        // 本地存储
        this.storageKey = 'any4chat_current_conversation';

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
    async initialize() {
        this.initializeElements();
        await this.getCurrentUserInfo();
        await this.loadConversationHistory(); 
        await this.initializeConversation();
        await this.checkPreviewMode();
        await this.checkDelayMode();
        await this.checkToolsEnabled();
        this.setupEventListeners();
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
            newChatBtn: document.getElementById('newChatBtn'),
            historyList: document.getElementById('historyList'),
            historyLoading: document.getElementById('historyLoading'),
            historyEmpty: document.getElementById('historyEmpty'),
            conversationHistory: document.getElementById('conversationHistory')
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

        // 更新预览模式状态显示
        const previewModeStatus = document.getElementById('previewModeStatus');
        if (previewModeStatus) {
            if (this.isPreviewMode) {
                previewModeStatus.style.display = 'flex';
            } else {
                previewModeStatus.style.display = 'none';
            }
        }

        // 更新延迟模式状态显示
        const delayModeStatus = document.getElementById('delayModeStatus');
        const delayModeBadge = document.getElementById('delayModeBadge');
        if (delayModeStatus && delayModeBadge) {
            if (this.isDelayMode) {
                delayModeStatus.style.display = 'flex';
                delayModeBadge.textContent = `${this.delayTime}s`;
                delayModeBadge.title = `延迟模式已启用，消息将在${this.delayTime}秒后合并处理`;
            } else {
                delayModeStatus.style.display = 'none';
            }
        }

        // 更新工具系统状态显示
        const toolsStatus = document.getElementById('toolsStatus');
        if (toolsStatus) {
            if (this.isToolsEnabled) {
                toolsStatus.style.display = 'flex';
            } else {
                toolsStatus.style.display = 'none';
            }
        }

        // 流式模式切换
        const streamModeToggle = document.getElementById('streamModeToggle');
        if (streamModeToggle) {
            // 初始化开关状态
            streamModeToggle.checked = this.options.stream;

            // 预览模式下禁用流式开关
            if (this.isPreviewMode) {
                streamModeToggle.disabled = true;
                streamModeToggle.checked = false;

                // 添加预览模式提示
                const toggleContainer = streamModeToggle.parentElement;
                if (toggleContainer) {
                    const previewModeHint = document.createElement('span');
                    previewModeHint.className = 'preview-mode-hint';
                    previewModeHint.textContent = ' (预览模式已禁用)';
                    previewModeHint.style.cssText = 'color: #6b7280; font-size: 12px; margin-left: 8px;';
                    toggleContainer.appendChild(previewModeHint);
                }
            }

            streamModeToggle.addEventListener('change', (e) => {
                // 预览模式下阻止切换
                if (this.isPreviewMode) {
                    e.target.checked = false;
                    return;
                }

                this.options.stream = e.target.checked;
                // 不显示切换提示，保持界面简洁
            });
        }

        
        // 页面关闭前清理
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });

        // 延迟模式下添加连续发送提示
        if (this.isDelayMode) {
            const chatInput = this.elements.chatInput;
            if (chatInput) {
                // 添加输入提示
                const originalPlaceholder = chatInput.placeholder || '请输入您的问题...';
                chatInput.placeholder = `${originalPlaceholder} (可连续发送多条消息)`;
            }
        }

        // 错误处理
        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e);
            if (typeof UiUtils !== 'undefined' && UiUtils.showMessage) {
                UiUtils.showMessage('发生未知错误，请刷新页面重试', 'error');
            } else {
                showMessage('发生未知错误，请刷新页面重试', 'error');
            }
        });
    }

    
    /**
     * 检测预览模式状态
     */
    async checkPreviewMode() {
        try {
            const response = await fetch('/api/chat/config/preview-mode', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const data = await response.json();
                this.isPreviewMode = data.preview_mode === true;

                // 如果预览模式启用，强制禁用流式模式
                if (this.isPreviewMode) {
                    this.options.stream = false;
                }
            } else {
                console.warn('Failed to check preview mode status');
                this.isPreviewMode = false;
            }
        } catch (error) {
            console.warn('Failed to check preview mode:', error);
            this.isPreviewMode = false;
        }
    }

    /**
     * 检测延迟模式状态
     */
    async checkDelayMode() {
        try {
            const response = await fetch('/api/chat/config/delay-mode', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const data = await response.json();
                this.isDelayMode = data.delay_mode === true;
                this.delayTime = data.delay_time || 3;
            } else {
                console.warn('Failed to check delay mode status');
                this.isDelayMode = false;
                this.delayTime = 3;
            }
        } catch (error) {
            console.warn('Failed to check delay mode:', error);
            this.isDelayMode = false;
            this.delayTime = 3;
        }
    }

    /**
     * 检测工具系统状态
     */
    async checkToolsEnabled() {
        try {
            const response = await fetch('/api/chat/config/tools-enabled', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const data = await response.json();
                this.isToolsEnabled = data.tools_enabled === true;
            } else {
                console.warn('Failed to check tools enabled status');
                this.isToolsEnabled = false;
            }
        } catch (error) {
            console.warn('Failed to check tools enabled:', error);
            this.isToolsEnabled = false;
        }
    }

    /**
     * 获取当前用户信息
     */
    async getCurrentUserInfo() {
        try {
            if (typeof ApiService !== 'undefined' && ApiService.getCurrentUser) {
                const result = await ApiService.getCurrentUser();
                if (result && result.success) {
                    this.currentUser = {
                        username: result.username,
                        nickname: result.nickname,
                        user_id: result.user_id
                    };
                } else {
                    console.warn('Failed to get current user info:', result?.message || 'Unknown error');
                    this.currentUser = null;
                }
            } else {
                // 如果ApiService不可用，直接使用fetch
                const response = await fetch('/api/chat/current-user', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        this.currentUser = {
                            username: data.username,
                            nickname: data.nickname,
                            user_id: data.user_id
                        };
                    }
                } else {
                    console.warn('Failed to get current user info, status:', response.status);
                    this.currentUser = null;
                }
            }
        } catch (error) {
            console.warn('Failed to get current user info:', error);
            this.currentUser = null;
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
        if (this.isTyping && !this.isDelayMode) {
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
            // 延迟模式下允许连续发送
            if (!this.isDelayMode) {
                this.setTypingState(true);
            }

            // 预览模式下强制使用非流式响应
            const shouldUseStream = this.options.stream && !this.isPreviewMode;

            const requestData = {
                messages: this.messages,
                model: this.options.model,
                stream: shouldUseStream,
                temperature: this.options.temperature,
                max_tokens: this.options.max_tokens,
                sender_id: this.currentUser?.username || 'web_user',
                sender_nickname: this.currentUser?.nickname || 'Web用户',
                platform: 'any4chat',
                delay_time: this.isDelayMode ? this.delayTime : undefined
            };

            
            if (shouldUseStream) {
                await this.handleStreamResponse(requestData);
            } else {
                await this.handleNormalResponse(requestData);
            }

        } catch (error) {
            console.error('Send message failed:', error);
            this.handleSendError(error);
        } finally {
            if (!this.isDelayMode) {
                this.setTypingState(false);
            }
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

                            if (content && content.trim()) {
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

            // 处理延迟模式下的特殊响应
            if (data.delay_processing) {
                return;
            }

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

        this.showMessage(errorMessage, 'error');

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
                let formattedContent = this.formatMessageContent(message.content);

                if (typeof formattedContent !== 'string') {
                    console.warn('updateMessage: formattedContent is not a string:', typeof formattedContent, formattedContent);
                    formattedContent = String(formattedContent || '');
                }

                if (message.role === 'assistant' && formattedContent) {
                    const pTagMatch = formattedContent.match(/^<p>([\s\S]*?)<\/p>$/);
                    if (pTagMatch) {
                        formattedContent = pTagMatch[1];
                    }
                }

                textElement.innerHTML = formattedContent;
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
        text.className = message.role === 'assistant' ? 'message-text markdown-body' : 'message-text';

        let formattedContent = this.formatMessageContent(message.content);

        if (typeof formattedContent !== 'string') {
            console.warn('formattedContent is not a string:', typeof formattedContent, formattedContent);
            formattedContent = String(formattedContent || '');
        }

        if (message.role === 'assistant' && formattedContent) {
            // 如果整个内容被包裹在单个p标签中，移除它
            const pTagMatch = formattedContent.match(/^<p>([\s\S]*?)<\/p>$/);
            if (pTagMatch) {
                formattedContent = pTagMatch[1];
            }
        }

        text.innerHTML = formattedContent;

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
        // 确保输入是字符串
        if (content === null || content === undefined) {
            return '';
        }

        if (typeof content === 'object') {
            console.warn('formatMessageContent received object:', content);
            try {
                return JSON.stringify(content, null, 2);
            } catch (e) {
                return '[Object conversion failed]';
            }
        }

        if (typeof content !== 'string') {
            content = String(content);
        }

        if (window.ContentProcessor && ContentProcessor.renderMarkdown) {
            try {
                let result = ContentProcessor.renderMarkdown(content);
                if (typeof result !== 'string') {
                    console.warn('ContentProcessor.renderMarkdown returned non-string:', typeof result, result);
                    result = String(result || '');
                }
                return result;
            } catch (error) {
                console.warn('Markdown rendering failed:', error);
                if (window.ContentProcessor && ContentProcessor.escapeHtml) {
                    return ContentProcessor.escapeHtml(content).replace(/\n/g, '<br>');
                }
                return content.replace(/\n/g, '<br>');
            }
        }

        if (window.ContentProcessor && ContentProcessor.escapeHtml) {
            return ContentProcessor.escapeHtml(content).replace(/\n/g, '<br>');
        }

        return content.replace(/\n/g, '<br>');
    }

    /**
     * 设置输入状态
     */
    setTypingState(isTyping) {
        this.isTyping = isTyping;

        // 延迟模式下不禁用输入框和发送按钮
        if (!this.isDelayMode) {
            this.elements.sendButton.disabled = isTyping;
            this.elements.chatInput.disabled = isTyping;
        }

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
     * 显示消息
     */
    showMessage(message, type = 'info', duration = 2000) {
        if (typeof showMessage === 'function') {
            showMessage(message, type, duration);
        } else if (typeof UiUtils !== 'undefined' && UiUtils.showMessage) {
            UiUtils.showMessage(message, type, duration);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
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
            this.showMessage('聊天记录已清空', 'success');
        }
    }

    /**
     * 切换流式/非流式模式
     */
    toggleStreamMode() {
        // 预览模式下阻止切换
        if (this.isPreviewMode) {
            return;
        }

        this.options.stream = !this.options.stream;
    }

    /**
     * 导出聊天记录
     */
    exportChatHistory() {
        if (this.messages.length === 0) {
            this.showMessage('没有可导出的聊天记录', 'warning');
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
            this.showMessage('聊天记录已导出', 'success');
        } catch (error) {
            console.error('Export failed:', error);
            this.showMessage('导出失败，请重试', 'error');
        }
    }

    /**
     * 处理开启新会话
     */
    async handleNewChat() {
        try {
            // 创建新会话
            const response = await this.createNewConversation();
            if (response && response.conversation_id) {
                this.currentConversationId = response.conversation_id;

                this.messages = [];
                this.renderMessages();

                this.isTyping = false;
                this.currentStreamController = null;

                this.elements.chatInput.focus();

                // 重新加载历史记录以更新列表
                await this.loadConversationHistory();
            }
        } catch (error) {
            console.error('Failed to create new conversation:', error);
        }
    }

    /**
     * 初始化会话（恢复现有会话或创建新会话）
     */
    async initializeConversation() {
        try {
            // 首先尝试恢复用户最新的会话
            let response;

            if (typeof ApiService !== 'undefined' && ApiService.getLatestConversation) {
                response = await ApiService.getLatestConversation();
            } else {
                // 降级处理：直接使用fetch
                const fetchResponse = await fetch('/api/chat/latest-conversation', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (fetchResponse.ok) {
                    response = await fetchResponse.json();
                } else {
                    throw new Error(`HTTP ${fetchResponse.status}: ${fetchResponse.statusText}`);
                }
            }

            if (response && response.success && response.conversation_id) {
                // 成功恢复现有会话
                this.currentConversationId = response.conversation_id;

                // 转换消息格式以适配前端渲染逻辑
                this.messages = (response.messages || []).map(msg => ({
                    id: msg.message_id || `msg-${msg.sequence_number}`,
                    role: msg.role || msg.sender_type, // 兼容处理两种字段名
                    content: msg.content,
                    timestamp: msg.timestamp
                }));

                // 保存到本地存储
                this.saveConversationToStorage();

                // 渲染恢复的消息
                this.renderMessages();

                // 如果有消息，隐藏空状态
                if (this.messages.length > 0) {
                    this.hideEmptyState();
                }

            } else {
                // 没有现有会话，创建新会话
                console.log('No existing conversation found, creating new one...');
                await this.createNewConversation();
            }
        } catch (error) {
            console.error('Failed to initialize conversation:', error);
            // 降级处理：直接创建新会话
            await this.createNewConversation();
        }
    }

    /**
     * 创建新会话（仅在需要时调用）
     */
    async createNewConversation() {
        try {
            if (typeof ApiService !== 'undefined' && ApiService.createConversation) {
                const result = await ApiService.createConversation(
                    this.currentUser?.username || 'web_user',
                    this.currentUser?.nickname || 'Web用户',
                    'any4chat'
                );
                return result;
            } else {
                // 降级处理：直接使用fetch
                const response = await fetch('/api/conversation/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sender_id: this.currentUser?.username || 'web_user',
                        sender_nickname: this.currentUser?.nickname || 'Web用户',
                        platform: 'any4chat'
                    })
                });

                if (response.ok) {
                    return await response.json();
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }
        } catch (error) {
            console.error('Error creating conversation:', error);
            throw error;
        }
    }

    /**
     * 保存会话信息到本地存储
     */
    saveConversationToStorage() {
        try {
            const conversationData = {
                conversationId: this.currentConversationId,
                timestamp: Date.now(),
                messageCount: this.messages.length
            };
            localStorage.setItem(this.storageKey, JSON.stringify(conversationData));
        } catch (error) {
            console.warn('Failed to save conversation to storage:', error);
        }
    }

    /**
     * 从本地存储获取会话信息
     */
    getConversationFromStorage() {
        try {
            const data = localStorage.getItem(this.storageKey);
            return data ? JSON.parse(data) : null;
        } catch (error) {
            console.warn('Failed to get conversation from storage:', error);
            return null;
        }
    }

    /**
     * 清理本地存储的会话信息
     */
    clearConversationFromStorage() {
        try {
            localStorage.removeItem(this.storageKey);
        } catch (error) {
            console.warn('Failed to clear conversation from storage:', error);
        }
    }

    /**
     * 加载用户历史记录
     */
    async loadConversationHistory() {
        if (this.isLoadingHistory) return;

        try {
            this.isLoadingHistory = true;
            this.showHistoryLoading(true);

            let response;

            // 使用ApiService，如果不可用则直接使用fetch
            if (typeof ApiService !== 'undefined' && ApiService.getUserConversations) {
                response = await ApiService.getUserConversations(
                    'any4chat',
                    this.historyPageSize,
                    this.currentHistoryPage * this.historyPageSize
                );
            } else {
                // 降级处理：直接使用fetch
                const fetchResponse = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        platform: 'any4chat',
                        limit: this.historyPageSize,
                        offset: this.currentHistoryPage * this.historyPageSize
                    })
                });

                if (fetchResponse.ok) {
                    response = await fetchResponse.json();
                } else {
                    throw new Error(`HTTP ${fetchResponse.status}: ${fetchResponse.statusText}`);
                }
            }

            if (response && response.success) {
                this.conversationHistory = response.conversations || [];
                this.renderConversationHistory();
            } else {
                console.warn('No success response from API:', response);
                this.showHistoryEmpty();
            }
        } catch (error) {
            console.error('Failed to load conversation history:', error);
            this.showHistoryEmpty();
        } finally {
            this.isLoadingHistory = false;
            this.showHistoryLoading(false);
        }
    }

    /**
     * 渲染历史记录列表
     */
    renderConversationHistory() {
        if (!this.elements.historyList) return;

        if (this.conversationHistory.length === 0) {
            this.showHistoryEmpty();
            return;
        }

        this.elements.historyList.innerHTML = '';

        this.conversationHistory.forEach(conversation => {
            const historyItem = this.createHistoryItem(conversation);
            this.elements.historyList.appendChild(historyItem);
        });
    }

    /**
     * 创建历史记录项
     */
    createHistoryItem(conversation) {
        const item = document.createElement('div');
        item.className = 'history-item';
        item.dataset.conversationId = conversation.conversation_id;

        // 如果是当前会话，添加active类
        if (conversation.conversation_id === this.currentConversationId) {
            item.classList.add('active');
        }

        // 格式化时间
        const timeStr = this.formatHistoryTime(conversation.last_active);

        // 获取第一条消息作为标题
        const title = conversation.first_message || '新对话';

        item.innerHTML = `
            <div class="history-item-title">${this.escapeHtml(title)}</div>
            <div class="history-item-meta">
                <span class="history-item-time">${timeStr}</span>
                <span class="history-item-count">${conversation.message_count || 0}</span>
            </div>
        `;

        // 点击事件
        item.addEventListener('click', () => {
            this.loadConversation(conversation.conversation_id);
        });

        return item;
    }

    /**
     * 加载指定会话
     */
    async loadConversation(conversationId) {
        if (conversationId === this.currentConversationId) {
            return; // 已经是当前会话
        }

        try {
            let response;

            // 使用ApiService，如果不可用则直接使用fetch
            if (typeof ApiService !== 'undefined' && ApiService.fetchConversationMessages) {
                response = await ApiService.fetchConversationMessages(conversationId);
            } else {
                // 降级处理：直接使用fetch
                const fetchResponse = await fetch(`/api/conversation/${conversationId}/history`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (fetchResponse.ok) {
                    response = await fetchResponse.json();
                } else {
                    throw new Error(`HTTP ${fetchResponse.status}: ${fetchResponse.statusText}`);
                }
            }

            if (response && response.success) {
                // 更新当前会话ID
                this.currentConversationId = conversationId;

                // 转换消息格式以适配前端渲染逻辑
                this.messages = (response.messages || []).map(msg => ({
                    id: msg.message_id || `msg-${msg.sequence_number}`,
                    role: msg.role || msg.sender_type, // 兼容处理两种字段名
                    content: msg.content,
                    timestamp: msg.timestamp
                }));
                this.renderMessages();

                // 更新历史记录的active状态
                this.updateHistoryActiveState(conversationId);

                // 滚动到底部
                this.scrollToBottom();

            } else {
                console.warn('No success response from conversation API:', response);
            }
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }

    /**
     * 更新历史记录的active状态
     */
    updateHistoryActiveState(conversationId) {
        const items = this.elements.historyList.querySelectorAll('.history-item');
        items.forEach(item => {
            if (item.dataset.conversationId === conversationId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    /**
     * 显示/隐藏加载状态
     */
    showHistoryLoading(show) {
        if (this.elements.historyLoading) {
            this.elements.historyLoading.style.display = show ? 'block' : 'none';
        }
        if (this.elements.historyEmpty) {
            this.elements.historyEmpty.style.display = 'none';
        }
        if (this.elements.historyList) {
            this.elements.historyList.style.display = show ? 'none' : 'block';
        }
    }

    /**
     * 显示空状态
     */
    showHistoryEmpty() {
        if (this.elements.historyEmpty) {
            this.elements.historyEmpty.style.display = 'block';
        }
        if (this.elements.historyLoading) {
            this.elements.historyLoading.style.display = 'none';
        }
        if (this.elements.historyList) {
            this.elements.historyList.style.display = 'none';
        }
    }

    /**
     * 格式化历史记录时间
     */
    formatHistoryTime(timestamp) {
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;

            if (diff < 24 * 60 * 60 * 1000) { // 24小时内
                return date.toLocaleTimeString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else if (diff < 7 * 24 * 60 * 60 * 1000) { // 7天内
                return date.toLocaleDateString('zh-CN', {
                    month: 'short',
                    day: 'numeric'
                });
            } else {
                return date.toLocaleDateString('zh-CN', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });
            }
        } catch (error) {
            return '';
        }
    }

    /**
     * HTML转义
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
                isTyping: window.chatController.isTyping,
                streamMode: window.chatController.options.stream,
                previewMode: window.chatController.isPreviewMode,
                delayMode: window.chatController.isDelayMode
            };
        }
        return null;
    }
};