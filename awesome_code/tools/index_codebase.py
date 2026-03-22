import os

from awesome_code.tools.base import BaseTool


class IndexCodebaseTool(BaseTool):
    name = "index_codebase"
    description = (
        "Index the current codebase for semantic search. "
        "Scans code files, generates embeddings via Ollama, "
        "and stores them locally. Uses incremental indexing — "
        "only re-indexes changed files. Requires Ollama running locally."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Root directory to index (default: current directory)",
            },
            "force": {
                "type": "boolean",
                "description": "Force full re-index, ignoring cache (default: false)",
            },
        },
        "required": [],
    }

    def execute(self, **kwargs) -> str:
        raise RuntimeError("IndexCodebaseTool must be called via execute_async")

    async def execute_async(self, **kwargs) -> str:
        from awesome_code.indexing import index_project

        path = kwargs.get("path", os.getcwd())
        force = kwargs.get("force", False)
        return await index_project(path, force=force)
