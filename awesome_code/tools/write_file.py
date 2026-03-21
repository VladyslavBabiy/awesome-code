import os

from awesome_code.tools.base import BaseTool


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file. Creates the file and parent directories if they don't exist. Overwrites existing content."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    }

    def execute(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        content = kwargs["content"]

        try:
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return f"Successfully wrote {lines} lines to {file_path}"
        except Exception as e:
            return f"Error writing file: {e}"
