import os

from awesome_code.tools.base import BaseTool

IGNORE = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".egg-info", ".tox", ".DS_Store",
}


class ListDirTool(BaseTool):
    name = "list_dir"
    description = (
        "List the directory structure as a tree. "
        "Useful for understanding how a project is organized. "
        "Automatically skips common non-essential directories like .git, node_modules, __pycache__."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list (default: current directory)",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum depth to recurse (default: 3)",
            },
        },
        "required": [],
    }

    def execute(self, **kwargs) -> str:
        path = kwargs.get("path", ".")
        max_depth = kwargs.get("max_depth", 3)

        if not os.path.isdir(path):
            return f"Error: Not a directory: {path}"

        lines = []
        self._walk(path, "", 0, max_depth, lines)

        if not lines:
            return "(empty directory)"

        return "\n".join(lines)

    def _walk(self, path: str, prefix: str, depth: int, max_depth: int, lines: list):
        if depth >= max_depth:
            return

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            lines.append(f"{prefix}[permission denied]")
            return

        dirs = []
        files = []
        for e in entries:
            if e in IGNORE or e.endswith(".egg-info"):
                continue
            full = os.path.join(path, e)
            if os.path.isdir(full):
                dirs.append(e)
            else:
                files.append(e)

        items = [(d, True) for d in dirs] + [(f, False) for f in files]

        for i, (name, is_dir) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            if is_dir:
                lines.append(f"{prefix}{connector}{name}/")
                extension = "    " if is_last else "│   "
                self._walk(
                    os.path.join(path, name),
                    prefix + extension,
                    depth + 1,
                    max_depth,
                    lines,
                )
            else:
                lines.append(f"{prefix}{connector}{name}")
