import re

def process_keywords(keywords: str) -> str:
    """
    处理关键词内容
    :param keywords: 原始关键词内容
    :return: 处理后的文本内容
    """
    # 过滤各种形式的<think>标签并拼接<<<<<
    return re.sub(r'<think\b[^>]*>.*?</think>', '', keywords, flags=re.DOTALL) + "<<<<<"
