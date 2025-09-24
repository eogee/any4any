import re

def clean_img_text(text: str)  -> str:
    """过滤img标签及内容"""
    pattern_full_img = r'<img\b[^>]*>'                      # 匹配完整标签
    pattern_start_img = r'<img\b[^>]*$'                     # 匹配开头标签
    pattern_end_alt = r'[^<]*alt="image">'                  # 匹配结尾alt标签

    cleaned = re.sub(pattern_full_img, '', text)
    if cleaned != text:                                     # 如果完整标签被替换过，直接返回结果
        return cleaned.strip()

    cleaned = re.sub(pattern_start_img, '', cleaned)
    cleaned = re.sub(pattern_end_alt, '', cleaned)
    return cleaned.strip()

def clean_video_text(text: str)  -> str:
    """过滤video标签及内容"""
    pattern_full_video = r'<video\b[^>]*>[\s\S]*?</video>'  # 匹配完整标签
    pattern_start_video = r'<video\b[\s\S]*$'               # 匹配开头标签
    pattern_end_video = r'[\s\S]*?</video>'                 # 匹配结尾标签

    cleaned = re.sub(pattern_full_video, '', text, flags=re.DOTALL)
    if cleaned != text:                                     # 如果完整标签被替换过，直接返回结果
        return cleaned.strip()

    cleaned = re.sub(pattern_start_video, '', cleaned)
    cleaned = re.sub(pattern_end_video, '', cleaned)
    return cleaned.strip()

def filter_special_chars(text: str) -> str:
    """过滤文本转语音特殊字符"""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'[#*]', '', text)
    text = clean_img_text(text)
    text = clean_video_text(text)
    return text

def filter_think_content(text: str) -> str:
    """过滤<think>和</think>之间包括这两个标签的内容"""
    if not text:
        return text    
    # 匹配<think>标签（可能包含属性）及其内容
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned_text.strip()