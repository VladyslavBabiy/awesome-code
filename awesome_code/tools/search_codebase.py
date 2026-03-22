import os

from awesome_code.tools.base import BaseTool


class SearchCodebaseTool(BaseTool):
    name = "search_codebase"
    description = (
        "Semantically search the indexed codebase. "
        "Find code by meaning, not just text matching. "
        "The codebase must be indexed first with index_codebase. "
        "Returns relevant code snippets with file paths and line numbers."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural language search query "
                    "(e.g. 'authentication logic', 'database connection handling')"
                ),
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default: 10)",
            },
        },
        "required": ["query"],
    }

    def execute(self, **kwargs) -> str:
        raise RuntimeError("SearchCodebaseTool must be called via execute_async")

    async def execute_async(self, **kwargs) -> str:
        from awesome_code.indexing import search_project

        query = kwargs["query"]
        top_k = kwargs.get("top_k", 10)
        return await search_project(os.getcwd(), query, top_k=top_k)
