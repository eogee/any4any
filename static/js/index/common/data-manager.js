/**
 * 数据管理相关公共函数
 */

// 数据状态管理
class DataManager {
    constructor() {
        this.data = new Map();
        this.subscribers = new Map();
    }

    // 设置数据
    set(key, value) {
        this.data.set(key, value);
        this.notifySubscribers(key, value);
    }

    // 获取数据
    get(key) {
        return this.data.get(key);
    }

    // 删除数据
    delete(key) {
        this.data.delete(key);
        this.notifySubscribers(key, undefined);
    }

    // 检查数据是否存在
    has(key) {
        return this.data.has(key);
    }

    // 订阅数据变化
    subscribe(key, callback) {
        if (!this.subscribers.has(key)) {
            this.subscribers.set(key, []);
        }
        this.subscribers.get(key).push(callback);
    }

    // 取消订阅
    unsubscribe(key, callback) {
        if (this.subscribers.has(key)) {
            const callbacks = this.subscribers.get(key);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    // 通知订阅者
    notifySubscribers(key, value) {
        if (this.subscribers.has(key)) {
            this.subscribers.get(key).forEach(callback => {
                try {
                    callback(value, key);
                } catch (error) {
                    console.error('Subscriber callback error:', error);
                }
            });
        }
    }

    // 清空所有数据
    clear() {
        this.data.clear();
        this.subscribers.clear();
    }
}

// 全局数据管理器实例
const dataManager = new DataManager();

// 预览数据管理
class PreviewDataManager {
    constructor() {
        this.previews = [];
        this.currentPreviewId = null;
        this.pollingInterval = null;
        this.isLoading = false;
    }

    // 设置预览数据
    setPreviews(previews) {
        this.previews = Array.isArray(previews) ? previews : [];
        dataManager.set('previews', this.previews);
    }

    // 获取预览数据
    getPreviews() {
        return this.previews;
    }

    // 设置当前预览ID
    setCurrentPreviewId(previewId) {
        this.currentPreviewId = previewId;
        dataManager.set('currentPreviewId', previewId);
    }

    // 获取当前预览ID
    getCurrentPreviewId() {
        return this.currentPreviewId;
    }

    // 根据ID获取预览项
    getPreviewById(previewId) {
        return this.previews.find(p => p.preview_id === previewId);
    }

    // 根据索引获取预览项
    getPreviewByIndex(index) {
        return this.previews[index];
    }

    // 添加预览项
    addPreview(preview) {
        this.previews.push(preview);
        dataManager.set('previews', this.previews);
    }

    // 删除预览项
    removePreview(previewId) {
        const index = this.previews.findIndex(p => p.preview_id === previewId);
        if (index > -1) {
            this.previews.splice(index, 1);
            dataManager.set('previews', this.previews);

            // 如果删除的是当前选中的预览项，清除当前选中
            if (this.currentPreviewId === previewId) {
                this.setCurrentPreviewId(null);
            }
        }
        return index > -1;
    }

    // 更新预览项
    updatePreview(previewId, updates) {
        const preview = this.getPreviewById(previewId);
        if (preview) {
            Object.assign(preview, updates);
            dataManager.set('previews', this.previews);
        }
        return preview;
    }

    // 获取待预览数量
    getPendingCount() {
        return this.previews.length;
    }

    // 获取已回复数量（模拟）
    getApprovedCount() {
        return Math.floor(this.previews.length * 0.7);
    }

    // 加载超时统计数据
    async loadTimeoutStats() {
        try {
            const result = await ApiService.getTimeoutStats();
            const timeoutCount = result.count || 0;
            dataManager.set('timeoutCount', timeoutCount);
            return { timeoutCount };
        } catch (error) {
            console.error('Failed to load timeout stats:', error);
            const timeoutCount = 0;
            dataManager.set('timeoutCount', timeoutCount);
            return { timeoutCount };
        }
    }

    // 设置加载状态
    setLoading(loading) {
        this.isLoading = loading;
        dataManager.set('previewLoading', loading);
    }

    // 获取加载状态
    getLoading() {
        return this.isLoading;
    }
}

// 会话数据管理
class ConversationDataManager {
    constructor() {
        this.conversations = new Map();
        this.currentConversationId = null;
    }

    // 设置会话消息
    setConversationMessages(conversationId, messages) {
        this.conversations.set(conversationId, messages);
        dataManager.set(`conversation_${conversationId}`, messages);
    }

    // 获取会话消息
    getConversationMessages(conversationId) {
        return this.conversations.get(conversationId) || [];
    }

    // 设置当前会话ID
    setCurrentConversationId(conversationId) {
        this.currentConversationId = conversationId;
        dataManager.set('currentConversationId', conversationId);
    }

    // 获取当前会话ID
    getCurrentConversationId() {
        return this.currentConversationId;
    }

    // 清除会话数据
    clearConversation(conversationId) {
        this.conversations.delete(conversationId);
        dataManager.delete(`conversation_${conversationId}`);
    }

    // 清除所有会话数据
    clearAllConversations() {
        this.conversations.clear();
        this.currentConversationId = null;
        dataManager.clear();
    }
}

// 创建实例
const previewDataManager = new PreviewDataManager();
const conversationDataManager = new ConversationDataManager();

// 导出管理器和实例
window.DataManager = DataManager;
window.dataManager = dataManager;
window.PreviewDataManager = PreviewDataManager;
window.previewDataManager = previewDataManager;
window.ConversationDataManager = ConversationDataManager;
window.conversationDataManager = conversationDataManager;