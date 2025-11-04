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

// 获取当前用户信息
async function getCurrentUser() {
    return await apiRequest('/api/chat/current-user', {
        method: 'GET'
    });
}

// 创建新对话
async function createConversation(senderId, senderNickname, platform) {
    return await apiRequest('/api/conversation/create', {
        method: 'POST',
        body: JSON.stringify({
            sender_id: senderId,
            sender_nickname: senderNickname,
            platform: platform
        })
    });
}

// 获取用户会话列表
async function getUserConversations(platform = 'any4chat', limit = 20, offset = 0) {
    return await apiRequest('/api/conversations', {
        method: 'POST',
        body: JSON.stringify({
            platform: platform,
            limit: limit,
            offset: offset
        })
    });
}

// 获取用户的最新会话
async function getLatestConversation() {
    return await apiRequest('/api/chat/latest-conversation', {
        method: 'GET'
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

// 获取超时统计数据
async function getTimeoutStats(sender = null, platform = null) {
    let url = '/api/stats/timeout';
    const params = new URLSearchParams();

    if (sender) params.append('sender', sender);
    if (platform) params.append('platform', platform);

    if (params.toString()) {
        url += '?' + params.toString();
    }

    return await apiRequest(url);
}

// 获取已回复统计数据
async function getApprovedStats(sender = null, platform = null) {
    let url = '/api/preview/stats';
    const params = new URLSearchParams();

    if (sender) params.append('sender', sender);
    if (platform) params.append('platform', platform);

    if (params.toString()) {
        url += '?' + params.toString();
    }

    return await apiRequest(url);
}

// 获取会话统计数据
async function getConversationStats(user_nick = null, platform = null, date_range = null) {
    let url = '/api/conversations/stats';
    const params = new URLSearchParams();

    if (user_nick) params.append('user_nick', user_nick);
    if (platform) params.append('platform', platform);
    if (date_range) params.append('date_range', date_range);

    if (params.toString()) {
        url += '?' + params.toString();
    }

    return await apiRequest(url);
}

// 获取会话列表
async function getConversationsList(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    let url = '/api/conversations/list';
    if (queryString) {
        url += '?' + queryString;
    }
    return await apiRequest(url);
}

// 获取会话详情
async function getConversationDetail(conversationId) {
    return await apiRequest(`/api/conversations/detail/${conversationId}`);
}

// 导出函数
window.ApiService = {
    apiRequest,
    fetchPendingPreviews,
    fetchConversationMessages,
    confirmPreview,
    savePreviewContent,
    login,
    getCurrentUser,
    createConversation,
    getUserConversations,
    getLatestConversation,
    queryDatabase,
    getTimeoutStats,
    getApprovedStats,
    getConversationStats,
    getConversationsList,
    getConversationDetail
};