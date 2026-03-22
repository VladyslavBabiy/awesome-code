import os

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn

from awesome_code import config
from awesome_code.indexing.scanner import scan_directory, compute_project_hash
from awesome_code.indexing.chunker import chunk_file
from awesome_code.indexing.embedder import embed_texts, embed_single, check_ollama, OllamaError
from awesome_code.indexing.store import VectorStore

console = Console()
INDEX_BASE = os.path.join(os.path.expanduser("~"), ".awesome-code", "index")


def _get_index_dir(root: str) -> str:
    project_hash = compute_project_hash(root)
    return os.path.join(INDEX_BASE, project_hash)


def _get_config() -> tuple[str, str]:
    cfg = config.load()
    ollama_url = cfg.get("ollama_url", "http://localhost:11434")
    embed_model = cfg.get("embed_model", "nomic-embed-text")
    return ollama_url, embed_model


async def index_project(root: str, force: bool = False) -> str:
    ollama_url, embed_model = _get_config()

    if not await check_ollama(ollama_url):
        raise OllamaError(
            "Ollama is not running. Start it with: ollama serve\n"
            f"Then pull the model: ollama pull {embed_model}"
        )

    index_dir = _get_index_dir(root)
    store = VectorStore(index_dir)

    old_hashes: dict[str, str] = {}
    if not force:
        store.load()
        old_hashes = store.get_file_hashes()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TextColumn("[dim]{task.fields[detail]}[/dim]"),
        console=console,
    )
    progress.start()

    try:
        # Phase 1: Scan
        scan_task = progress.add_task("Scanning", total=1, detail="...")
        scanned = scan_directory(root)
        progress.update(scan_task, completed=1, detail=f"{len(scanned)} files")

        new_hashes = {f.rel_path: f.sha256 for f in scanned}
        new_files = [f for f in scanned if f.rel_path not in old_hashes]
        changed_files = [
            f for f in scanned
            if f.rel_path in old_hashes and old_hashes[f.rel_path] != f.sha256
        ]
        deleted_paths = [p for p in old_hashes if p not in new_hashes]

        if force:
            files_to_index = scanned
        else:
            files_to_index = new_files + changed_files

        if not files_to_index and not deleted_paths:
            progress.stop()
            return (
                f"Index is up to date. "
                f"{store.chunk_count()} chunks across {len(old_hashes)} files."
            )

        # Remove stale data
        for f in changed_files:
            store.remove_file(f.rel_path)
        for p in deleted_paths:
            store.remove_file(p)

        # Phase 2: Chunk
        total_files = len(files_to_index)
        chunk_task = progress.add_task("Chunking", total=total_files,
                                       detail=f"0/{total_files} files")
        all_chunks = []
        file_hashes: dict[str, str] = {}

        for i, f in enumerate(files_to_index, 1):
            try:
                with open(f.path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except OSError:
                progress.advance(chunk_task)
                continue

            chunks = chunk_file(f.rel_path, content)
            if chunks:
                all_chunks.extend(chunks)
                file_hashes[f.rel_path] = f.sha256

            progress.update(chunk_task, completed=i,
                            detail=f"{i}/{total_files} → {len(all_chunks)} chunks")

        if not all_chunks:
            progress.stop()
            store.save()
            return "No indexable content found in changed files."

        # Phase 3: Embed
        total_chunks = len(all_chunks)
        embed_task = progress.add_task("Embedding", total=total_chunks,
                                       detail=f"0/{total_chunks} · {embed_model}")
        embedded = 0

        def on_batch_done(count: int):
            nonlocal embedded
            embedded += count
            progress.update(embed_task, completed=embedded,
                            detail=f"{embedded}/{total_chunks} · {embed_model}")

        texts = [c.content for c in all_chunks]
        vectors = await embed_texts(
            texts, model=embed_model, ollama_url=ollama_url,
            on_batch_done=on_batch_done,
        )

        # Phase 4: Save
        save_task = progress.add_task("Saving", total=1, detail="...")
        store.add(all_chunks, vectors, file_hashes)
        store.save()
        progress.update(save_task, completed=1,
                        detail=f"{store.chunk_count()} chunks")

    finally:
        progress.stop()

    return (
        f"Indexed {len(files_to_index)} file(s) "
        f"({len(new_files)} new, {len(changed_files)} updated, "
        f"{len(deleted_paths)} deleted). "
        f"Total: {store.chunk_count()} chunks."
    )


async def search_project(root: str, query: str, top_k: int = 10) -> str:
    ollama_url, embed_model = _get_config()

    index_dir = _get_index_dir(root)
    store = VectorStore(index_dir)

    if not store.load():
        return (
            "No index found for this project. "
            "Run /index or use the index_codebase tool first."
        )

    query_vector = await embed_single(query, model=embed_model, ollama_url=ollama_url)
    results = store.search(query_vector, top_k=top_k)

    if not results:
        return f"No relevant results found for: {query}"

    lines = [f"Found {len(results)} result(s) for \"{query}\":\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"--- Result {i} (score: {r.score:.3f}) ---\n"
            f"File: {r.file_path} (lines {r.start_line}-{r.end_line})\n"
            f"{r.content}\n"
        )

    return "\n".join(lines)
