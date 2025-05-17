from config import Config

def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """
    将文本分块处理
    :param text: 输入文本
    :param chunk_size: 每块大小，默认使用Config.DEFAULT_CHUNK_SIZE
    :param overlap: 重叠部分大小，默认使用Config.DEFAULT_OVERLAP
    :return: 分块后的文本列表
    """
    chunk_size = chunk_size or Config.DEFAULT_CHUNK_SIZE
    overlap = overlap or Config.DEFAULT_OVERLAP
    chunks = []
    start = 0
    end = chunk_size
    text_length = len(text)
    
    while start < text_length:
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
        end = start + chunk_size
        
        # 确保最后一块不会超出文本长度
        if end > text_length:
            end = text_length
    
    return chunks
