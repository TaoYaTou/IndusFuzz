"""
CodeGuard MCP 集成。
提供代码安全审计能力的 MCP 接口，供 AgentScope 等框架调用。
"""

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class CodeGuardMCP:
    name = "codeguard"

    def __init__(self, scan_root: str = "."):
        self.scan_root = scan_root

    def is_available(self) -> bool:
        return MCP_AVAILABLE

    def list_tools(self):
        return [
            {
                "name": "codeguard_audit",
                "description": "对指定目录执行代码安全审计",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "待审计目录"},
                        "level": {"type": "string", "enum": ["quick", "deep"], "default": "quick"},
                    },
                    "required": ["path"],
                },
            }
        ]

    async def call_tool(self, tool_name: str, arguments: dict):
        if tool_name == "codeguard_audit":
            return await self._audit(arguments.get("path"), arguments.get("level", "quick"))
        raise ValueError(f"未知工具: {tool_name}")

    async def _audit(self, path: str, level: str):
        # TODO: 集成 Bandit / fenceline / Codeaudit 等 SAST 工具
        return {
            "status": "not_implemented",
            "path": path,
            "level": level,
            "message": "CodeGuard 审计尚未接入",
        }


def create_server():
    if not MCP_AVAILABLE:
        raise RuntimeError("mcp 包未安装，无法启动 CodeGuard MCP 服务。pip install mcp")
    server = Server("codeguard-mcp")
    client = CodeGuardMCP()

    @server.list_tools()
    async def list_tools():
        return [Tool(**t) for t in client.list_tools()]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = await client.call_tool(name, arguments)
        return [TextContent(type="text", text=str(result))]

    return server


async def main():
    server = create_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
