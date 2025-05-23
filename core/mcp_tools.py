from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tools")

@mcp.tool()
def add(a: int, b: int) -> int:
    """两个整数相加"""
    return a + b

@mcp.tool()
def sub(a: int, b: int) -> int:
    """两个整数相减"""
    return a - b

@mcp.tool()
def mul(a: int, b: int) -> int:
    """两个整数相乘"""
    return a * b

@mcp.tool()
def div(a: int, b: int) -> float:
    """两个整数相除"""
    return a / b