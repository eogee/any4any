/**
 * Dashboard JavaScript - 数字人交互界面
 * 依赖: LayUI 框架
 */

class DashboardController {
    constructor() {
        this.layer = null;
        this.form = null;
        this.element = null;

        // DOM元素
        this.sendBtn = null;
        this.messageText = null;
        this.connectionStatus = null;
        this.statusText = null;
        this.systemInfo = null;
        this.connectBtn = null;
        this.disconnectBtn = null;
        this.videoElement = null;
        this.placeholderMessage = null;

        // WebRTC相关
        this.pc = null;
        this.sessionId = null;
        this.isConnected = false;
        this.localStream = null;

        this.init();
    }

    /**
     * 初始化控制器
     */
    init() {
        // 等待LayUI加载完成
        if (typeof layui !== 'undefined') {
            layui.use(['layer', 'form', 'element'], () => {
                this.setupLayUI();
                this.bindElements();
                this.bindEvents();
                this.initializeUI();
            });
        } else {
            console.error('LayUI框架未加载');
        }
    }

    /**
     * 设置LayUI组件
     */
    setupLayUI() {
        this.layer = layui.layer;
        this.form = layui.form;
        this.element = layui.element;
    }

    /**
     * 绑定DOM元素
     */
    bindElements() {
        this.sendBtn = document.getElementById('sendMessage');
        this.messageText = document.getElementById('messageText');
        this.connectionStatus = document.getElementById('connection-status');
        this.statusText = document.getElementById('status-text');
        this.systemInfo = document.getElementById('system-info');
        this.connectBtn = document.getElementById('connectBtn');
        this.disconnectBtn = document.getElementById('disconnectBtn');
        this.videoElement = document.getElementById('videoElement');
        this.placeholderMessage = document.getElementById('placeholderMessage');

        if (!this.sendBtn || !this.messageText || !this.connectionStatus || !this.statusText || !this.systemInfo ||
            !this.connectBtn || !this.disconnectBtn || !this.videoElement || !this.placeholderMessage) {
            console.error('必要的DOM元素未找到');
            return false;
        }
        return true;
    }

    /**
     * 绑定事件监听器
     */
    bindEvents() {
        if (!this.sendBtn || !this.messageText || !this.connectBtn || !this.disconnectBtn) return;

        // 连接按钮点击事件
        this.connectBtn.addEventListener('click', () => {
            this.connect();
        });

        // 断开连接按钮点击事件
        this.disconnectBtn.addEventListener('click', () => {
            this.disconnect();
        });

        // 发送按钮点击事件
        this.sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });

        // 回车键发送消息
        this.messageText.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    /**
     * 初始化UI状态
     */
    initializeUI() {
        this.updateConnectionUI(false);
        this.messageText.focus();
    }

    /**
     * 更新连接状态显示
     * @param {boolean} connected - 连接状态
     */
    updateConnectionStatus(connected) {
        if (!this.connectionStatus || !this.statusText) return;

        if (connected) {
            this.connectionStatus.className = 'status-indicator status-connected';
            this.statusText.textContent = '已连接';
        } else {
            this.connectionStatus.className = 'status-indicator status-disconnected';
            this.statusText.textContent = '未连接';
        }
    }

    /**
     * 更新连接UI状态
     * @param {boolean} connected - 连接状态
     */
    updateConnectionUI(connected) {
        if (connected) {
            // 连接状态UI
            this.connectBtn.style.display = 'none';
            this.disconnectBtn.style.display = 'block';
            this.sendBtn.disabled = false;
            this.messageText.disabled = false;
            this.updateConnectionStatus(true);
        } else {
            // 断开连接状态UI
            this.connectBtn.style.display = 'block';
            this.disconnectBtn.style.display = 'none';
            this.sendBtn.disabled = true;
            this.messageText.disabled = true;
            this.updateConnectionStatus(false);
        }
    }

    /**
     * 连接到数字人
     */
    async connect() {
        if (this.isConnected) {
            this.showNotification('已经连接到服务器', 'info');
            return;
        }

        try {
            // 创建WebRTC连接（服务器会分配sessionid）
            await this.createWebRTCConnection();

            this.isConnected = true;
            this.updateConnectionUI(true);
            this.showNotification('连接成功', 'success');

        } catch (error) {
            console.error('连接失败:', error);
            this.showNotification(`连接失败: ${error.message}`, 'error');
            this.cleanup();
        }
    }

    /**
     * 断开连接
     */
    async disconnect() {
        if (!this.isConnected) {
            return;
        }

        try {
            this.cleanup();
            this.updateConnectionUI(false);
            this.showNotification('已断开连接', 'info');
        } catch (error) {
            console.error('断开连接失败:', error);
        }
    }

    /**
     * 创建WebRTC连接
     */
    async createWebRTCConnection() {
        // 创建RTCPeerConnection
        this.pc = new RTCPeerConnection({
            iceServers: [
                { urls: 'stun:stun.miwifi.com:3478' }
            ]
        });

        // 处理远程流
        this.pc.ontrack = (event) => {
            this.videoElement.srcObject = event.streams[0];
            this.videoElement.style.display = 'block';
            this.placeholderMessage.style.display = 'none';
        };

        // ICE candidate事件
        this.pc.onicecandidate = (event) => {
            if (event.candidate) {
                // ICE candidate 已收集
            }
        };

        // 添加本地媒体轨道以确保SDP包含媒体描述
        try {
            // 获取用户媒体（音频和视频）
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: true
            });

            // 添加所有轨道到PeerConnection
            this.localStream.getTracks().forEach(track => {
                this.pc.addTrack(track, this.localStream);
            });
        } catch (error) {
            console.warn('无法获取本地媒体，尝试添加空轨道:', error);

            // 如果无法获取本地媒体，创建空的媒体轨道
            try {
                const audioTrack = this.pc.addTransceiver('audio', {
                    direction: 'recvonly'
                });

                const videoTrack = this.pc.addTransceiver('video', {
                    direction: 'recvonly'
                });

                console.log('空媒体轨道已添加');
            } catch (transceiverError) {
                console.error('添加媒体轨道失败:', transceiverError);
                throw new Error('无法建立WebRTC连接');
            }
        }

        // 创建offer
        const offer = await this.pc.createOffer();
        await this.pc.setLocalDescription(offer);

        // 发送offer到服务器（前端生成的sessionid仅用于标识）
        const response = await fetch('/any4dh/offer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('服务器响应错误:', errorText);
            throw new Error(`WebRTC握手失败: ${response.status} ${errorText}`);
        }

        const data = await response.json();

        // 使用服务器返回的sessionid
        this.sessionId = data.sessionid;

        // 设置远程描述
        await this.pc.setRemoteDescription({
            sdp: data.sdp,
            type: data.type
        });
    }

    /**
     * 清理连接
     */
    cleanup() {
        // 停止本地媒体流
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => {
                track.stop();
            });
            this.localStream = null;
        }

        // 关闭WebRTC连接
        if (this.pc) {
            this.pc.close();
            this.pc = null;
        }

        // 清理视频显示
        this.videoElement.srcObject = null;
        this.videoElement.style.display = 'none';
        this.placeholderMessage.style.display = 'block';

        // 重置状态
        this.isConnected = false;
        this.sessionId = null;
    }

    /**
     * 发送消息到数字人
     */
    async sendMessage() {
        const message = this.messageText.value.trim();

        // 验证输入
        if (!message) {
            this.showNotification('请输入消息内容', 'error');
            return;
        }

        if (!this.isConnected || !this.sessionId) {
            this.showNotification('请先连接到服务器', 'error');
            return;
        }

        // 禁用发送按钮，防止重复提交
        this.setSendingState(true);

        try {
            // 发送HTTP请求
            const response = await fetch('/any4dh/human', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sessionid: this.sessionId,
                    text: message,
                    type: 'echo'
                })
            });

            const data = await response.json();

            // 处理响应
            if (data.code === 0 || response.ok) {
                this.handleSendSuccess(message);
            } else {
                this.handleSendError(data.msg || '服务器错误');
            }

        } catch (error) {
            this.handleSendError(error.message);
        } finally {
            this.setSendingState(false);
        }
    }

    /**
     * 处理发送成功
     * @param {string} message - 发送的消息
     */
    handleSendSuccess(message) {
        // 清空输入框
        this.messageText.value = '';

        // 显示成功提示
        this.showNotification('消息发送成功', 'success');

        // 更新系统信息
        const displayMessage = message.length > 20 ?
            message.substring(0, 20) + '...' :
            message;
        this.systemInfo.innerHTML = `消息已发送: ${displayMessage}`;

        // 重新聚焦输入框
        this.messageText.focus();
    }

    /**
     * 处理发送错误
     * @param {string} errorMessage - 错误消息
     */
    handleSendError(errorMessage) {
        this.showNotification(`发送失败: ${errorMessage}`, 'error');
    }

    /**
     * 设置发送状态
     * @param {boolean} isSending - 是否正在发送
     */
    setSendingState(isSending) {
        if (!this.sendBtn) return;

        this.sendBtn.disabled = isSending;
        this.sendBtn.innerHTML = isSending ?
            '<i class="layui-icon layui-icon-loading layui-anim layui-anim-rotate layui-anim-loop"></i> 发送中...' :
            '<i class="layui-icon layui-icon-release"></i> 发送消息';
    }

    /**
     * 显示通知消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型 (success, error, loading)
     */
    showNotification(message, type = 'info') {
        if (!this.layer) {
            console.log(`[${type.toUpperCase()}] ${message}`);
            return;
        }

        const iconMap = {
            success: 1,
            error: 2,
            loading: 16,
            info: 0
        };

        const icon = iconMap[type] || 0;

        if (type === 'loading') {
            this.layer.msg(message, {icon: icon, shade: 0.3, time: 1000});
        } else {
            this.layer.msg(message, {icon: icon, time: 2000});
        }
    }

    /**
     * 获取当前状态信息
     */
    getStatus() {
        return {
            connected: this.connectionStatus?.className.includes('status-connected') || false,
            messageCount: this.systemInfo?.innerHTML.includes('消息已发送') ? 1 : 0
        };
    }

    /**
     * 重置界面状态
     */
    reset() {
        this.cleanup();
        this.messageText.value = '';
        this.systemInfo.innerHTML = '等待发送消息...';
        this.updateConnectionUI(false);
        this.setSendingState(false);
    }
}

// 页面加载完成后初始化（避免重复初始化）
document.addEventListener('DOMContentLoaded', function() {
    if (!window.dashboardController) {
        // 创建全局控制器实例
        window.dashboardController = new DashboardController();

        // 暴露到全局作用域以便调试
        window.dashboard = window.dashboardController;
    } else {
        console.log('Dashboard 控制器已存在，跳过重复初始化');
    }
});

// 导出到模块（如果使用模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DashboardController;
}