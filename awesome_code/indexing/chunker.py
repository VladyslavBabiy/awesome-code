import re
from dataclasses import dataclass

# Patterns that signal the start of a new code block
BOUNDARY_PATTERNS = re.compile(
    r"^(?:"
    r"(?:export\s+)?(?:async\s+)?(?:def |class |function |fn |func )"
    r"|(?:pub(?:\(crate\))?\s+)?(?:fn |struct |enum |impl |trait |mod )"
    r"|(?:public|private|protected)\s+(?:static\s+)?(?:class |interface |record |enum |void |int |String |boolean |long |double |float |[\w<>\[\]]+\s+\w+\s*\()"
    r"|(?:export\s+)?(?:const |let |var |type |interface )\w+.*[={]"
    r"|@\w+|#\[|package |import "
    r")",
    re.MULTILINE,
)

MAX_CHUNK_LINES = 100
MIN_CHUNK_LINES = 3
FIXED_CHUNK_SIZE = 60
FIXED_CHUNK_OVERLAP = 10


@dataclass
class Chunk:
    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_type: str


def chunk_file(rel_path: str, content: str) -> list[Chunk]:
    lines = content.splitlines(keepends=True)
    if not lines:
        return []

    boundaries = _find_boundaries(lines)

    if len(boundaries) < 2:
        return _fixed_chunks(rel_path, lines)

    return _smart_chunks(rel_path, lines, boundaries)


def _find_boundaries(lines: list[str]) -> list[int]:
    boundaries = [0]
    for i, line in enumerate(lines):
        if i == 0:
            continue
        stripped = line.lstrip()
        if BOUNDARY_PATTERNS.match(stripped):
            # Only treat as boundary if it's at a reasonable indent level
            indent = len(line) - len(stripped)
            if indent <= 8:
                boundaries.append(i)
    return boundaries


def _smart_chunks(rel_path: str, lines: list[str], boundaries: list[int]) -> list[Chunk]:
    chunks: list[Chunk] = []
    boundaries.append(len(lines))  # sentinel

    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]

        # Merge small chunks with next
        if end - start < MIN_CHUNK_LINES and i < len(boundaries) - 2:
            boundaries[i + 1] = start
            continue

        # Sub-split large chunks
        if end - start > MAX_CHUNK_LINES:
            sub = _fixed_chunks(rel_path, lines[start:end], offset=start)
            chunks.extend(sub)
        else:
            chunk_lines = lines[start:end]
            header = f"# File: {rel_path} (lines {start + 1}-{end})\n"
            chunks.append(Chunk(
                file_path=rel_path,
                start_line=start + 1,
                end_line=end,
                content=header + "".join(chunk_lines),
                chunk_type="block",
            ))

    return chunks


def _fixed_chunks(rel_path: str, lines: list[str], offset: int = 0) -> list[Chunk]:
    chunks: list[Chunk] = []
    i = 0
    while i < len(lines):
        end = min(i + FIXED_CHUNK_SIZE, len(lines))
        chunk_lines = lines[i:end]
        start_line = offset + i + 1
        end_line = offset + end

        header = f"# File: {rel_path} (lines {start_line}-{end_line})\n"
        chunks.append(Chunk(
            file_path=rel_path,
            start_line=start_line,
            end_line=end_line,
            content=header + "".join(chunk_lines),
            chunk_type="fixed",
        ))

        if end >= len(lines):
            break
        i = end - FIXED_CHUNK_OVERLAP

    return chunks
