from awesome_code.tools.base import BaseTool
from awesome_code.tools.read_file import ReadFileTool
from awesome_code.tools.write_file import WriteFileTool
from awesome_code.tools.bash import BashTool
from awesome_code.tools.list_dir import ListDirTool
from awesome_code.tools.index_codebase import IndexCodebaseTool
from awesome_code.tools.search_codebase import SearchCodebaseTool
from awesome_code.tools.load_skill import LoadSkillTool

_BUILTIN_TOOLS = [
    ReadFileTool(), WriteFileTool(), BashTool(), ListDirTool(),
    IndexCodebaseTool(), SearchCodebaseTool(), LoadSkillTool(),
]

ALL_TOOLS: list[BaseTool] = list(_BUILTIN_TOOLS)
TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}


def register_tools(tools: list[BaseTool]):
    """Add MCP tools to the registry."""
    for t in tools:
        ALL_TOOLS.append(t)
        TOOLS_BY_NAME[t.name] = t


def unregister_mcp_tools():
    """Remove all MCP tools from the registry."""
    from awesome_code.mcp.tool import McpTool
    ALL_TOOLS[:] = [t for t in ALL_TOOLS if not isinstance(t, McpTool)]
    TOOLS_BY_NAME.clear()
    TOOLS_BY_NAME.update({t.name: t for t in ALL_TOOLS})


def get_tools_for_api() -> list[dict]:
    return [t.to_openai_tool() for t in ALL_TOOLS]
