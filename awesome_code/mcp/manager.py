from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

from awesome_code.mcp.tool import McpTool

console = Console()


@dataclass
class ServerInfo:
    name: str
    command: str
    session: ClientSession
    tools: list[McpTool] = field(default_factory=list)


class McpManager:
    """Manages MCP server connections and tool discovery."""
    """MCP Expample
    "mcpServers": {
      "context7": {
        "command": "npx",
        "args": [
          "-y",
          "@upstash/context7-mcp"
        ],
        "env": {}
        }
    }
    """

    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self._servers: dict[str, ServerInfo] = {}

    async def start(self, config: dict):
        """Connect to all configured MCP servers and discover their tools."""
        from awesome_code.tools import register_tools

        servers_cfg = config.get("mcpServers", {})
        if not servers_cfg:
            return

        for name, srv_cfg in servers_cfg.items():
            try:
                await self._connect_server(name, srv_cfg)
            except Exception as e:
                console.print(f"[yellow]MCP [{name}]: failed to connect — {e}[/yellow]")
                continue

            # Register discovered tools in the global registry
            server = self._servers[name]
            if server.tools:
                register_tools(server.tools)
                console.print(
                    f"[dim]MCP [{name}]: {len(server.tools)} tool(s) loaded[/dim]"
                )

    async def _connect_server(self, name: str, srv_cfg: dict):
        """Connect to a single MCP server via stdio."""
        params = StdioServerParameters(
            command=srv_cfg["command"],
            args=srv_cfg.get("args", []),
            env=srv_cfg.get("env"),
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        read_stream, write_stream = stdio_transport

        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        # Discover tools
        tools_result = await session.list_tools()
        mcp_tools = []
        for t in tools_result.tools:
            mcp_tool = McpTool(
                server_name=name,
                tool_name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema if t.inputSchema else {},
                session=session,
            )
            mcp_tools.append(mcp_tool)

        self._servers[name] = ServerInfo(
            name=name,
            command=srv_cfg["command"],
            session=session,
            tools=mcp_tools,
        )

    async def stop(self):
        """Shut down all MCP servers and clean up."""
        try:
            await self._exit_stack.aclose()
        except Exception:
            pass
        self._servers.clear()

    def list_servers(self) -> dict[str, ServerInfo]:
        return dict(self._servers)

    def has_servers(self) -> bool:
        return bool(self._servers)
