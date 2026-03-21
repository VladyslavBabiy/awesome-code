from awesome_code.tools.read_file import ReadFileTool
from awesome_code.tools.write_file import WriteFileTool
from awesome_code.tools.bash import BashTool
from awesome_code.tools.list_dir import ListDirTool

ALL_TOOLS = [ReadFileTool(), WriteFileTool(), BashTool(), ListDirTool()]

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}


def get_tools_for_api() -> list[dict]:
    return [t.to_openai_tool() for t in ALL_TOOLS]
