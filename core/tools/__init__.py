"""
Tools module for various AI tool functionalities
"""

# Import voice_kb for easy access
try:
    from core.tools.voice_kb import get_voice_workflow
    __all__ = ['get_voice_workflow']
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import voice_kb: {e}")
    __all__ = []

# Import ADB LLM interface for easy access
try:
    from core.tools.adb.llm_interface import ADB_LLM_TOOLS
    __all__.extend(['ADB_LLM_TOOLS'])
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import ADB LLM interface: {e}")