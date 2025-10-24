/**
 * 登录页面控制器
 */

// 初始化登录页面
function initializeLoginPage() {
    // 如果使用了 layui，等待 layui 加载完成
    if (typeof layui !== 'undefined') {
        layui.use(['form', 'layer'], function() {
            const form = layui.form;
            const layer = layui.layer;

            setupFormValidation(form);
            setupFormSubmission(form, layer);
        });
    } else {
        console.error('Layui not available');
    }
}

// 设置表单验证
function setupFormValidation(form) {
    form.verify({
        username: function(value) {
            if (value.length < 3 || value.length > 50) {
                return '用户名长度3-50个字符';
            }
        },
        password: function(value) {
            if (value.length < 6 || value.length > 50) {
                return '密码长度6-50个字符';
            }
        }
    });
}

// 设置表单提交
function setupFormSubmission(form, layer) {
    form.on('submit(login)', function(data) {
        const loading = showLoading();

        // 使用 ApiService 进行登录请求
        if (typeof ApiService !== 'undefined') {
            ApiService.login(data.field.username, data.field.password)
                .then(result => {
                    hideLoading(loading);
                    handleLoginResult(result, layer);
                })
                .catch(error => {
                    hideLoading(loading);
                    handleLoginError(error, layer);
                });
        } else {
            // 降级处理：使用原生 fetch
            fetch('/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data.field)
            })
            .then(response => {
                hideLoading(loading);
                if (!response.ok) throw new Error('网络错误');
                return response.json();
            })
            .then(result => {
                handleLoginResult(result, layer);
            })
            .catch(error => {
                handleLoginError(error, layer);
            });
        }

        return false; // 阻止表单默认提交
    });
}

// 处理登录结果
function handleLoginResult(result, layer) {
    if (result.success) {
        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage('登录成功', 'success', 1500);
        } else if (layer) {
            layer.msg('登录成功', {icon: 1, time: 1500});
        }
        setTimeout(() => {
            window.location.href = '/index';
        }, 1500);
    } else {
        const message = result.message || '登录失败';
        if (typeof UiUtils !== 'undefined') {
            UiUtils.showMessage(message, 'error');
        } else if (layer) {
            layer.msg(message, {icon: 2});
        }
    }
}

// 处理登录错误
function handleLoginError(error, layer) {
    console.error('Login error:', error);
    const message = '登录失败，请重试';

    if (typeof UiUtils !== 'undefined') {
        UiUtils.showMessage(message, 'error');
    } else if (layer) {
        layer.msg(message, {icon: 2});
    }
}

// 显示加载状态
function showLoading() {
    if (typeof UiUtils !== 'undefined') {
        return UiUtils.showLoading('登录中...');
    } else if (typeof layui !== 'undefined' && layui.layer) {
        return layui.layer.load(2, {
            shade: [0.3, '#fff'],
            content: '登录中...'
        });
    }
    return null;
}

// 隐藏加载状态
function hideLoading(loadingIndex) {
    if (typeof UiUtils !== 'undefined') {
        UiUtils.hideLoading(loadingIndex);
    } else if (typeof layui !== 'undefined' && layui.layer && loadingIndex) {
        layui.layer.close(loadingIndex);
    }
}

// 导出函数
window.LoginController = {
    initializeLoginPage,
    setupFormValidation,
    setupFormSubmission,
    handleLoginResult,
    handleLoginError
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeLoginPage();
});