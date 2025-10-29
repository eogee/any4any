/**
 * GreenScreenProcessor - 绿幕处理核心类
 * 支持实时色键处理、背景替换和性能优化
 */

class GreenScreenProcessor {
    constructor(options = {}) {
        // 配置选项
        this.options = {
            keyColor: options.keyColor || [0, 255, 0], // 默认绿色
            threshold: options.threshold || 160,
            smoothing: options.smoothing || 5,
            scaleFactor: options.scaleFactor || 0.5, // 处理分辨率缩放
            maxFPS: options.maxFPS || 30,
            enableWebGL: options.enableWebGL !== false, // 默认启用WebGL
            ...options
        };

        // DOM元素
        this.videoElement = null;
        this.canvasElement = null;
        this.backgroundLayer = null;
        this.ctx = null;

        // 处理状态
        this.isEnabled = false;
        this.isProcessing = false;
        this.currentBackground = 'none';

        // 性能监控
        this.frameCount = 0;
        this.lastFPSTime = performance.now();
        this.currentFPS = 0;

        // 帧率控制
        this.frameInterval = 1000 / this.options.maxFPS;
        this.lastFrameTime = 0;

        // WebGL相关
        this.gl = null;
        this.shaderProgram = null;
        this.textures = {};

        // 缓存
        this.processedCache = new Map();
        this.maxCacheSize = 10;

        this.init();
    }

    /**
     * 初始化处理器
     */
    init() {
        this.bindElements();
        this.setupWebGL();
        this.bindEvents();
    }

    /**
     * 绑定DOM元素
     */
    bindElements() {
        this.videoElement = document.getElementById('videoElement');
        this.canvasElement = document.getElementById('processedCanvas');
        this.backgroundLayer = document.getElementById('backgroundLayer');

        if (!this.videoElement || !this.canvasElement || !this.backgroundLayer) {
            console.error('GreenScreenProcessor: 必要的DOM元素未找到');
            return false;
        }

        this.ctx = this.canvasElement.getContext('2d', { willReadFrequently: true });
        return true;
    }

    /**
     * 设置WebGL
     */
    setupWebGL() {
        if (!this.options.enableWebGL) return;

        try {
            this.gl = this.canvasElement.getContext('webgl', { willReadFrequently: true }) ||
                        this.canvasElement.getContext('experimental-webgl', { willReadFrequently: true });
            if (this.gl) {
                this.initWebGLShaders();
            }
        } catch (error) {
            this.gl = null;
        }
    }

    /**
     * 初始化WebGL着色器
     */
    initWebGLShaders() {
        const gl = this.gl;

        // 顶点着色器
        const vertexShaderSource = `
            attribute vec2 a_position;
            attribute vec2 a_texCoord;
            varying vec2 v_texCoord;

            void main() {
                gl_Position = vec4(a_position, 0, 1);
                v_texCoord = a_texCoord;
            }
        `;

        // 片段着色器
        const fragmentShaderSource = `
            precision mediump float;
            uniform sampler2D u_image;
            uniform vec3 u_keyColor;
            uniform float u_threshold;
            uniform float u_smoothing;
            varying vec2 v_texCoord;

            void main() {
                vec4 color = texture2D(u_image, v_texCoord);
                vec3 rgb = color.rgb;
                vec3 keyColor = u_keyColor;

                // 计算颜色距离
                float distance = length(rgb - keyColor);

                // 应用平滑过渡
                float alpha = 1.0;
                if (distance < u_threshold) {
                    alpha = 0.0;
                } else if (distance < u_threshold + u_smoothing * 10.0) {
                    alpha = (distance - u_threshold) / (u_smoothing * 10.0);
                }

                gl_FragColor = vec4(rgb, alpha * color.a);
            }
        `;

        // 编译着色器
        const vertexShader = this.compileShader(vertexShaderSource, gl.VERTEX_SHADER);
        const fragmentShader = this.compileShader(fragmentShaderSource, gl.FRAGMENT_SHADER);

        if (!vertexShader || !fragmentShader) {
            throw new Error('着色器编译失败');
        }

        // 创建程序
        this.shaderProgram = gl.createProgram();
        gl.attachShader(this.shaderProgram, vertexShader);
        gl.attachShader(this.shaderProgram, fragmentShader);
        gl.linkProgram(this.shaderProgram);

        if (!gl.getProgramParameter(this.shaderProgram, gl.LINK_STATUS)) {
            throw new Error('着色器程序链接失败');
        }

        // 设置顶点数据
        const positions = new Float32Array([
            -1, -1, 1, -1, -1, 1, 1, 1
        ]);
        const texCoords = new Float32Array([
            0, 1, 1, 1, 0, 0, 1, 0
        ]);

        // 创建缓冲区
        const positionBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

        const texCoordBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, texCoords, gl.STATIC_DRAW);

        // 获取属性位置
        const positionLocation = gl.getAttribLocation(this.shaderProgram, 'a_position');
        const texCoordLocation = gl.getAttribLocation(this.shaderProgram, 'a_texCoord');

        // 设置属性
        gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
        gl.enableVertexAttribArray(positionLocation);
        gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

        gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
        gl.enableVertexAttribArray(texCoordLocation);
        gl.vertexAttribPointer(texCoordLocation, 2, gl.FLOAT, false, 0, 0);

        // 创建纹理
        this.textures.image = gl.createTexture();
    }

    /**
     * 编译着色器
     */
    compileShader(source, type) {
        const gl = this.gl;
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);

        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            console.error('着色器编译错误:', gl.getShaderInfoLog(shader));
            gl.deleteShader(shader);
            return null;
        }

        return shader;
    }

    /**
     * 绑定事件监听器
     */
    bindEvents() {
        // 监听视频播放事件
        this.videoElement.addEventListener('play', () => {
            this.startProcessing();
        });

        this.videoElement.addEventListener('pause', () => {
            this.stopProcessing();
        });

        this.videoElement.addEventListener('ended', () => {
            this.stopProcessing();
        });
    }

    /**
     * 启用绿幕处理
     */
    enable() {
        this.isEnabled = true;
        this.canvasElement.style.display = 'block';
        this.backgroundLayer.style.display = 'block';

        if (this.videoElement.srcObject && !this.videoElement.paused) {
            this.startProcessing();
        }
    }

    /**
     * 禁用绿幕处理
     */
    disable() {
        this.isEnabled = false;
        this.stopProcessing();
        this.canvasElement.style.display = 'none';
        this.backgroundLayer.style.display = 'none';
    }

    /**
     * 开始处理
     */
    startProcessing() {
        if (this.isProcessing || !this.isEnabled) return;

        this.isProcessing = true;
        this.lastFrameTime = performance.now();
        this.processFrame();
    }

    /**
     * 停止处理
     */
    stopProcessing() {
        this.isProcessing = false;
    }

    /**
     * 处理帧
     */
    processFrame() {
        if (!this.isProcessing) return;

        const now = performance.now();
        if (now - this.lastFrameTime < this.frameInterval) {
            requestAnimationFrame(() => this.processFrame());
            return;
        }

        this.lastFrameTime = now;

        try {
            if (this.gl) {
                this.processFrameWebGL();
            } else {
                this.processFrameCanvas2D();
            }

            this.updatePerformanceMetrics();
        } catch (error) {
            console.error('GreenScreenProcessor: 处理帧时出错', error);
        }

        requestAnimationFrame(() => this.processFrame());
    }

    /**
     * 使用WebGL处理帧
     */
    processFrameWebGL() {
        const gl = this.gl;
        const video = this.videoElement;

        // 设置canvas尺寸
        const width = video.videoWidth * this.options.scaleFactor;
        const height = video.videoHeight * this.options.scaleFactor;
        this.canvasElement.width = width;
        this.canvasElement.height = height;
        gl.viewport(0, 0, width, height);

        // 更新纹理
        gl.bindTexture(gl.TEXTURE_2D, this.textures.image);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, video);

        // 设置纹理参数
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

        // 使用着色器程序
        gl.useProgram(this.shaderProgram);

        // 设置uniform变量
        const keyColorLocation = gl.getUniformLocation(this.shaderProgram, 'u_keyColor');
        const thresholdLocation = gl.getUniformLocation(this.shaderProgram, 'u_threshold');
        const smoothingLocation = gl.getUniformLocation(this.shaderProgram, 'u_smoothing');

        const [r, g, b] = this.options.keyColor;
        gl.uniform3f(keyColorLocation, r / 255, g / 255, b / 255);
        gl.uniform1f(thresholdLocation, this.options.threshold / 255);
        gl.uniform1f(smoothingLocation, this.options.smoothing / 255);

        // 启用透明度混合
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

        // 清除画布
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);

        // 绘制
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    /**
     * 使用Canvas 2D处理帧
     */
    processFrameCanvas2D() {
        const video = this.videoElement;
        const ctx = this.ctx;

        // 设置canvas尺寸（使用缩放后的分辨率）
        const width = video.videoWidth * this.options.scaleFactor;
        const height = video.videoHeight * this.options.scaleFactor;
        this.canvasElement.width = width;
        this.canvasElement.height = height;

        // 绘制视频帧
        ctx.drawImage(video, 0, 0, width, height);

        // 获取图像数据
        const imageData = ctx.getImageData(0, 0, width, height);
        const data = imageData.data;

        // 应用色键算法
        this.applyChromaKey(data);

        // 放回处理后的图像数据
        ctx.putImageData(imageData, 0, 0);
    }

    /**
     * 应用色键算法
     */
    applyChromaKey(data) {
        const [keyR, keyG, keyB] = this.options.keyColor;
        const threshold = this.options.threshold;
        const smoothing = this.options.smoothing;

        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];

            // 计算颜色距离
            const distance = this.colorDistance([r, g, b], [keyR, keyG, keyB]);

            let alpha = 255;
            if (distance < threshold) {
                alpha = 0;
            } else if (distance < threshold + smoothing * 10) {
                // 边缘平滑过渡
                alpha = ((distance - threshold) / (smoothing * 10)) * 255;
            }

            data[i + 3] = alpha;
        }
    }

    /**
     * 计算颜色距离
     */
    colorDistance(color1, color2) {
        const [r1, g1, b1] = color1;
        const [r2, g2, b2] = color2;
        return Math.sqrt(
            Math.pow(r1 - r2, 2) +
            Math.pow(g1 - g2, 2) +
            Math.pow(b1 - b2, 2)
        );
    }

    /**
     * 设置目标颜色
     */
    setKeyColor(color) {
        if (Array.isArray(color)) {
            this.options.keyColor = color;
        } else if (typeof color === 'string') {
            this.options.keyColor = this.hexToRgb(color);
        }
    }

    /**
     * 设置阈值
     */
    setThreshold(threshold) {
        this.options.threshold = Math.max(0, Math.min(255, threshold));
    }

    /**
     * 设置平滑度
     */
    setSmoothing(smoothing) {
        this.options.smoothing = Math.max(0, Math.min(10, smoothing));
    }

    
    /**
     * 设置背景
     */
    setBackground(background) {
        this.currentBackground = background;

        if (background === 'none') {
            this.backgroundLayer.style.backgroundImage = 'none';
            this.backgroundLayer.style.backgroundColor = 'transparent';
        } else if (background.startsWith('data:') || background.startsWith('http')) {
            this.backgroundLayer.style.backgroundImage = `url(${background})`;
            this.backgroundLayer.style.backgroundColor = 'transparent';
        } else {
            // 预设背景
            const presetBackgrounds = {
                'office': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                'blur': 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, rgba(0,0,0,0.2) 100%)'
            };

            if (presetBackgrounds[background]) {
                this.backgroundLayer.style.backgroundImage = presetBackgrounds[background];
                this.backgroundLayer.style.backgroundColor = 'transparent';
            }
        }

        this.backgroundLayer.style.backgroundSize = 'cover';
        this.backgroundLayer.style.backgroundPosition = 'center';
    }

    /**
     * HEX颜色转RGB
     */
    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? [
            parseInt(result[1], 16),
            parseInt(result[2], 16),
            parseInt(result[3], 16)
        ] : [0, 255, 0];
    }

    /**
     * 更新性能指标
     */
    updatePerformanceMetrics() {
        this.frameCount++;
        const now = performance.now();
        const elapsed = now - this.lastFPSTime;

        if (elapsed >= 1000) {
            this.currentFPS = Math.round((this.frameCount * 1000) / elapsed);
            this.frameCount = 0;
            this.lastFPSTime = now;

            // 显示性能信息
            this.updatePerformanceDisplay();
        }
    }

    /**
     * 更新性能显示
     */
    updatePerformanceDisplay() {
        let perfElement = document.getElementById('performanceMonitor');
        if (!perfElement) {
            perfElement = document.createElement('div');
            perfElement.id = 'performanceMonitor';
            perfElement.className = 'performance-monitor';
            this.videoElement.parentElement.appendChild(perfElement);
        }

        perfElement.innerHTML = `
            FPS: ${this.currentFPS}<br>
            WebGL: ${this.gl ? 'ON' : 'OFF'}<br>
            Scale: ${this.options.scaleFactor}x
        `;
    }

    /**
     * 重置设置
     */
    reset() {
        this.options.keyColor = [0, 255, 0];
        this.options.threshold = 160;
        this.options.smoothing = 5;
        this.setBackground('none');
    }

    /**
     * 获取当前状态
     */
    getStatus() {
        return {
            enabled: this.isEnabled,
            processing: this.isProcessing,
            fps: this.currentFPS,
            webgl: !!this.gl,
            scaleFactor: this.options.scaleFactor,
            background: this.currentBackground,
            keyColor: this.options.keyColor,
            threshold: this.options.threshold,
            smoothing: this.options.smoothing
        };
    }

    /**
     * 销毁处理器
     */
    destroy() {
        this.stopProcessing();

        if (this.gl) {
            // 清理WebGL资源
            Object.values(this.textures).forEach(texture => {
                this.gl.deleteTexture(texture);
            });

            if (this.shaderProgram) {
                this.gl.deleteProgram(this.shaderProgram);
            }
        }

        this.processedCache.clear();
    }
}

// 导出到全局
if (typeof window !== 'undefined') {
    window.GreenScreenProcessor = GreenScreenProcessor;
}

// 支持模块导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GreenScreenProcessor;
}