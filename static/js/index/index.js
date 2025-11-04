/**
 * Any4Chat 预览页面主控制器
 */

// 全局变量
let currentPreviewId = null;
let previewPollingInterval = null;
let previews = [];
let layer = null;

// DOM 元素引用
const elements = {
    previewList: null,
    previewDetail: null,
    approvedCount: null,
    timeoutCount: null,
    conversationCount: null,
    conversationStats: null,
    emptyState: null,
    editorContainer: null,
    contentEditor: null,
    contentPreview: null
};

// 初始化函数
function initializeApp() {
    // 初始化 marked
    if (typeof ContentProcessor !== 'undefined') {
        ContentProcessor.setupMarked();
    }

    // 获取 DOM 元素
    initializeElements();

    // 设置事件监听器
    setupEventListeners();

    // 开始轮询预览数据
    startPreviewPolling();

    // 初始化编辑器
    setTimeout(initializeEditor, 100);

    // 开始统计更新轮询
    startStatsPolling();

    // 设置页面生命周期监听器
    setupLifecycleListeners();
}

// 初始化 DOM 元素
function initializeElements() {
    elements.previewList = document.getElementById('previewList');
    elements.previewDetail = document.getElementById('previewDetail');
    elements.approvedCount = document.getElementById('approvedCount');
    elements.approvedStats = document.getElementById('approvedStats');
    elements.timeoutCount = document.getElementById('timeoutCount');
    elements.timeoutStats = document.getElementById('timeoutStats');
    elements.conversationCount = document.getElementById('conversationCount');
    elements.conversationStats = document.getElementById('conversationStats');
    elements.emptyState = document.getElementById('emptyState');
    elements.editorContainer = document.getElementById('editorContainer');
    elements.contentEditor = document.getElementById('contentEditor');
    elements.contentPreview = document.getElementById('contentPreview');

    // 为已回复统计添加点击事件
    if (elements.approvedStats) {
        elements.approvedStats.style.cursor = 'pointer';
        elements.approvedStats.addEventListener('click', () => {
            window.open('/preview', '_blank');
        });

        // 添加悬停提示
        elements.approvedStats.title = '点击查看已回复列表';
    }

    // 为超时响应统计添加点击事件
    if (elements.timeoutStats) {
        elements.timeoutStats.style.cursor = 'pointer';
        elements.timeoutStats.addEventListener('click', () => {
            window.open('/timeout', '_blank');
        });

        // 添加悬停提示
        elements.timeoutStats.title = '点击查看超时响应列表';
    }

    // 为全部会话统计添加点击事件
    if (elements.conversationStats) {
        elements.conversationStats.style.cursor = 'pointer';
        elements.conversationStats.addEventListener('click', () => {
            window.open('/conversations', '_blank');
        });

        // 添加悬停提示
        elements.conversationStats.title = '点击查看全部会话列表';
    }
}

// 设置事件监听器
function setupEventListeners() {
    // 这里可以添加全局事件监听器
    window.addEventListener('resize', () => {
        // 响应式处理
    });
}

// 设置页面生命周期监听器
function setupLifecycleListeners() {
    // 页面卸载时停止轮询
    window.addEventListener('beforeunload', function() {
        stopPreviewPolling();
        stopStatsPolling();
    });

    // 页面可见性变化时控制轮询
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            stopPreviewPolling();
            stopStatsPolling();
        } else {
            startPreviewPolling();
            startStatsPolling();
        }
    });
}

// 轮询预览数据
async function pollPreviewData() {
    try {
        if (typeof ApiService === 'undefined') {
            console.error('ApiService not available');
            return;
        }

        const data = await ApiService.fetchPendingPreviews();
        previews = Array.isArray(data) ? data : (data.previews || []);

        // 更新数据管理器
        if (typeof previewDataManager !== 'undefined') {
            previewDataManager.setPreviews(previews);
        }

        if (previews.length > 0) {
            renderPreviewList();
            updateStats();

            // 检查当前预览是否还存在
            if (currentPreviewId && !previews.find(p => p.preview_id === currentPreviewId)) {
                currentPreviewId = null;
                renderPreviewDetail(null);
            }
        } else {
            renderPreviewList();
            updateStats();
        }
    } catch (error) {
        console.error('数据获取失败:', error);
        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage('数据获取失败', 'error');
        }
    }
}

// 开始预览轮询
function startPreviewPolling() {
    if (previewPollingInterval) {
        clearInterval(previewPollingInterval);
    }
    previewPollingInterval = setInterval(pollPreviewData, 3000);
    pollPreviewData();
}

// 停止预览轮询
function stopPreviewPolling() {
    if (previewPollingInterval) {
        clearInterval(previewPollingInterval);
        previewPollingInterval = null;
    }
}

// 统计轮询间隔
let statsPollingInterval = null;

// 开始统计轮询
function startStatsPolling() {
    if (statsPollingInterval) {
        clearInterval(statsPollingInterval);
    }
    statsPollingInterval = setInterval(updateStats, 5000); // 每5秒更新一次统计
    updateStats(); // 立即执行一次
}

// 停止统计轮询
function stopStatsPolling() {
    if (statsPollingInterval) {
        clearInterval(statsPollingInterval);
        statsPollingInterval = null;
    }
}

// 渲染预览列表
function renderPreviewList() {
    if (!elements.previewList) return;

    if (previews.length === 0) {
        if (typeof UiUtils !== 'undefined') {
            elements.previewList.innerHTML = UiUtils.createEmptyState('inbox', '暂无待预览内容');
        } else {
            elements.previewList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>暂无待预览内容</p>
                </div>
            `;
        }
        return;
    }

    let html = '';
    previews.forEach(preview => {
        const isActive = preview.preview_id === currentPreviewId;
        const previewTime = typeof ContentProcessor !== 'undefined' ?
            ContentProcessor.formatTime(preview.timestamp) :
            new Date(preview.timestamp || Date.now()).toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit'
            });

        let lastUserMessage = '无内容';
        const messages = preview.request_data?.messages;
        if (messages && Array.isArray(messages)) {
            for (let i = messages.length - 1; i >= 0; i--) {
                if (messages[i].role === 'user') {
                    lastUserMessage = messages[i].content || '无内容';
                    break;
                }
            }
        }

        let previewContent = preview.generated_content || '等待响应...';
        if (typeof ContentProcessor !== 'undefined') {
            previewContent = ContentProcessor.removeThinkContent(previewContent);
            previewContent = ContentProcessor.truncateText(previewContent, 100);
        } else {
            // 简单的截取处理
            if (previewContent.length > 100) {
                previewContent = previewContent.substring(0, 100) + '...';
            }
        }

        html += `
            <div class="preview-item ${isActive ? 'active' : ''}" data-id="${preview.preview_id}">
                <div class="preview-item-header">
                    <div class="preview-item-title">${lastUserMessage}</div>
                    <div class="preview-item-time">${previewTime}</div>
                </div>
                <div class="preview-item-content">${previewContent}</div>
            </div>
        `;
    });

    elements.previewList.innerHTML = html;

    // 添加点击事件监听器
    document.querySelectorAll('.preview-item').forEach(item => {
        item.addEventListener('click', function() {
            const previewId = this.getAttribute('data-id');
            selectPreviewItem(previewId);
        });
    });
}

// 选择预览项
function selectPreviewItem(previewId) {
    currentPreviewId = previewId;
    renderPreviewList();
    const selectedPreview = previews.find(p => p.preview_id === previewId);
    renderPreviewDetail(selectedPreview);
}

// 渲染预览详情
function renderPreviewDetail(preview) {
    if (!elements.previewDetail) return;

    if (!preview) {
        if (elements.emptyState) elements.emptyState.style.display = 'flex';
        if (elements.editorContainer) elements.editorContainer.style.display = 'none';
        const previewContent = document.getElementById('previewContent');
        if (previewContent) previewContent.style.display = 'none';
        return;
    }

    if (elements.emptyState) elements.emptyState.style.display = 'none';
    if (elements.editorContainer) elements.editorContainer.style.display = 'none';

    let previewContent = document.getElementById('previewContent');
    if (!previewContent) {
        previewContent = document.createElement('div');
        previewContent.id = 'previewContent';
        elements.previewDetail.appendChild(previewContent);
    }

    previewContent.style.display = 'block';

    const requestData = preview.request_data || {};
    const responseContent = preview.generated_content || "等待响应...";

    let lastUserQuestion = '无问题';
    const messages = requestData.messages;
    if (messages && Array.isArray(messages)) {
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].role === 'user') {
                lastUserQuestion = messages[i].content || '无问题';
                break;
            }
        }
    }

    let lastAssistantMessage = null;
    if (messages && Array.isArray(messages)) {
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].role === 'assistant') {
                lastAssistantMessage = messages[i];
                break;
            }
        }
    }

    const renderedResponse = typeof ContentProcessor !== 'undefined' ?
        `<div class="markdown-body">${ContentProcessor.renderMarkdown(responseContent)}</div>` : responseContent;

    previewContent.innerHTML = `
        <div class="preview-section">
            <h3><i class="fas fa-question-circle"></i> 当前问题</h3>
            <div class="preview-request">${lastUserQuestion}</div>
        </div>

        <div class="preview-section">
            <h3><i class="fas fa-paper-plane"></i> 会话历史</h3>
            <div class="request-table-container">
                <table class="request-table">
                    <thead>
                        <tr>
                            <th>用户消息</th>
                            <th>助手回复</th>
                        </tr>
                    </thead>
                    <tbody id="requestTableBody">
                        <tr><td colspan="2" class="loading-state">加载中...</td></tr>
                    </tbody>
                </table>
                <button class="table-toggle-btn" id="toggleRequestTable">
                    <i class="fas fa-chevron-down"></i> 显示更多
                </button>
            </div>
        </div>
        <div class="preview-section">
            <h3><i class="fas fa-robot"></i> AI响应</h3>
            <div class="preview-response">${renderedResponse}</div>
        </div>

        <div class="preview-actions">
            ${lastAssistantMessage && lastAssistantMessage.is_timeout === 1 ?
                `<button class="layui-btn layui-btn-warm" id="confirmTimeoutBtn">
                    <i class="fas fa-warning"></i> 确认超时回复
                </button>` :
                `<button class="layui-btn layui-btn-normal" id="editBtn">
                    <i class="fas fa-edit"></i> 编辑
                </button>
                <button class="layui-btn layui-btn-primary" id="confirmBtnDetail">
                    <i class="fas fa-check"></i> 确认发送
                </button>`
            }
        </div>`;

    // 绑定按钮事件
    const editBtn = document.getElementById('editBtn');
    const confirmBtnDetail = document.getElementById('confirmBtnDetail');
    const confirmTimeoutBtn = document.getElementById('confirmTimeoutBtn');

    if (editBtn) editBtn.onclick = () => startEditMode(preview);
    if (confirmBtnDetail) confirmBtnDetail.onclick = () => confirmPreview(preview.preview_id);
    if (confirmTimeoutBtn) confirmTimeoutBtn.onclick = handleTimeoutConfirm;

    // 加载会话历史
    const conversationId = requestData.conversation_id;
    if (conversationId) {
        loadConversationHistory(conversationId);
    } else {
        const tableBody = document.getElementById('requestTableBody');
        if (tableBody) {
            tableBody.innerHTML = '<tr><td colspan="2" class="empty-state">无对话历史</td></tr>';
        }
    }
}

// 加载会话历史
async function loadConversationHistory(conversationId) {
    try {
        if (typeof ApiService === 'undefined') {
            console.error('ApiService not available');
            return;
        }

        const data = await ApiService.fetchConversationMessages(conversationId);

        if (data.success) {
            const reversedMessages = [...data.messages].reverse();
            renderConversationMessages(reversedMessages);
            updateButtonsByTimeoutStatus(data.messages);
        } else {
            const tableBody = document.getElementById('requestTableBody');
            if (tableBody) {
                tableBody.innerHTML = '<tr><td colspan="2" class="error-state">加载失败</td></tr>';
            }
        }
    } catch (error) {
        const tableBody = document.getElementById('requestTableBody');
        if (tableBody) {
            tableBody.innerHTML = '<tr><td colspan="2" class="error-state">网络错误</td></tr>';
        }
    }
}

// 渲染会话消息
function renderConversationMessages(messages) {
    const tableBody = document.getElementById('requestTableBody');
    if (!tableBody) return;

    if (!messages || messages.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="2" class="empty-state">无对话消息</td></tr>';
        return;
    }

    const pairs = [];
    let currentPair = null;

    for (let j = 0; j < messages.length; j++) {
        const msg = messages[j];

        if (msg.sender_type === 'user') {
            if (currentPair) pairs.push(currentPair);
            currentPair = { user: msg, assistant: null };
        } else if (msg.sender_type === 'assistant' && currentPair) {
            currentPair.assistant = msg;
            pairs.push(currentPair);
            currentPair = null;
        }
    }

    if (currentPair) pairs.push(currentPair);

    tableBody.innerHTML = '';

    const assistantMessages = pairs.map(pair => pair.assistant ? pair.assistant.content : '');

    for (let k = 0; k < pairs.length; k++) {
        const pair = pairs[k];
        const row = document.createElement('tr');
        row.className = 'message-pair';
        row.setAttribute('data-row-index', k.toString());

        const userCell = document.createElement('td');
        userCell.className = 'user-message';
        if (pair.user && pair.user.content) {
            if (typeof ContentProcessor !== 'undefined') {
                userCell.innerHTML = ContentProcessor.escapeHtml(pair.user.content);
            } else {
                userCell.textContent = pair.user.content;
            }
        }

        const assistantCell = document.createElement('td');
        assistantCell.className = 'assistant-message';

        if (k === 0) {
            assistantCell.innerHTML = '待确认回复...';
        } else {
            const previousAssistantContent = assistantMessages[k - 1];
            if (previousAssistantContent) {
                if (typeof ContentProcessor !== 'undefined') {
                    assistantCell.innerHTML = ContentProcessor.escapeHtml(previousAssistantContent);
                } else {
                    assistantCell.textContent = previousAssistantContent;
                }
            }
        }

        row.appendChild(userCell);
        row.appendChild(assistantCell);
        tableBody.appendChild(row);
    }

    setupTableToggle();
}

// 设置表格切换功能
function setupTableToggle() {
    const toggleBtn = document.getElementById('toggleRequestTable');
    const tableBody = document.getElementById('requestTableBody');

    if (toggleBtn && tableBody) {
        let isExpanded = false;
        const rows = tableBody.querySelectorAll('tr.message-pair');

        if (rows.length > 3) {
            for (let i = 3; i < rows.length; i++) rows[i].style.display = 'none';
            toggleBtn.style.display = 'block';
        } else {
            toggleBtn.style.display = 'none';
        }

        toggleBtn.addEventListener('click', function() {
            isExpanded = !isExpanded;

            if (isExpanded) {
                for (let i = 1; i < rows.length; i++) rows[i].style.display = '';
                toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> 收起';
            } else {
                for (let i = 3; i < rows.length; i++) rows[i].style.display = 'none';
                toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> 显示更多';
            }
        });
    }
}

// 根据超时状态更新按钮
function updateButtonsByTimeoutStatus(messages) {
    if (!messages || !Array.isArray(messages)) return;

    let lastAssistantMessage = null;
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].sender_type === 'assistant') {
            lastAssistantMessage = messages[i];
            break;
        }
    }

    if (lastAssistantMessage && lastAssistantMessage.is_timeout === 1) {
        const previewActions = document.querySelector('.preview-actions');
        if (previewActions) {
            previewActions.innerHTML = `
                <button class="layui-btn layui-btn-warm" id="confirmTimeoutBtn">
                    <i class="fas fa-warning"></i> 确认超时回复
                </button>
            `;

            const confirmTimeoutBtn = document.getElementById('confirmTimeoutBtn');
            if (confirmTimeoutBtn) confirmTimeoutBtn.onclick = handleTimeoutConfirm;
        }
    }
}

// 开始编辑模式
function startEditMode(preview) {
    if (!elements.emptyState || !elements.editorContainer || !elements.contentEditor || !elements.contentPreview) {
        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage('编辑器初始化失败', 'error');
        }
        return;
    }

    try {
        currentPreviewId = preview.preview_id;

        if (elements.emptyState) elements.emptyState.style.display = 'none';
        const previewContent = document.getElementById('previewContent');
        if (previewContent) previewContent.style.display = 'none';
        elements.editorContainer.style.display = 'flex';

        elements.contentEditor.value = preview.generated_content || '';

        if (typeof ContentProcessor !== 'undefined') {
            elements.contentPreview.innerHTML = `<div class="markdown-body">${ContentProcessor.renderMarkdown(elements.contentEditor.value)}</div>`;
        } else {
            elements.contentPreview.textContent = elements.contentEditor.value;
        }

        setTimeout(() => elements.contentEditor.focus(), 100);
    } catch (error) {
        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage('编辑模式启动失败', 'error');
        }
    }
}

// 确认预览
async function confirmPreview(previewId) {
    try {
        const preview = previews.find(p => p.preview_id === previewId);
        if (!preview) throw new Error('未找到预览数据');

        const requestBody = {
            sender_id: preview.sender_id || preview.user_id || '',
            sender_name: preview.sender_name || preview.username || '',
            original_content: preview.original_content || '',
            request_id: preview.request_id || preview.preview_id
        };

        if (typeof ApiService === 'undefined') {
            throw new Error('ApiService not available');
        }

        const response = await ApiService.confirmPreview(previewId, requestBody);

        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage('内容已发送', 'success');
        }
        pollPreviewData();
    } catch (error) {
        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage('发送失败', 'error');
        }
    }
}

// 处理超时确认
function handleTimeoutConfirm() {
    if (typeof UiUtils !== 'undefined') {
        UiUtils.showMessage('已确认超时回复', 'success');
    }

    if (currentPreviewId) {
        const index = previews.findIndex(p => p.preview_id === currentPreviewId);
        if (index !== -1) previews.splice(index, 1);

        currentPreviewId = null;
        renderPreviewList();
        updateStats();

        if (elements.emptyState) elements.emptyState.style.display = 'flex';
        const previewContent = document.getElementById('previewContent');
        if (previewContent) previewContent.style.display = 'none';
        if (elements.editorContainer) elements.editorContainer.style.display = 'none';
    }

    setTimeout(pollPreviewData, 200);
}

// 更新统计信息
async function updateStats() {
    try {
        // 更新已回复数量
        if (elements.approvedCount) {
            try {
                if (typeof ApiService !== 'undefined') {
                    const result = await ApiService.getApprovedStats();
                    elements.approvedCount.textContent = result.count || 0;
                } else {
                    elements.approvedCount.textContent = '0';
                }
            } catch (error) {
                console.error('Failed to update approved stats:', error);
                elements.approvedCount.textContent = '0';
            }
        }

        // 更新超时响应数量
        if (elements.timeoutCount) {
            try {
                if (typeof previewDataManager !== 'undefined' && previewDataManager.loadTimeoutStats) {
                    const timeoutStats = await previewDataManager.loadTimeoutStats();
                    elements.timeoutCount.textContent = timeoutStats.timeoutCount || 0;
                } else if (typeof ApiService !== 'undefined') {
                    const result = await ApiService.getTimeoutStats();
                    elements.timeoutCount.textContent = result.count || 0;
                } else {
                    elements.timeoutCount.textContent = '0';
                }
            } catch (error) {
                console.error('Failed to update timeout stats:', error);
                elements.timeoutCount.textContent = '0';
            }
        }

        // 更新会话总数
        if (elements.conversationCount) {
            try {
                if (typeof ApiService !== 'undefined') {
                    const result = await ApiService.getConversationStats();
                    elements.conversationCount.textContent = result.count || 0;
                } else {
                    elements.conversationCount.textContent = '0';
                }
            } catch (error) {
                console.error('Failed to update conversation stats:', error);
                elements.conversationCount.textContent = '0';
            }
        }
    } catch (error) {
        console.error('Failed to update stats:', error);
    }
}

// 初始化编辑器
function initializeEditor() {
    const saveAndSendBtn = document.getElementById('saveAndSendBtn');
    const cancelBtn = document.getElementById('cancelBtn');

    if (!elements.contentEditor || !elements.contentPreview || !saveAndSendBtn || !cancelBtn) {
        setTimeout(initializeEditor, 100);
        return;
    }

    // 编辑器输入事件
    elements.contentEditor.addEventListener('input', function() {
        if (typeof ContentProcessor !== 'undefined') {
            elements.contentPreview.innerHTML = `<div class="markdown-body">${ContentProcessor.renderMarkdown(this.value)}</div>`;
        } else {
            elements.contentPreview.textContent = this.value;
        }
    });

    // 保存并发送按钮事件
    saveAndSendBtn.addEventListener('click', async function() {
        if (!currentPreviewId) return;

        try {
            const preview = previews.find(p => p.preview_id === currentPreviewId);
            if (!preview) throw new Error('未找到预览数据');

            const additionalFields = {
                sender_id: preview.sender_id || preview.user_id || '',
                sender_name: preview.sender_name || preview.username || '',
                original_content: preview.original_content || '',
                request_id: preview.request_id || preview.preview_id
            };

            if (typeof ApiService === 'undefined') {
                throw new Error('ApiService not available');
            }

            // 保存内容
            await ApiService.savePreviewContent(currentPreviewId, elements.contentEditor.value, additionalFields);

            // 确认发送
            await ApiService.confirmPreview(currentPreviewId, additionalFields);

            if (typeof UiUtils !== 'undefined') {
                UiUtils.showMessage('内容已发送', 'success');
            }

            if (elements.editorContainer) elements.editorContainer.style.display = 'none';
            if (elements.emptyState) elements.emptyState.style.display = 'flex';
            pollPreviewData();
        } catch (error) {
            if (typeof UiUtils !== 'undefined') {
                UiUtils.showMessage('发送失败', 'error');
            }
        }
    });

    // 取消按钮事件
    cancelBtn.addEventListener('click', function() {
        if (elements.editorContainer) elements.editorContainer.style.display = 'none';

        if (currentPreviewId) {
            const selectedPreview = previews.find(p => p.preview_id === currentPreviewId);
            if (selectedPreview) {
                renderPreviewDetail(selectedPreview);
            } else {
                if (elements.emptyState) elements.emptyState.style.display = 'flex';
                const previewContent = document.getElementById('previewContent');
                if (previewContent) previewContent.style.display = 'none';
            }
        } else {
            if (elements.emptyState) elements.emptyState.style.display = 'flex';
            const previewContent = document.getElementById('previewContent');
            if (previewContent) previewContent.style.display = 'none';
        }
    });
}

// 导出函数供其他脚本使用
window.Any4Chat = {
    initializeApp,
    selectPreviewItem,
    confirmPreview,
    renderPreviewDetail,
    pollPreviewData,
    startPreviewPolling,
    stopPreviewPolling
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 如果使用了 layui，等待 layui 加载完成
    if (typeof layui !== 'undefined') {
        layui.use(['layer', 'form'], function(){
            layer = layui.layer;
            initializeApp();
        });
    } else {
        initializeApp();
    }
});