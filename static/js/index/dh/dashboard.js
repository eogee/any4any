/**
 * Dashboard JavaScript - 数字人交互界面
 * 依赖: LayUI 框架
 */

/**
 * 语音录音器类
 */
class VoiceRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.stream = null;
    }

    /**
     * 开始录音
     */
    async startRecording() {
        try {
            // 获取麦克风权限
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            // 创建MediaRecorder实例
            const options = { mimeType: 'audio/webm;codecs=opus' };
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = 'audio/webm';
            }
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = 'audio/mp4';
            }

            this.mediaRecorder = new MediaRecorder(this.stream, options);
            this.audioChunks = [];

            // 处理录音数据
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            // 处理录音错误
            this.mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder错误:', event.error);
                this.cleanup();
            };

            // 开始录音
            this.mediaRecorder.start(100); // 每100ms收集一次数据
            this.isRecording = true;

            console.log('录音开始');

        } catch (error) {
            console.error('录音启动失败:', error);
            this.cleanup();
            throw error;
        }
    }

    /**
     * 停止录音
     */
    stopRecording() {
        return new Promise((resolve, reject) => {
            if (!this.mediaRecorder || !this.isRecording) {
                resolve(new Blob());
                return;
            }

            // 设置停止回调
            this.mediaRecorder.onstop = () => {
                try {
                    const audioBlob = new Blob(this.audioChunks, {
                        type: this.mediaRecorder.mimeType || 'audio/webm'
                    });
                    console.log('录音停止，音频大小:', audioBlob.size, 'bytes');
                    resolve(audioBlob);
                } catch (error) {
                    console.error('音频Blob创建失败:', error);
                    reject(error);
                } finally {
                    this.cleanup();
                }
            };

            // 停止录音
            try {
                this.mediaRecorder.stop();
                this.isRecording = false;
            } catch (error) {
                console.error('停止录音失败:', error);
                this.cleanup();
                reject(error);
            }
        });
    }

    /**
     * 清理资源
     */
    cleanup() {
        this.isRecording = false;

        // 停止音频流
        if (this.stream) {
            this.stream.getTracks().forEach(track => {
                try {
                    track.stop();
                } catch (error) {
                    console.error('停止音轨失败:', error);
                }
            });
            this.stream = null;
        }

        // 清理MediaRecorder
        if (this.mediaRecorder) {
            this.mediaRecorder.ondataavailable = null;
            this.mediaRecorder.onerror = null;
            this.mediaRecorder.onstop = null;
            this.mediaRecorder = null;
        }

        // 清理音频数据
        this.audioChunks = [];
    }

    /**
     * 取消录音
     */
    cancelRecording() {
        if (this.isRecording) {
            this.cleanup();
            console.log('录音已取消');
        }
    }
}

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

        // 绿幕处理相关
        this.greenScreenProcessor = null;
        this.enableGreenScreenSwitch = null;
        this.keyColorPicker = null;
        this.thresholdSlider = null;
        this.smoothingSlider = null;
        this.bgImageInput = null;
        this.uploadBgBtn = null;
        this.resetGreenScreenBtn = null;

        // 语音对话相关
        this.voiceRecorder = null;
        this.voiceRecordBtn = null;
        this.voiceChatHistory = null;

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
            layui.use(['layer', 'form', 'element', 'slider'], () => {
                this.setupLayUI();
                this.bindElements();
                this.bindEvents();
                this.initializeUI();

                // 延迟初始化绿幕功能，确保主UI优先显示
                setTimeout(() => {
                    this.initGreenScreen();
                }, 100);
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

        // 重新渲染表单组件
        this.form.render();
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

        // 绿幕控制元素
        this.enableGreenScreenSwitch = document.getElementById('enableGreenScreen');
        this.keyColorPicker = document.getElementById('keyColor');
        this.thresholdSlider = document.getElementById('thresholdSlider');
        this.smoothingSlider = document.getElementById('smoothingSlider');
        this.bgImageInput = document.getElementById('bgImageInput');
        this.uploadBgBtn = document.getElementById('uploadBg');
        this.resetGreenScreenBtn = document.getElementById('resetGreenScreen');

        // 语音对话元素
        this.voiceRecordBtn = document.getElementById('voiceRecordBtn');
                        this.voiceChatHistory = document.getElementById('voiceChatHistory');

        
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

        // 语音录音按钮点击事件
        if (this.voiceRecordBtn) {
            this.voiceRecordBtn.addEventListener('click', () => {
                this.toggleVoiceRecording();
            });
        }
    }

    /**
     * 初始化UI状态
     */
    initializeUI() {
        this.updateConnectionUI(false);
        this.messageText.focus();
        this.initVoiceChat();
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

            // 如果绿幕处理器已启用，开始处理
            if (this.greenScreenProcessor && this.greenScreenProcessor.isEnabled) {
                setTimeout(() => {
                    this.greenScreenProcessor.startProcessing();
                }, 100); // 等待视频开始播放
            }
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

    /**
     * 初始化绿幕处理器
     */
    initGreenScreen() {
        try {
            // 重新渲染表单组件（确保绿幕相关的表单元素正确渲染）
            if (this.form) {
                this.form.render();
            }

            // 检查绿幕脚本是否加载
            if (typeof GreenScreenProcessor === 'undefined') {
                this.hideGreenScreenControls();
                return;
            }

            // 检查绿幕相关DOM元素
            if (!this.enableGreenScreenSwitch || !this.keyColorPicker) {
                this.hideGreenScreenControls();
                return;
            }

            
            // 创建绿幕处理器实例
            this.greenScreenProcessor = new GreenScreenProcessor({
                keyColor: [0, 255, 0],
                threshold: 160,
                smoothing: 5,
                scaleFactor: 0.75, // 75%分辨率处理，平衡性能和质量
                maxFPS: 25,
                enableWebGL: true
            });

            // 绑定绿幕事件
            this.bindGreenScreenEvents();

            
            } catch (error) {
            this.hideGreenScreenControls();
        }
    }

    /**
     * 隐藏绿幕控制面板（如果初始化失败）
     */
    hideGreenScreenControls() {
        const greenScreenSection = document.querySelector('.sidebar-section h3');
        if (greenScreenSection && greenScreenSection.textContent.includes('绿幕设置')) {
            const section = greenScreenSection.closest('.sidebar-section');
            if (section) {
                section.style.display = 'none';
            }
        }
    }

    /**
     * 显示简单的绿幕状态信息（即使绿幕功能不可用）
     */
    showSimpleGreenScreenInfo() {
        const greenScreenInfo = document.getElementById('green-screen-info');
        if (greenScreenInfo) {
            greenScreenInfo.innerHTML = '绿幕功能: 不可用<br>请刷新页面重试';
        }
    }

    /**
     * 绑定绿幕控制事件
     */
    bindGreenScreenEvents() {
        if (!this.greenScreenProcessor) return;

        // 启用/禁用绿幕 - 使用LayUI表单事件监听
        if (this.form) {
            this.form.on('switch(enableGreenScreen)', (data) => {
                if (data.elem.checked) {
                    this.greenScreenProcessor.enable();
                    this.updateGreenScreenInfo();
                } else {
                    this.greenScreenProcessor.disable();
                    this.updateGreenScreenInfo();
                }
            });
        }

        // 目标颜色选择
        if (this.keyColorPicker) {
            this.keyColorPicker.addEventListener('change', (e) => {
                this.greenScreenProcessor.setKeyColor(e.target.value);
            });
        }

        // 阈值滑块
        if (this.thresholdSlider) {
            layui.slider.render({
                elem: this.thresholdSlider,
                min: 0,
                max: 255,
                value: 160,
                change: (value) => {
                    this.greenScreenProcessor.setThreshold(value);
                    document.getElementById('thresholdValue').textContent = value;
                }
            });
        }

        // 平滑度滑块
        if (this.smoothingSlider) {
            layui.slider.render({
                elem: this.smoothingSlider,
                min: 0,
                max: 10,
                value: 5,
                change: (value) => {
                    this.greenScreenProcessor.setSmoothing(value);
                    document.getElementById('smoothingValue').textContent = value;
                }
            });
        }

        // 背景图片上传
        if (this.uploadBgBtn && this.bgImageInput) {
            this.uploadBgBtn.addEventListener('click', () => {
                this.bgImageInput.click();
            });

            this.bgImageInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file && file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        this.greenScreenProcessor.setBackground(event.target.result);
                        this.showNotification('背景图片已更新', 'success');
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        // 重置按钮
        if (this.resetGreenScreenBtn) {
            this.resetGreenScreenBtn.addEventListener('click', () => {
                this.greenScreenProcessor.reset();

                // 重置UI控件
                this.enableGreenScreenSwitch.checked = false;
                this.keyColorPicker.value = '#00ff00';
                document.getElementById('thresholdValue').textContent = '160';
                document.getElementById('smoothingValue').textContent = '5';

                // 重置滑块
                layui.slider.render({
                    elem: this.thresholdSlider,
                    min: 0,
                    max: 255,
                    value: 160
                });

                layui.slider.render({
                    elem: this.smoothingSlider,
                    min: 0,
                    max: 10,
                    value: 5
                });

                this.showNotification('绿幕设置已重置', 'info');
            });
        }
    }

    /**
     * 获取绿幕状态
     */
    getGreenScreenStatus() {
        if (!this.greenScreenProcessor) return null;
        return this.greenScreenProcessor.getStatus();
    }

    /**
     * 更新绿幕系统信息
     */
    updateGreenScreenInfo() {
        const status = this.getGreenScreenStatus();
        if (!status) return;

        const info = `
            绿幕状态: ${status.enabled ? '启用' : '禁用'}<br>
            处理中: ${status.processing ? '是' : '否'}<br>
            FPS: ${status.fps}<br>
            渲染: ${status.webgl ? 'WebGL' : 'Canvas 2D'}
        `;

        // 可以在系统信息面板中显示
        const greenScreenInfoElement = document.getElementById('green-screen-info');
        if (greenScreenInfoElement) {
            greenScreenInfoElement.innerHTML = info;
        }
    }

    /**
     * 初始化语音对话功能
     */
    initVoiceChat() {
        // 创建语音录音器实例
        this.voiceRecorder = new VoiceRecorder();

        // 初始化流式模式控件
        if (typeof layui !== 'undefined' && layui.form) {
            layui.form.render(); // 渲染所有表单
        }

        // 检查浏览器是否支持录音
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            
            if (this.voiceRecordBtn) {
                this.voiceRecordBtn.disabled = true;
                this.voiceRecordBtn.innerHTML = '<i class="layui-icon layui-icon-close"></i> 浏览器不支持录音';
            }
            return;
        }        
    }

    /**
     * 切换语音录音状态
     */
    async toggleVoiceRecording() {
        if (!this.voiceRecorder) {
            this.showVoiceError('语音录音器未初始化');
            return;
        }

        try {
            if (this.voiceRecorder.isRecording) {
                await this.stopVoiceRecording();
            } else {
                await this.startVoiceRecording();
            }
        } catch (error) {
            console.error('语音录音切换失败:', error);
            this.showVoiceError('录音操作失败: ' + error.message);
        }
    }

    /**
     * 开始语音录音
     */
    async startVoiceRecording() {
        try {
            await this.voiceRecorder.startRecording();
            
            // 更新按钮状态
            this.voiceRecordBtn.innerHTML = '<i class="layui-icon layui-icon-close"></i> 停止录音';
            this.voiceRecordBtn.className = 'layui-btn layui-btn-fluid layui-btn-warm recording';

            // 开始录音计时
            this.startRecordingTimer();

        } catch (error) {
            console.error('录音启动失败:', error);
            this.showVoiceError('录音启动失败: ' + error.message);
        }
    }

    /**
     * 停止语音录音
     */
    async stopVoiceRecording() {
        try {
            
            // 停止录音计时
            this.stopRecordingTimer();

            // 更新按钮状态
            this.voiceRecordBtn.innerHTML = '<i class="layui-icon layui-icon-loading layui-anim layui-anim-rotate layui-anim-loop"></i> 处理中...';
            this.voiceRecordBtn.disabled = true;

            // 获取录音数据
            const audioBlob = await this.voiceRecorder.stopRecording();

            // 检查是否启用流式模式
            const streamingEnabled = document.getElementById('enableStreaming')?.checked ?? true;

            // 根据模式选择处理方式
            let result;
            if (streamingEnabled) {
                // 流式模式
                await this.processVoiceChatStream(audioBlob);
                return; // 流式模式会自行处理结果显示
            } else {
                // 标准模式
                result = await this.sendVoiceToServer(audioBlob);
            }

            if (result.success) {
                this.displayVoiceChatResult(result);

                // 音频始终通过数字人播放，不使用前端音频播放器
                if (result.audio_synced) {
                    // 音频已同步到数字人，显示播放状态
                    
                    // 使用服务器返回的准确音频时长
                    const duration = result.audio_duration || 15000; // 默认15秒
                    console.log(`音频播放时长: ${duration}ms`);
                    setTimeout(() => {
                        
                        console.log('数字人音频播放完成');
                    }, duration);
                } else {
                    this.showVoiceError('音频同步失败，请稍后重试');
                    setTimeout(() => {
                        
                    }, 3000);
                }
            } else {
                this.showVoiceError(result.error || '语音处理失败');
            }

        } catch (error) {
            console.error('录音处理失败:', error);
            this.showVoiceError('录音处理失败: ' + error.message);
        } finally {
            // 恢复按钮状态
            this.voiceRecordBtn.innerHTML = '<i class="layui-icon layui-icon-record"></i> 开始录音';
            this.voiceRecordBtn.className = 'layui-btn layui-btn-fluid layui-btn-danger';
            this.voiceRecordBtn.disabled = false;
            
        }
    }

    /**
     * 发送语音数据到服务器
     */
    async sendVoiceToServer(audioBlob) {
        const formData = new FormData();
        formData.append('file', audioBlob, `recording_${Date.now()}.webm`);
        // 传递当前的数字人会话ID
        if (this.sessionId) {
            formData.append('sessionid', this.sessionId.toString());
        }

        try {
            const response = await fetch('/any4dh/voice-chat', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('服务器错误详情:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`);
            }

            return await response.json();

        } catch (error) {
            console.error('发送语音数据失败:', error);
            throw error;
        }
    }

    /**
     * 显示语音对话结果
     */
    displayVoiceChatResult(result) {
        if (!this.voiceChatHistory) return;

        // 移除占位符
        const placeholder = this.voiceChatHistory.querySelector('.voice-chat-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const chatItem = document.createElement('div');
        chatItem.className = 'voice-chat-item';
        chatItem.innerHTML = `
            <div class="voice-user-message">
                <div class="voice-message-label">您</div>
                <div>${this.escapeHtml(result.recognized_text)}</div>
            </div>
            <div class="voice-ai-message">
                <div class="voice-message-label">AI助手</div>
                <div>${this.escapeHtml(result.response_text)}</div>
            </div>
        `;

        // 插入到顶部
        this.voiceChatHistory.insertBefore(chatItem, this.voiceChatHistory.firstChild);

        // 限制历史记录数量
        const maxItems = 10;
        const items = this.voiceChatHistory.querySelectorAll('.voice-chat-item');
        if (items.length > maxItems) {
            for (let i = maxItems; i < items.length; i++) {
                items[i].remove();
            }
        }
    }

    /**
     * 流式语音处理 - 支持分段TTS响应
     */
    async processVoiceChatStream(audioBlob) {
        if (!this.voiceChatHistory) return;

        try {
            // 创建流式对话项
            this.createStreamChatItem();

            // 发送流式请求
            const formData = new FormData();
            formData.append('file', audioBlob, `recording_${Date.now()}.webm`);
            if (this.sessionId) {
                formData.append('sessionid', this.sessionId.toString());
            }

            const response = await fetch('/any4dh/voice-chat-stream', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // 处理流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保留最后一行（可能不完整）

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            this.handleStreamData(data);
                        } catch (e) {
                            console.error('解析流式数据失败:', e, line);
                        }
                    }
                }
            }

        } catch (error) {
            console.error('流式语音处理失败:', error);
            this.showVoiceError('流式语音处理失败: ' + error.message);
            this.updateStreamChatItem('error', '处理失败');
        }
    }

    /**
     * 创建流式对话项
     */
    createStreamChatItem() {
        // 移除占位符
        const placeholder = this.voiceChatHistory.querySelector('.voice-chat-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const chatItem = document.createElement('div');
        chatItem.className = 'voice-chat-item streaming';
        chatItem.innerHTML = `
            <div class="voice-user-message">
                <div class="voice-message-label">您</div>
                <div class="voice-user-text">正在识别...</div>
            </div>
            <div class="voice-ai-message">
                <div class="voice-message-label">AI助手</div>
                <div class="voice-ai-text">
                    <span class="streaming-indicator">正在思考...</span>
                </div>
            </div>
        `;

        this.voiceChatHistory.appendChild(chatItem);
        this.voiceChatHistory.scrollTop = this.voiceChatHistory.scrollHeight;

        return chatItem;
    }

    /**
     * 处理流式数据
     */
    handleStreamData(data) {
        switch (data.type) {
            case 'status':
                // 显示用户输入的文本
                if (data.recognized_text) {
                    this.updateStreamChatItem('user', data.recognized_text);
                }
                this.updateStreamChatItem('status', data.message);
                break;

            case 'audio_segment':
            case 'final_segment':
                // 显示AI回复文本
                if (data.data.text) {
                    this.updateStreamChatItem('ai', data.data.text);
                }

                if (data.data.audio_url) {
                    // 在控制台显示音频生成状态，不在界面显示
                    console.log('音频生成中...');
                    // 在流式模式下，立即播放音频
                    this.playAudioSegment(data.data.audio_url, data.data.text, data.segment_index);
                }

                if (data.type === 'final_segment') {
                    this.updateStreamChatItem('status', '回复完成');
                    // 流式模式结束后，更新状态
                    setTimeout(() => {
                        this.isProcessing = false;
                        this.updateRecordingState(false);
                    }, 1000);
                }
                break;

            case 'audio_file':
                // 处理预录音频文件
                if (data.data.text) {
                    this.updateStreamChatItem('ai', data.data.text);
                }

                // 直接播放音频文件
                if (data.data.audio_path) {
                    this.playAudioSegment(data.data.audio_path, data.data.text, 0);
                }

                // 更新状态并结束处理
                this.updateStreamChatItem('status', '回复完成');
                setTimeout(() => {
                    this.isProcessing = false;
                    this.updateRecordingState(false);
                }, 1000);
                break;

            case 'completed':
                this.updateStreamChatItem('status', `处理完成 (共${data.total_segments}段)`);
                this.isProcessing = false;
                this.updateRecordingState(false);
                break;

            case 'error':
                this.updateStreamChatItem('error', data.message);
                this.isProcessing = false;
                this.updateRecordingState(false);
                this.showError(data.message);
                break;

            default:
                console.log('未知数据类型:', data);
        }
    }

    /**
     * 更新流式对话项
     */
    updateStreamChatItem(type, content) {
        const chatItem = this.voiceChatHistory.querySelector('.voice-chat-item.streaming:last-child');
        if (!chatItem) return;

        const userText = chatItem.querySelector('.voice-user-text');
        const aiText = chatItem.querySelector('.voice-ai-text');

        switch (type) {
            case 'user':
                // 显示用户文本
                if (userText) {
                    userText.innerHTML = content;
                }
                break;

            case 'status':
                // 显示状态信息，但保留AI文本
                const currentAiText = aiText.getAttribute('data-ai-text') || '';
                if (currentAiText) {
                    aiText.innerHTML = `${currentAiText}<br><span class="streaming-indicator">${content}</span>`;
                } else {
                    aiText.innerHTML = `<span class="streaming-indicator">${content}</span>`;
                }
                break;

            case 'ai':
                // 累积AI文本
                let existingText = aiText.getAttribute('data-ai-text') || '';
                existingText += content;
                aiText.setAttribute('data-ai-text', existingText);
                aiText.innerHTML = existingText;
                break;

            case 'final':
                // 最终文本
                aiText.setAttribute('data-ai-text', content);
                aiText.innerHTML = content;
                chatItem.classList.remove('streaming');
                break;

            case 'completed':
                // 完成状态
                const finalAiText = aiText.getAttribute('data-ai-text') || '';
                if (finalAiText) {
                    aiText.innerHTML = `${finalAiText}<br><span class="streaming-complete">${content}</span>`;
                } else {
                    aiText.innerHTML = `<span class="streaming-complete">${content}</span>`;
                }
                chatItem.classList.remove('streaming');
                break;

            case 'error':
                // 错误状态
                aiText.innerHTML = `<span class="streaming-error">${content}</span>`;
                chatItem.classList.add('error');
                chatItem.classList.remove('streaming');
                break;
        }

        // 滚动到底部
        this.voiceChatHistory.scrollTop = this.voiceChatHistory.scrollHeight;
    }

    /**
     * 播放音频段 - 同步到数字人
     */
    async playAudioSegment(audioUrl, text, segmentIndex) {
        try {
            if (!this.isConnected || !this.sessionId) {
                console.warn('数字人未连接，无法播放音频');
                return;
            }

            // 确保sessionid是数字类型
            const sessionId = parseInt(this.sessionId);
            if (isNaN(sessionId)) {
                console.warn('无效的sessionId:', this.sessionId);
                return;
            }

            // 通知数字人播放音频
            const response = await fetch('/any4dh/play-audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sessionid: sessionId,
                    audio_url: audioUrl,
                    text: text,
                    segment_index: segmentIndex
                })
            });

            if (response.ok) {
                console.log(`音频段已发送到数字人: ${text ? text.substring(0, 20) : 'N/A'}...`);
            } else {
                console.error('音频播放请求失败:', await response.text());
            }

        } catch (error) {
            console.error('播放音频段失败:', error);
        }
    }

    /**
     * 更新录音状态
     */
    updateRecordingState(isProcessing) {
        if (isProcessing) {
            this.isProcessing = true;
            if (this.voiceRecordBtn) {
                this.voiceRecordBtn.disabled = true;
                this.voiceRecordBtn.innerHTML = '<i class="layui-icon layui-icon-loading layui-anim layui-anim-rotate layui-anim-loop"></i> 处理中...';
            }
        } else {
            this.isProcessing = false;
            if (this.voiceRecordBtn) {
                this.voiceRecordBtn.disabled = false;
                this.voiceRecordBtn.innerHTML = '<i class="layui-icon layui-icon-record"></i> 开始录音';
                this.voiceRecordBtn.className = 'layui-btn layui-btn-fluid layui-btn-danger';
            }
        }
    }

    /**
     * 发送流式语音数据到服务器（备用方法）
     */
    async sendVoiceToServerStream(audioBlob) {
        return this.processVoiceChatStream(audioBlob);
    }

    /**
     * 显示语音错误
     */
    showVoiceError(message) {
        // 更新状态显示
        

        // 显示错误提示
        if (typeof layui !== 'undefined' && layui.layer) {
            layui.layer.msg(message, {icon: 2, time: 3000});
        } else {
            alert(message);
        }

        console.error('语音对话错误:', message);
    }

    /**
     * 开始录音计时
     */
    startRecordingTimer() {
        this.recordingStartTime = Date.now();
        this.recordingTimer = setInterval(() => {
            const duration = Math.floor((Date.now() - this.recordingStartTime) / 1000);
            const minutes = Math.floor(duration / 60);
            const seconds = duration % 60;
            const timeText = `正在录音... ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            
        }, 1000);
    }

    /**
     * 停止录音计时
     */
    stopRecordingTimer() {
        if (this.recordingTimer) {
            clearInterval(this.recordingTimer);
            this.recordingTimer = null;
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