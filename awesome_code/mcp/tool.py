from awesome_code.tools.base import BaseTool


class McpTool(BaseTool):
    """Wraps an MCP server tool as a BaseTool for the agent."""

    def __init__(self, server_name: str, tool_name: str, description: str,
                 input_schema: dict, session):
        self.name = f"{server_name}__{tool_name}"
        self.description = description or f"MCP tool: {tool_name}"
        self.parameters = input_schema or {"type": "object", "properties": {}}
        self._server_name = server_name
        self._original_name = tool_name
        self._session = session

    def execute(self, **kwargs) -> str:
        raise RuntimeError("McpTool must be called via execute_async")

    async def execute_async(self, **kwargs) -> str:
        result = await self._session.call_tool(self._original_name, kwargs)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) if parts else "(no output)"
