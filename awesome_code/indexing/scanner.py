import hashlib
import os
from dataclasses import dataclass

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".egg-info", ".tox", ".DS_Store", ".idea", ".vscode",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".sh", ".bash", ".zsh", ".sql", ".yaml",
    ".yml", ".toml", ".json", ".md", ".html", ".css", ".scss",
    ".xml", ".gradle", ".cmake", ".lua", ".r", ".jl",
}

MAX_FILE_SIZE = 1_000_000  # 1 MB


@dataclass
class ScannedFile:
    path: str
    rel_path: str
    sha256: str
    size: int


def compute_file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_project_hash(root: str) -> str:
    return hashlib.sha256(os.path.abspath(root).encode()).hexdigest()[:16]


def scan_directory(root: str) -> list[ScannedFile]:
    root = os.path.abspath(root)
    results: list[ScannedFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORE_DIRS and not d.endswith(".egg-info")
        ]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in CODE_EXTENSIONS:
                continue

            full_path = os.path.join(dirpath, fname)

            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue

            if size > MAX_FILE_SIZE or size == 0:
                continue

            rel_path = os.path.relpath(full_path, root)
            file_hash = compute_file_hash(full_path)

            results.append(ScannedFile(
                path=full_path,
                rel_path=rel_path,
                sha256=file_hash,
                size=size,
            ))

    return results
