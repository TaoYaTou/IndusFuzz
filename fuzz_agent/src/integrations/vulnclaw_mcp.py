"""
VulnClaw MCP 集成。
提供漏洞扫描/渗透测试能力的 MCP 接口，供 AgentScope 等框架调用。
"""

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class VulnClawMCP:
    name = "vulnclaw"

    def __init__(self, ollama_base_url="http://localhost:11434", model="qwen2.5-coder:14b"):
        self.ollama_base_url = ollama_base_url
        self.model = model

    def is_available(self) -> bool:
        return MCP_AVAILABLE

    def list_tools(self):
        return [
            {
                "name": "vulnclaw_scan",
                "description": "对指定目标执行漏洞扫描",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "目标 URL 或 IP"},
                        "mode": {"type": "string", "enum": ["quick", "full"], "default": "quick"},
                    },
                    "required": ["target"],
                },
            }
        ]

    async def call_tool(self, tool_name: str, arguments: dict):
        if tool_name == "vulnclaw_scan":
            return await self._scan(arguments.get("target"), arguments.get("mode", "quick"))
        raise ValueError(f"未知工具: {tool_name}")

    async def _scan(self, target: str, mode: str):
        # TODO: 集成 VulnClaw 实际扫描逻辑
        return {
            "status": "not_implemented",
            "target": target,
            "mode": mode,
            "message": "VulnClaw 扫描尚未接入，请先在环境变量中配置授权",
        }


def create_server():
    if not MCP_AVAILABLE:
        raise RuntimeError("mcp 包未安装，无法启动 VulnClaw MCP 服务。pip install mcp")
    server = Server("vulnclaw-mcp")
    client = VulnClawMCP()

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
