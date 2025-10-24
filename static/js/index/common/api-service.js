/**
 * API 请求相关公共函数
 */

// API 基础配置
const API_CONFIG = {
    baseURL: '',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
};

// 通用请求函数
async function apiRequest(url, options = {}) {
    const config = {
        ...API_CONFIG,
        ...options,
        headers: {
            ...API_CONFIG.headers,
            ...options.headers
        }
    };

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), config.timeout);

        const response = await fetch(url, {
            ...config,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('请求超时');
        }
        throw error;
    }
}

// 获取待预览数据
async function fetchPendingPreviews() {
    return await apiRequest('/api/pending-previews');
}

// 获取会话消息
async function fetchConversationMessages(conversationId) {
    return await apiRequest(`/api/conversation/${conversationId}/messages`);
}

// 确认预览
async function confirmPreview(previewId, requestBody) {
    return await apiRequest(`/v1/chat/confirm/${previewId}`, {
        method: 'POST',
        body: JSON.stringify(requestBody)
    });
}

// 保存预览内容
async function savePreviewContent(previewId, content, additionalFields = {}) {
    return await apiRequest(`/api/previews/${previewId}`, {
        method: 'PUT',
        body: JSON.stringify({ content, ...additionalFields })
    });
}

// 登录请求
async function login(username, password) {
    return await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
    });
}

// 数据库查询
async function queryDatabase(query) {
    const formData = new FormData();
    formData.append('query', query);

    return await apiRequest('/v1/db/query', {
        method: 'POST',
        headers: {}, // 让浏览器自动设置 Content-Type 为 multipart/form-data
        body: formData
    });
}

// 导出函数
window.ApiService = {
    apiRequest,
    fetchPendingPreviews,
    fetchConversationMessages,
    confirmPreview,
    savePreviewContent,
    login,
    queryDatabase
};