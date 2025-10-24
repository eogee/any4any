/**
 * 内容处理相关公共函数
 */

// 设置 marked 选项
function setupMarked() {
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }
}

// 移除思考内容
function removeThinkContent(text) {
    if (!text) return '';
    return text.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

// 处理思考内容
function processThinkContent(text) {
    if (!text) return '';

    const thinkPattern = /<think>([\s\S]*?)<\/think>/g;
    let processedText = text;
    let thinkCount = 0;

    processedText = processedText.replace(thinkPattern, (match, content) => {
        const formattedContent = content.trim().split('\n').map(line => line.trim()).filter(line => line.length > 0).join('\n');
        const uniqueId = `think-${Date.now()}-${thinkCount}`;
        thinkCount++;

        return `<div class="think-container">
            <button class="think-toggle" onclick="toggleThink('${uniqueId}')">
                <i class="fas fa-lightbulb"></i> 思考过程
            </button>
            <div id="${uniqueId}" class="think-content" style="display: none;">${formattedContent}</div>
        </div>`;
    });

    return processedText;
}

// 切换思考内容显示/隐藏
function toggleThink(thinkId) {
    const content = document.getElementById(thinkId);
    if (!content) return;

    const button = content.previousElementSibling;
    const isHidden = content.style.display === 'none';

    content.style.display = isHidden ? 'block' : 'none';
    button.innerHTML = isHidden ?
        '<i class="fas fa-lightbulb"></i> 收起思考' :
        '<i class="fas fa-lightbulb"></i> 思考过程';
}

// 渲染 Markdown 内容
function renderMarkdown(content) {
    if (!content) return '';

    try {
        if (typeof marked === 'undefined') {
            console.warn('marked library not loaded');
            return content;
        }

        content = processThinkContent(content);

        const thinkBlocks = [];
        content = content.replace(/<div class="think-container">[\s\S]*?<\/div><\/div>/g, (match) => {
            const id = `THINK_BLOCK_${thinkBlocks.length}`;
            thinkBlocks.push({id: id, content: match});
            return id;
        });

        content = marked.parse(content);

        thinkBlocks.forEach(block => {
            content = content.replace(new RegExp(block.id, 'g'), block.content);
        });

        return content;
    } catch (e) {
        console.error('渲染错误:', e);
        return content;
    }
}

// HTML 转义
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/\n/g, '<br>');
}

// 格式化时间
function formatTime(timestamp) {
    return new Date(timestamp || Date.now()).toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 截取文本
function truncateText(text, maxLength = 100) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// 导出函数
window.ContentProcessor = {
    setupMarked,
    removeThinkContent,
    processThinkContent,
    toggleThink,
    renderMarkdown,
    escapeHtml,
    formatTime,
    truncateText
};