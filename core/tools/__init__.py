"""
Any4Any 工具系统统一接口
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .tool_registry import get_tool_registry, process_with_tools
from .result import ToolResult

logger = logging.getLogger(__name__)


def get_available_tools() -> List[Dict[str, Any]]:
    """获取所有可用工具信息"""
    try:
        registry = get_tool_registry()
        return registry.get_available_tools()
    except Exception as e:
        logger.error(f"Failed to get available tools: {e}")
        return []

async def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
    """执行指定工具"""
    try:
        registry = get_tool_registry()
        return await registry.execute_tool_by_name(tool_name, parameters)
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return ToolResult.error_result(f"工具执行失败: {str(e)}", tool_name=tool_name)

def get_tool_status() -> Dict[str, Any]:
    """获取工具系统状态"""
    try:
        registry = get_tool_registry()
        return registry.get_tool_status()
    except Exception as e:
        logger.error(f"Failed to get tool status: {e}")
        return {"error": str(e)}

# 兼容原接口的导出
def get_tool_manager():
    """兼容原get_tool_manager接口"""
    return get_tool_registry()

# 各工具的快速访问接口
def get_nl2sql_tool():
    """获取NL2SQL工具"""
    from .nl2sql.workflow import get_nl2sql_tool
    return get_nl2sql_tool()

def get_voice_kb_tool():
    """获取语音知识库工具"""
    from .voice_kb.workflow import get_voice_kb_tool
    return get_voice_kb_tool()


def get_time_tool():
    """获取时间工具"""
    from .time.workflow import get_time_tool
    return get_time_tool()

def get_adb_tool():
    """获取ADB工具"""
    from .adb.workflow import get_adb_tool
    return get_adb_tool()

def get_web_search_tool():
    """获取Web搜索工具"""
    from .web_search.workflow import get_web_search_tool
    return get_web_search_tool()

# 向后兼容的接口
try:
    from .voice_kb.voice_workflow import get_voice_workflow
    VOICE_WORKFLOW_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import voice workflow: {e}")
    VOICE_WORKFLOW_AVAILABLE = False
    get_voice_workflow = None

try:
    from .nl2sql.workflow import get_nl2sql_workflow
    NL2SQL_WORKFLOW_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import NL2SQL workflow: {e}")
    NL2SQL_WORKFLOW_AVAILABLE = False
    get_nl2sql_workflow = None

try:
    from .adb import login, logout
    ADB_TOOLS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import ADB tools: {e}")
    ADB_TOOLS_AVAILABLE = False

# 构建导出列表
__all__ = [
    'get_available_tools',
    'execute_tool',
    'process_with_tools',
    'get_tool_status',
    'get_tool_manager',
    'get_nl2sql_tool',
    'get_voice_kb_tool',
    'get_time_tool',
    'get_adb_tool',
    'get_web_search_tool',
    'ToolResult'
]

# 添加向后兼容的导出
if VOICE_WORKFLOW_AVAILABLE:
    __all__.append('get_voice_workflow')

if NL2SQL_WORKFLOW_AVAILABLE:
    __all__.append('get_nl2sql_workflow')


__all__.extend([
    'VOICE_WORKFLOW_AVAILABLE',
    'NL2SQL_WORKFLOW_AVAILABLE',
    'ADB_TOOLS_AVAILABLE'
])