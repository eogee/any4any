/**
 * UI 操作相关公共函数
 */

// 显示消息提示
function showMessage(message, type = 'info', duration = 2000) {
    if (typeof layui !== 'undefined' && layui.layer) {
        const layer = layui.layer;
        const icons = {
            'success': 1,
            'error': 2,
            'warning': 3,
            'info': 0,
            'loading': 2
        };

        if (type === 'loading') {
            return layer.load(2, {
                shade: [0.3, '#fff'],
                content: message
            });
        } else {
            layer.msg(message, {
                icon: icons[type] || 0,
                time: duration
            });
        }
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

// 显示加载状态
function showLoading(message = '加载中...') {
    return showMessage(message, 'loading');
}

// 隐藏加载状态
function hideLoading(loadingIndex) {
    if (typeof layui !== 'undefined' && layui.layer && loadingIndex) {
        layui.layer.close(loadingIndex);
    }
}

// 确认对话框
function confirmDialog(message, onConfirm, onCancel) {
    if (typeof layui !== 'undefined' && layui.layer) {
        layui.layer.confirm(message, {
            icon: 3,
            title: '确认'
        }, function(index) {
            layui.layer.close(index);
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
        }, function(index) {
            layui.layer.close(index);
            if (typeof onCancel === 'function') {
                onCancel();
            }
        });
    } else {
        if (window.confirm(message)) {
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
        } else {
            if (typeof onCancel === 'function') {
                onCancel();
            }
        }
    }
}

// 创建空状态元素
function createEmptyState(icon, message) {
    return `
        <div class="empty-state">
            <i class="fas fa-${icon}"></i>
            <p>${message}</p>
        </div>
    `;
}

// 创建错误状态元素
function createErrorState(message) {
    return `
        <div class="error-state">
            <i class="fas fa-exclamation-triangle"></i>
            <p>${message}</p>
        </div>
    `;
}

// 创建加载状态元素
function createLoadingState(message = '加载中...') {
    return `
        <div class="loading-state">
            <i class="fas fa-spinner fa-spin"></i>
            <p>${message}</p>
        </div>
    `;
}

// 切换元素显示状态
function toggleElement(elementId, show = null) {
    const element = document.getElementById(elementId);
    if (!element) return;

    if (show === null) {
        // 如果没有指定显示状态，则切换当前状态
        element.style.display = element.style.display === 'none' ? 'block' : 'none';
    } else {
        element.style.display = show ? 'block' : 'none';
    }
}

// 设置元素内容
function setElementContent(elementId, content) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = content;
    }
}

// 获取元素
function getElement(elementId) {
    return document.getElementById(elementId);
}

// 添加事件监听器
function addEventListener(elementId, event, handler) {
    const element = document.getElementById(elementId);
    if (element) {
        element.addEventListener(event, handler);
    }
}

// 移除事件监听器
function removeEventListener(elementId, event, handler) {
    const element = document.getElementById(elementId);
    if (element) {
        element.removeEventListener(event, handler);
    }
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 导出函数
window.UiUtils = {
    showMessage,
    showLoading,
    hideLoading,
    confirmDialog,
    createEmptyState,
    createErrorState,
    createLoadingState,
    toggleElement,
    setElementContent,
    getElement,
    addEventListener,
    removeEventListener,
    debounce,
    throttle
};