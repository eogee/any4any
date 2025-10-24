"""
自然语言转SQL（NL2SQL）工具模块

本模块提供将自然语言问题转换为SQL查询并执行的 工具。
"""

from .table_info import get_all_tables, get_relevant_tables
from .sql_executor import generate_and_execute_sql

__all__ = [
    'get_all_tables',
    'get_relevant_tables',
    'generate_and_execute_sql'
]