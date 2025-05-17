import os

def write_content_to_file(content: str, filename: str = "text_add_keywords.txt") -> str:
    """
    将内容写入文件（如果文件不存在则创建）
    :param content: 要写入的文本内容
    :param filename: 文件名（默认 text_add_keywords.txt）
    :return: 文件路径
    """
    filepath = os.path.join("data", filename)
    with open(filepath, "a", encoding="utf-8") as file:
        file.write(content + "\n")  # 追加内容并换行
    return filepath
