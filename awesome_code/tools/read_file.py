import os

from awesome_code.tools.base import BaseTool


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file. Returns lines with line numbers."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based). Optional.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read. Optional.",
            },
        },
        "required": ["file_path"],
    }

    def execute(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit")

        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        if os.path.isdir(file_path):
            entries = os.listdir(file_path)
            return "Directory listing:\n" + "\n".join(entries)

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading file: {e}"

        start = max(0, offset - 1)
        end = start + limit if limit else len(lines)
        selected = lines[start:end]

        result = []
        for i, line in enumerate(selected, start=start + 1):
            result.append(f"{i:>4}\t{line.rstrip()}")

        if not result:
            return "(empty file)"

        return "\n".join(result)
