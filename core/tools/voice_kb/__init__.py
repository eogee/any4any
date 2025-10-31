"""
Voice Knowledge Base Tool
语音知识库工具模块
"""

# 延迟导入以避免循环依赖
def get_voice_data_manager():
    from core.tools.voice_kb.voice_data_manager import get_voice_data_manager as _get_voice_data_manager
    return _get_voice_data_manager()

def get_voice_workflow():
    from core.tools.voice_kb.voice_workflow import get_voice_workflow as _get_voice_workflow
    return _get_voice_workflow()

__all__ = [
    'get_voice_data_manager',
    'get_voice_workflow'
]