import re
import logging

logger = logging.getLogger(__name__)

def filter_special_chars(text: str) -> str:
    """过滤文本转语音特殊字符"""
    if not text or not isinstance(text, str):
        return ""
    
    # 保存原始文本用于日志
    original_text = text
    
    # 1. 移除URL和链接
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    text = re.sub(r'www\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', '', text)
    
    # 2. 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 3. 移除邮箱地址
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # 4. 移除特殊符号和标点（保留中文标点和基本英文标点）
    # 移除的符号：# * @ $ % ^ & _ = + [ ] { } | \ ~ ` < >
    text = re.sub(r'[#*@$%^&_=+\[\]{}|\\~`<>]', '', text)
    
    # 5. 移除数学符号
    text = re.sub(r'[±×÷≠≈≡≤≥∞∫∑∏√∂∆∇]', '', text)
    
    # 6. 移除表情符号和特殊Unicode字符
    text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)  # 补充平面字符
    text = re.sub(r'[\u2000-\u2FFF]', '', text)  # 各种符号区域
    text = re.sub(r'[\u3000-\u303F]', '', text)  # CJK符号和标点（部分保留）
    
    # 7. 移除控制字符和不可见字符
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)  # ASCII控制字符
    
    # 8. 处理重复的标点符号（保留一个）
    text = re.sub(r'[!?。，]{2,}', lambda m: m.group()[0], text)
    
    # 9. 处理多余的空白字符
    text = re.sub(r'\s+', ' ', text)  # 多个空格合并为一个
    text = text.strip()
    
    # 10. 调用原有的清理函数
    text = clean_img_text(text)
    text = clean_video_text(text)
    
    # 11. 移除可能影响TTS的特定模式
    # 移除版本号模式 (如 v1.2.3, Version 2.0)
    text = re.sub(r'\b[vV]?\d+\.\d+(\.\d+)?\b', '', text)
    # 移除文件扩展名
    text = re.sub(r'\b\w+\.(txt|pdf|doc|jpg|png|mp3|wav)\b', '', text)
    
    # 12. 处理特殊括号内容（可选移除）
    # 移除括号及其内容，如 (注释内容) [说明文字]
    text = re.sub(r'[\[\(].*?[\]\)]', '', text)
    
    # 13. 最终清理：移除首尾的特殊字符
    text = re.sub(r'^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$', '', text)
    
    # 记录清理日志（如果变化较大）
    if len(original_text) != len(text) or original_text != text:
        logger.debug(f"Text cleaned: '{original_text}' -> '{text}'")
    
    return text

def clean_img_text(text: str) -> str:
    """清理图片相关文本"""
    if not text:
        return ""
    
    # 移除图片标记和文件名
    patterns = [
        r'\[img\].*?\[/img\]',  # [img]...[/img]
        r'!\[.*?\]\(.*?\)',     # ![alt](url)
        r'\bimage\d*\b',        # image, image1, image2
        r'\bpic[ture]?\d*\b',   # pic, picture, pic1
        r'\bphoto\d*\b',        # photo, photo1
        r'\bscreenshot\d*\b',   # screenshot
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return text.strip()

def clean_video_text(text: str) -> str:
    """清理视频相关文本"""
    if not text:
        return ""
    
    # 移除视频标记和文件名
    patterns = [
        r'\[video\].*?\[/video\]',  # [video]...[/video]
        r'\bvideo\d*\b',           # video, video1
        r'\bmovie\d*\b',           # movie
        r'\bfilm\d*\b',            # film
        r'\bclip\d*\b',            # clip
        r'\.(mp4|avi|mov|wmv|flv)\b',  # 视频文件扩展名
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return text.strip()

def filter_think_content(text: str) -> str:
    """过滤<think>和</think>之间包括这两个标签的内容"""
    if not text:
        return text    
    # 匹配<think>标签（可能包含属性）及其内容
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned_text.strip()