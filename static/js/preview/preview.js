/**
 * 已回复预览列表页面控制器
 */

class ApprovedPreviewsManager {
    constructor() {
        this.table = null;
        this.layui = null;
        this.searchTimeout = null;
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

            // 最后初始化表格（避免重复查询）
            this.initializeTable();

            // 设置初始化完成标志
            this.isInitialized = true;

        } catch (error) {
            console.error('Failed to initialize ApprovedPreviewsManager:', error);
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
            elem: '#previewsTable',
            url: '/api/preview/list',
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
                none: '暂无已回复记录'
            },
            cols: [[
                {field: 'sender_nickname', title: '发起用户', width: 150, sort: true, templet: '#userInfoTpl'},
                {field: 'platform', title: '平台', width: 100, templet: '#platformTpl'},
                {field: 'last_user_message', title: '请求内容', width: 200, templet: d => {
                    return this.truncateText(d.last_user_message || d.current_request || '无', 30);
                }},
                {field: 'saved_content', title: '回复内容',  templet: d => {
                    return this.truncateText(d.saved_content || '无', 50);
                }},
                {field: 'response_time', title: '响应时间', width: 100, align: 'center', templet: '#responseTimeTpl'},
                {field: 'created_at', title: '创建时间', width: 150, sort: true, templet: '#createTimeTpl'},
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
        this.layui.table.on('tool(previewsTable)', (obj) => {
            if (obj.event === 'view') {
                this.viewPreviewDetail(obj.data);
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

            // 监听搜索框变化
            document.getElementById('searchKeyword')?.addEventListener('input', (e) => {
                const formData = this.layui.form.val('filterForm');
                // 使用防抖避免频繁请求
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.table.reload({
                        where: formData
                    });
                }, 500);
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
            const response = await ApiService.apiRequest('/api/users/unique');
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

    applyFilter() {
        const userFilter = document.getElementById('userFilter');
        const dateRangeFilter = document.getElementById('dateRangeFilter');
        const searchInput = document.getElementById('searchInput');

        this.currentFilter = {
            user_nick: userFilter ? (userFilter.value || '').trim() : '',
            date_range: dateRangeFilter ? dateRangeFilter.value : 'all',
            search: searchInput ? (searchInput.value || '').trim() : ''
        };

        console.log('Calling reloadData from applyFilter'); this.reloadData();
    }

    resetFilter() {
        const userFilter = document.getElementById('userFilter');
        const dateRangeFilter = document.getElementById('dateRangeFilter');
        const searchInput = document.getElementById('searchInput');

        if (userFilter) userFilter.value = '';
        if (dateRangeFilter) dateRangeFilter.value = 'all';
        if (searchInput) searchInput.value = '';

        this.currentFilter = {
            user_nick: '',
            date_range: 'all',
            search: ''
        };

        if (this.layui && this.layui.form) {
            this.layui.form.render();
        }

        console.log('Calling reloadData from resetFilter'); this.reloadData();
    }

    reloadData() {
        if (!this.table || this.isReloading) return;

        // 添加调用栈调试
        const stack = new Error().stack;
        console.log('reloadData called from:', stack.split('\n')[1]?.trim());

        // 创建筛选状态的hash来检查是否有实际变化
        const currentFilterHash = JSON.stringify(this.currentFilter);
        if (this.lastFilterHash === currentFilterHash) {
            console.log('Filter unchanged, skipping reload');
            return;
        }
        this.lastFilterHash = currentFilterHash;

        this.isReloading = true;

        // 构建查询参数
        const where = {};
        if (this.currentFilter.user_nick && this.currentFilter.user_nick.trim() !== '') {
            where.user_nick = this.currentFilter.user_nick;
        }
        if (this.currentFilter.date_range !== 'all') {
            where.date_range = this.currentFilter.date_range;
        }
        if (this.currentFilter.search && this.currentFilter.search.trim() !== '') {
            where.search = this.currentFilter.search;
        }

        // 添加调试日志
        console.log('Reloading data with filter:', this.currentFilter);
        console.log('Where clause for table reload:', where);

        // 重新加载表格数据
        this.table.reload({
            where: where,
            page: {
                curr: 1
            },
            done: () => {
                // 重置加载标志
                this.isReloading = false;
                console.log('Table reload completed');
            }
        });
    }

    viewPreviewDetail(previewData) {
        if (!this.layui || !this.layui.layer) {
            window.open(`/api/preview/${previewData.preview_id}`, '_blank');
            return;
        }

        // 创建详情内容
        const messages = previewData.messages || [];
        let messagesHtml = '';

        if (Array.isArray(messages)) {
            messages.forEach(msg => {
                const roleClass = msg.role === 'user' ? 'user-message' : 'assistant-message';
                const roleIcon = msg.role === 'user' ? 'fa-user' : 'fa-robot';
                const roleName = msg.role === 'user' ? '用户' : '助手';

                messagesHtml += `
                    <div class="message-item ${roleClass}">
                        <div class="message-header">
                            <i class="fas ${roleIcon}"></i>
                            <span class="message-role">${roleName}</span>
                        </div>
                        <div class="message-content">${this.escapeHtml(msg.content || '')}</div>
                    </div>
                `;
            });
        }

        const content = `
            <div class="preview-detail-content">
                <div class="detail-section">
                    <h3><i class="fas fa-info-circle"></i> 基本信息</h3>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>预览ID:</label>
                            <span>${previewData.preview_id || ''}</span>
                        </div>
                        <div class="detail-item">
                            <label>发起用户:</label>
                            <span>${previewData.sender_nickname || ''}</span>
                        </div>
                        <div class="detail-item">
                            <label>用户ID:</label>
                            <span>${previewData.sender_id || ''}</span>
                        </div>
                        <div class="detail-item">
                            <label>平台:</label>
                            <span>${previewData.platform || ''}</span>
                        </div>
                        <div class="detail-item">
                            <label>响应时间:</label>
                            <span>${previewData.response_time ? previewData.response_time + 's' : '未知'}</span>
                        </div>
                        <div class="detail-item">
                            <label>创建时间:</label>
                            <span>${previewData.created_at || ''}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h3><i class="fas fa-reply"></i> 回复内容</h3>
                    <div class="response-content">
                        ${this.escapeHtml(previewData.saved_content || '无回复内容')}
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
            title: '预览详情',
            area: ['80%', '80%'],
            shadeClose: true,
            shade: 0.8,
            content: content,
            success: function(layero, index) {
                // 添加样式
                const style = document.createElement('style');
                style.textContent = `
                    .preview-detail-content {
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
                    .message-content {
                        line-height: 1.6;
                        white-space: pre-wrap;
                    }
                    .response-content {
                        background: #f8f9fa;
                        padding: 15px;
                        border-radius: 8px;
                        line-height: 1.6;
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
    }

    
    truncateText(text, maxLength) {
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
    window.approvedManager = new ApprovedPreviewsManager();
});