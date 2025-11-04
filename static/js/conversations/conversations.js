/**
 * 全部会话列表页面控制器
 */

class ConversationsManager {
    constructor() {
        this.table = null;
        this.layui = null;
        this.isInitialized = false; // 防止初始化时触发事件
        this.initialize();
    }

    async initialize() {
        try {
            // 初始化layui
            await this.initializeLayui();

            // 绑定事件
            this.bindEvents();

            // 初始化layui表单
            if (this.layui && this.layui.form) {
                this.layui.form.render();
            }

            // 加载用户列表
            await this.loadUsers();

            // 加载平台列表
            await this.loadPlatforms();

            // 最后初始化表格（避免重复查询）
            this.initializeTable();

            // 设置初始化完成标志
            this.isInitialized = true;

        } catch (error) {
            console.error('Failed to initialize ConversationsManager:', error);
            this.showError('页面初始化失败: ' + error.message);
        }
    }

    async initializeLayui() {
        return new Promise((resolve) => {
            if (typeof layui !== 'undefined') {
                layui.use(['table', 'form', 'layer', 'util'], () => {
                    this.layui = layui;
                    resolve();
                });
            } else {
                console.error('Layui not loaded');
                resolve();
            }
        });
    }

    initializeTable() {
        if (!this.layui) return;

        this.table = this.layui.table.render({
            elem: '#conversationTable',
            url: '/api/conversations/list',
            method: 'get',
            toolbar: '#tableToolbar',
            defaultToolbar: ['exports', 'print'],
            page: true,
            limit: 20,
            limits: [10, 20, 50, 100],
            parseData: (res) => {
                // 适配后端返回的数据格式到Layui标准格式
                return {
                    "code": res.error ? 1 : 0,
                    "msg": res.error || 'success',
                    "count": res.total || 0,
                    "data": res.data || []
                };
            },
            text: {
                none: '暂无会话记录'
            },
            cols: [[
                {field: 'user_nick', title: '用户昵称', width: 150, sort: true, templet: '#userInfoTpl'},
                {field: 'platform', title: '平台', width: 100, templet: '#platformTpl'},
                {field: 'last_user_message', title: '最新用户请求', width: 200, templet: d => {
                    const text = d.last_user_message || '无';
                    const truncated = this.truncateText(text, 50);
                    return `<div class="last-message user-message" title="${this.escapeHtml(text)}">${this.escapeHtml(truncated)}</div>`;
                }},
                {field: 'last_assistant_message', title: '最新助手响应', templet: d => {
                    const text = d.last_assistant_message || '无';
                    const truncated = this.truncateText(text, 50);
                    return `<div class="last-message assistant-message" title="${this.escapeHtml(text)}">${this.escapeHtml(truncated)}</div>`;
                }},
                {field: 'message_count', title: '消息数量', width: 100, templet: '#messageCountTpl', align: 'center'},
                {field: 'created_time', title: '创建时间', width: 150, sort: true, templet: '#createTimeTpl'},
                {field: 'last_active', title: '最后活跃', width: 150, sort: true, templet: '#lastActiveTpl'},
                {title: '操作', width: 80, align: 'center', toolbar: '#tableOperations', fixed: 'right'}
            ]],
            done: (res) => {
                // 更新总记录数显示
                const totalCountEl = document.getElementById('totalCount');
                if (totalCountEl) {
                    totalCountEl.textContent = res.count || 0;
                }
            }
        });

        // 监听表格工具条事件
        this.layui.table.on('tool(conversationTable)', (obj) => {
            if (obj.event === 'view') {
                this.viewConversationDetail(obj.data);
            }
        });
    }

    bindEvents() {
        // 使用事件委托处理动态渲染的按钮
        document.addEventListener('click', (e) => {
            const target = e.target;

            // 处理返回按钮
            if (target.id === 'backBtn' || target.closest('#backBtn')) {
                window.location.href = '/index';
                return;
            }

            // 处理刷新按钮
            if (target.id === 'refreshBtn' || target.closest('#refreshBtn')) {
                this.table.reload();
                return;
            }
        });

        // 使用Layui标准的表单监听
        if (this.layui && this.layui.form) {
            // 监听表单提交
            this.layui.form.on('submit(filterSubmit)', (data) => {
                // 将表单数据传递给表格进行筛选
                this.table.reload({
                    where: data.field
                });
                return false; // 阻止默认提交
            });

            // 监听用户筛选变化
            this.layui.form.on('select(userNick)', () => {
                if (!this.isInitialized) return;
                // 获取当前表单所有数据
                const formData = this.layui.form.val('filterForm');
                // 重新加载表格并传递筛选参数
                this.table.reload({
                    where: formData
                });
            });

            // 监听平台筛选变化
            this.layui.form.on('select(platform)', () => {
                if (!this.isInitialized) return;
                // 获取当前表单所有数据
                const formData = this.layui.form.val('filterForm');
                // 重新加载表格并传递筛选参数
                this.table.reload({
                    where: formData
                });
            });

            // 监听时间范围筛选变化
            this.layui.form.on('select(dateRange)', () => {
                if (!this.isInitialized) return;
                // 获取当前表单所有数据
                const formData = this.layui.form.val('filterForm');
                // 重新加载表格并传递筛选参数
                this.table.reload({
                    where: formData
                });
            });

            // 监听表单重置
            document.getElementById('filterForm')?.addEventListener('reset', () => {
                // 重置后立即重新加载表格，清除所有筛选条件
                this.table.reload({
                    where: {} // 清空筛选条件
                });
            });
        }
    }

    async loadUsers() {
        try {
            const response = await ApiService.apiRequest('/api/conversations/users');
            if (response.users && Array.isArray(response.users)) {
                const userFilter = document.getElementById('userNick');
                if (userFilter && this.layui && this.layui.form) {
                    // 更新下拉框选项
                    let options = '<option value="">全部用户</option>';
                    response.users.forEach(user => {
                        options += `<option value="${user}">${user}</option>`;
                    });
                    userFilter.innerHTML = options;

                    // 重新渲染表单，但不触发事件
                    this.layui.form.render('select');
                }
            }
        } catch (error) {
            console.error('Failed to load users:', error);
        }
    }

    async loadPlatforms() {
        try {
            const response = await ApiService.apiRequest('/api/conversations/platforms');
            if (response.platforms && Array.isArray(response.platforms)) {
                const platformFilter = document.getElementById('platform');
                if (platformFilter && this.layui && this.layui.form) {
                    // 更新下拉框选项
                    let options = '<option value="">全部平台</option>';
                    response.platforms.forEach(platform => {
                        options += `<option value="${platform}">${platform}</option>`;
                    });
                    platformFilter.innerHTML = options;

                    // 重新渲染表单，但不触发事件
                    this.layui.form.render('select');
                }
            }
        } catch (error) {
            console.error('Failed to load platforms:', error);
        }
    }

    async viewConversationDetail(conversationData) {
        if (!this.layui || !this.layui.layer) {
            window.open(`/api/conversations/detail/${conversationData.conversation_id}`, '_blank');
            return;
        }

        try {
            // 获取详细信息
            const response = await ApiService.apiRequest(`/api/conversations/detail/${conversationData.conversation_id}`);

            if (!response.success) {
                this.showError('获取详情失败: ' + response.error);
                return;
            }

            const detail = response.data;
            const conversation = detail.conversation || {};
            const messages = detail.messages || [];

            let messagesHtml = '';

            if (Array.isArray(messages)) {
                messages.forEach(msg => {
                    const roleClass = msg.sender_type === 'user' ? 'user-message' : 'assistant-message';
                    const roleIcon = msg.sender_type === 'user' ? 'fa-user' : 'fa-robot';
                    const roleName = msg.sender_type === 'user' ? '用户' : '助手';

                    messagesHtml += `
                        <div class="message-item ${roleClass}">
                            <div class="message-header">
                                <i class="fas ${roleIcon}"></i>
                                <span class="message-role">${roleName}</span>
                                ${msg.is_timeout === 1 ? '<span class="timeout-badge">超时响应</span>' : ''}
                            </div>
                            <div class="message-content">${this.escapeHtml(msg.content || '')}</div>
                            <div class="message-time">${msg.timestamp_formatted || msg.timestamp}</div>
                        </div>
                    `;
                });
            }

            const content = `
                <div class="conversation-detail-content">
                    <div class="detail-section">
                        <h3><i class="fas fa-info-circle"></i> 基本信息</h3>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <label>会话ID:</label>
                                <span>${conversation.conversation_id || ''}</span>
                            </div>
                            <div class="detail-item">
                                <label>用户昵称:</label>
                                <span>${conversation.user_nick || ''}</span>
                            </div>
                            <div class="detail-item">
                                <label>用户ID:</label>
                                <span>${conversation.sender || ''}</span>
                            </div>
                            <div class="detail-item">
                                <label>平台:</label>
                                <span>${conversation.platform || ''}</span>
                            </div>
                            <div class="detail-item">
                                <label>消息数量:</label>
                                <span>${conversation.message_count || 0}</span>
                            </div>
                            <div class="detail-item">
                                <label>创建时间:</label>
                                <span>${conversation.created_at_formatted || conversation.created_time}</span>
                            </div>
                            <div class="detail-item">
                                <label>最后活跃:</label>
                                <span>${conversation.last_active_formatted || conversation.last_active}</span>
                            </div>
                        </div>
                    </div>

                    <div class="detail-section">
                        <h3><i class="fas fa-comments"></i> 对话记录</h3>
                        <div class="messages-container">
                            ${messagesHtml || '<p class="no-messages">暂无对话记录</p>'}
                        </div>
                    </div>
                </div>
            `;

            this.layui.layer.open({
                type: 1,
                title: '会话详情',
                area: ['80%', '80%'],
                shadeClose: true,
                shade: 0.8,
                content: content,
                success: function(layero, index) {
                    // 添加样式
                    const style = document.createElement('style');
                    style.textContent = `
                        .conversation-detail-content {
                            padding: 20px;
                            max-height: 70vh;
                            overflow-y: auto;
                        }
                        .detail-section {
                            margin-bottom: 25px;
                        }
                        .detail-section h3 {
                            color: #16baaa;
                            margin-bottom: 15px;
                            font-size: 16px;
                            border-bottom: 2px solid #f0f0f0;
                            padding-bottom: 8px;
                        }
                        .detail-grid {
                            display: grid;
                            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                            gap: 15px;
                        }
                        .detail-item {
                            display: flex;
                            align-items: center;
                        }
                        .detail-item label {
                            font-weight: 600;
                            color: #666;
                            min-width: 80px;
                            margin-right: 10px;
                        }
                        .messages-container {
                            border: 1px solid #eee;
                            border-radius: 8px;
                            padding: 15px;
                            background: #fafafa;
                        }
                        .message-item {
                            margin-bottom: 15px;
                            padding: 12px;
                            border-radius: 8px;
                        }
                        .message-item.user-message {
                            background: #e3f2fd;
                            margin-left: 20px;
                        }
                        .message-item.assistant-message {
                            background: #f3e5f5;
                            margin-right: 20px;
                        }
                        .message-header {
                            display: flex;
                            align-items: center;
                            margin-bottom: 8px;
                            font-weight: 600;
                            color: #333;
                        }
                        .message-header i {
                            margin-right: 8px;
                        }
                        .message-role {
                            margin-right: 10px;
                        }
                        .message-content {
                            line-height: 1.6;
                            white-space: pre-wrap;
                            margin-bottom: 8px;
                        }
                        .message-time {
                            font-size: 12px;
                            color: #999;
                            text-align: right;
                            margin-top: 4px;
                        }
                        .timeout-badge {
                            background: #ff9800;
                            color: white;
                            padding: 2px 6px;
                            border-radius: 3px;
                            font-size: 10px;
                            margin-left: 8px;
                        }
                        .message-content {
                            line-height: 1.6;
                            white-space: pre-wrap;
                        }
                        .no-messages {
                            text-align: center;
                            color: #999;
                            font-style: italic;
                            padding: 20px;
                        }
                    `;
                    document.head.appendChild(style);
                }
            });

        } catch (error) {
            console.error('Failed to load conversation detail:', error);
            this.showError('加载详情失败: ' + error.message);
        }
    }

    truncateText(text, maxLength = 50) {
        if (!text) return '无';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showSuccess(message) {
        if (this.layui && this.layui.layer) {
            this.layui.layer.msg(message, {icon: 1});
        } else {
            alert(message);
        }
    }

    showError(message) {
        if (this.layui && this.layui.layer) {
            this.layui.layer.msg(message, {icon: 2});
        } else {
            alert('错误: ' + message);
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    window.conversationsManager = new ConversationsManager();
});