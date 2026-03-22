import os

MEMORY_DIR = ".awesome-code"
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.md")


def load_memory() -> str | None:
    """Load memory bank content if it exists."""
    if not os.path.isfile(MEMORY_FILE):
        return None
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def memory_exists() -> bool:
    """Check if memory bank has been initialized."""
    return os.path.isfile(MEMORY_FILE)
