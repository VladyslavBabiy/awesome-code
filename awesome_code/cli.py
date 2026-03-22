import asyncio
import os
import re
import sys

from rich.console import Console
from rich.text import Text
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

from awesome_code import agent, config
from awesome_code.mcp import McpManager
from awesome_code.setup import run_setup

console = Console()

COMMANDS = {
    "/help": "Show available commands",
    "/quit": "Exit AwesomeCode",
    "/clear": "Clear conversation history",
    "/model": "Change the AI model",
    "/setup": "Reconfigure API key & model",
    "/mcp": "Show connected MCP servers & tools",
    "/index": "Index codebase for semantic search (requires Ollama)",
}

FILE_REF_PATTERN = re.compile(r"@(\S+)")

# ── Separator ──────────────────────────────────────────────────


def _sep():
    console.print("[#484848]" + "─" * console.width + "[/#484848]")


# ── Autocomplete ───────────────────────────────────────────────


class InputCompleter(Completer):

    def __init__(self):
        self._file_cache: list[str] | None = None

    def _get_files(self) -> list[str]:
        if self._file_cache is None:
            self._file_cache = _scan_project_files()
        return self._file_cache

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/"):
            for cmd, desc in COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text),
                                     display_meta=desc)
            return

        at_pos = text.rfind("@")
        if at_pos == -1:
            return
        if at_pos > 0 and not text[at_pos - 1].isspace():
            return

        partial = text[at_pos + 1:]
        if not partial:
            return

        partial_lower = partial.lower()
        count = 0
        for full_path in self._get_files():
            filename = os.path.basename(full_path)
            if partial_lower in filename.lower() or partial_lower in full_path.lower():
                yield Completion(
                    f"@{full_path}",
                    start_position=-(len(partial) + 1),
                    display=filename,
                    display_meta=full_path,
                )
                count += 1
                if count >= 20:
                    break


def _scan_project_files() -> list[str]:
    ignored = {".git", "__pycache__", "node_modules", ".venv", "venv",
               ".mypy_cache", ".pytest_cache", "dist", "build", ".tox",
               ".idea", ".vscode"}
    files = []
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = [d for d in dirnames
                       if d not in ignored and not d.endswith(".egg-info")]
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            if path.startswith("./"):
                path = path[2:]
            files.append(path)
    return files


# ── File expansion ─────────────────────────────────────────────


def expand_file_refs(user_input: str) -> str:
    refs = FILE_REF_PATTERN.findall(user_input)
    if not refs:
        return user_input

    clean_text = FILE_REF_PATTERN.sub("", user_input).strip()

    attached = []
    for ref in refs:
        if not os.path.isfile(ref):
            attached.append(f"<attached_file path=\"{ref}\">\n(file not found)\n</attached_file>")
            continue
        try:
            with open(ref, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            attached.append(f"<attached_file path=\"{ref}\">\n{content}\n</attached_file>")
        except OSError as e:
            attached.append(f"<attached_file path=\"{ref}\">\n(error: {e})\n</attached_file>")

    if clean_text:
        return clean_text + "\n\n---\n" + "\n\n".join(attached)
    return "\n\n".join(attached)


# ── Keybindings ────────────────────────────────────────────────


def _make_keybindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter")
    def handle_enter(event):
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    def handle_escape_enter(event):
        event.current_buffer.insert_text("\n")

    return kb


_kb = _make_keybindings()


# ── Input ──────────────────────────────────────────────────────


def get_input() -> str | None:
    try:
        _sep()
        result = pt_prompt(
            HTML("<b fg='ansicyan'>❯ </b>"),
            placeholder=HTML(
                "<style fg='#666666'>"
                "Ask about your code, or type / for commands..."
                "</style>"
            ),
            completer=InputCompleter(),
            complete_while_typing=True,
            multiline=True,
            key_bindings=_kb,
        ).strip()
        _sep()
        return result
    except (EOFError, KeyboardInterrupt):
        return None


# ── Welcome ────────────────────────────────────────────────────


LOGO = r"""
 ▄▀▄ █   █ ██▀ ▄▀▀ ▄▀▄ █▄ ▄█ ██▀   ▄▀▀ ▄▀▄ █▀▄ ██▀
 █▀█ ▀▄▀▄▀ █▄▄ ▀▄▄ ▀▄▀ █ ▀ █ █▄▄   ▀▄▄ ▀▄▀ █▄▀ █▄▄
"""


def print_welcome(mcp_manager: McpManager | None = None):
    from awesome_code.llm import get_model
    from awesome_code.indexing.store import VectorStore
    from awesome_code.indexing import _get_index_dir

    model = get_model()
    cwd = os.getcwd()

    # Index status
    index_dir = _get_index_dir(cwd)
    store = VectorStore(index_dir)
    if store.load():
        hashes = store.get_file_hashes()
        idx_icon, idx_style = "⊙", "green"
        index_status = f"{store.chunk_count()} chunks · {len(hashes)} files"
    else:
        idx_icon, idx_style = "○", "#808080"
        index_status = "not indexed"

    # MCP status
    mcp_count = 0
    if mcp_manager and mcp_manager.has_servers():
        mcp_count = len(mcp_manager.list_servers())
    mcp_icon = "⊙" if mcp_count else "○"
    mcp_style = "green" if mcp_count else "#808080"

    console.print()
    console.print(f"[bold #fab283]{LOGO}[/bold #fab283]")
    console.print(f"  [dim]v0.3.0[/dim]")
    console.print()
    _sep()
    console.print()
    console.print(f"  [#808080]model[/#808080]   {model}")
    console.print(f"  [#808080]dir[/#808080]     {os.path.basename(cwd)}/")
    console.print(
        f"  [#808080]index[/#808080]   [{idx_style}]{idx_icon}[/{idx_style}] {index_status}"
    )
    console.print(
        f"  [#808080]mcp[/#808080]     [{mcp_style}]{mcp_icon}[/{mcp_style}] "
        f"{f'{mcp_count} server(s)' if mcp_count else 'none'}"
    )
    console.print()
    console.print(
        "  [#808080]"
        "[bold]/[/bold] commands  ·  [bold]@[/bold]file attach  ·  "
        "[bold]esc+enter[/bold] newline"
        "[/#808080]"
    )
    console.print()


# ── Command handlers ───────────────────────────────────────────


def handle_mcp_command(mcp_manager: McpManager):
    servers = mcp_manager.list_servers()
    if not servers:
        console.print("  [dim]No MCP servers configured.[/dim]")
        return

    console.print()
    for name, info in servers.items():
        tool_count = len(info.tools) if info.tools else 0
        console.print(
            f"  [green]⊙[/green] [bold]{name}[/bold]  "
            f"[dim]{info.command} · {tool_count} tool(s)[/dim]"
        )
        if info.tools:
            for t in info.tools:
                console.print(f"    [dim]{t._original_name}[/dim]  {t.description[:60]}")
    console.print()


# ── Main loop ──────────────────────────────────────────────────


async def async_main():
    cfg = config.load()

    # Background indexing
    index_task: asyncio.Task | None = None

    async def _run_index():
        from awesome_code.indexing import index_project
        try:
            result = await index_project(os.getcwd())
            console.print(f"  [dim]{result}[/dim]")
        except Exception as e:
            console.print(f"  [yellow]Index: {e}[/yellow]")

    if cfg.get("auto_index", False):
        index_task = asyncio.create_task(_run_index())

    mcp_manager = McpManager()
    try:
        if cfg.get("mcpServers"):
            try:
                await mcp_manager.start(cfg)
            except Exception as e:
                console.print(f"[yellow]MCP warning: {e}[/yellow]")

        print_welcome(mcp_manager)

        messages: list[dict] = []

        while True:
            user_input = await asyncio.to_thread(get_input)
            if user_input is None:
                console.print("\n  [dim]Bye![/dim]")
                break

            if not user_input:
                continue

            if user_input == "/quit":
                console.print("  [dim]Bye![/dim]")
                break

            if user_input == "/clear":
                messages.clear()
                console.print("  [dim]History cleared.[/dim]")
                continue

            if user_input == "/setup":
                run_setup()
                continue

            if user_input == "/mcp":
                handle_mcp_command(mcp_manager)
                continue

            if user_input == "/index":
                from awesome_code.indexing import index_project
                try:
                    result = await index_project(os.getcwd())
                    console.print(f"  [green]{result}[/green]")
                except Exception as e:
                    console.print(f"  [red]Index: {e}[/red]")
                continue

            if user_input == "/model":
                from awesome_code.setup import POPULAR_MODELS
                from rich.prompt import Prompt

                cfg = config.load()
                console.print(f"\n  [dim]Current: {cfg.get('model')}[/dim]\n")
                for i, m in enumerate(POPULAR_MODELS, 1):
                    console.print(f"  [dim]{i}.[/dim] {m}")
                console.print(f"  [dim]{len(POPULAR_MODELS) + 1}.[/dim] Custom")
                choice = Prompt.ask("\n  [bold]Choice[/]", default="1")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(POPULAR_MODELS):
                        model = POPULAR_MODELS[idx]
                    elif idx == len(POPULAR_MODELS):
                        model = Prompt.ask("  [bold]Model ID[/]")
                    else:
                        model = cfg["model"]
                except ValueError:
                    model = choice
                cfg["model"] = model
                config.save(cfg)
                console.print(f"  [green]Model → {model}[/green]\n")
                continue

            if user_input == "/help":
                console.print()
                console.print("  [bold #fab283]Commands[/bold #fab283]")
                console.print()
                for cmd, desc in COMMANDS.items():
                    console.print(f"    [bold]{cmd:16s}[/bold] [dim]{desc}[/dim]")
                console.print()
                console.print("  [bold #fab283]Input[/bold #fab283]")
                console.print()
                console.print("    [bold]@file[/bold]           [dim]Attach file contents[/dim]")
                console.print("    [bold]Esc+Enter[/bold]       [dim]New line[/dim]")
                console.print("    [bold]Enter[/bold]           [dim]Send message[/dim]")
                console.print()
                continue

            if user_input.startswith("/"):
                console.print(f"  [red]Unknown: {user_input}[/red] [dim]type /help[/dim]")
                continue

            try:
                expanded = expand_file_refs(user_input)
                await agent.run(expanded, messages)
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")
            except Exception as e:
                console.print(f"  [red]Error: {e}[/red]")
    finally:
        await mcp_manager.stop()


def main():
    if "--setup" in sys.argv:
        run_setup()
        return

    if not config.is_configured():
        console.print("[yellow]First run — let's set up AwesomeCode.[/yellow]")
        if not run_setup():
            return

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        Console().print("\n  [dim]Bye![/dim]")


if __name__ == "__main__":
    main()
