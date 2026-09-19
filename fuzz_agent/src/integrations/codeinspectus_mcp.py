"""
CodeInspectus MCP 集成。
提供代码审查 / 静态分析能力的 MCP 接口，供 AgentScope 等框架调用。
"""

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class CodeInspectusMCP:
    name = "codeinspectus"

    def __init__(self, workspace: str = "."):
        self.workspace = workspace

    def is_available(self) -> bool:
        return MCP_AVAILABLE

    def list_tools(self):
        return [
            {
                "name": "codeinspectus_review",
                "description": "对指定文件或代码片段执行 AI 代码审查",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "文件路径或代码片段"},
                        "rules": {"type": "string", "description": "审查规则，如 PEP8、安全、性能"},
                    },
                    "required": ["target"],
                },
            }
        ]

    async def call_tool(self, tool_name: str, arguments: dict):
        if tool_name == "codeinspectus_review":
            return await self._review(arguments.get("target"), arguments.get("rules", "default"))
        raise ValueError(f"未知工具: {tool_name}")

    async def _review(self, target: str, rules: str):
        # TODO: 集成 CodeReview / CodeInspectus 工具
        return {
            "status": "not_implemented",
            "target": target,
            "rules": rules,
            "message": "CodeInspectus 审查尚未接入",
        }


def create_server():
    if not MCP_AVAILABLE:
        raise RuntimeError("mcp 包未安装，无法启动 CodeInspectus MCP 服务。pip install mcp")
    server = Server("codeinspectus-mcp")
    client = CodeInspectusMCP()

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
