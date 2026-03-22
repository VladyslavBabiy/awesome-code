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

from awesome_code import agent, agent_manager, agents, config, skills
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
    "/skills": "List available skills",
    "/agents": "List available sub-agents",
    "/switch": "Switch context to a sub-agent (or back to main)",
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
            # Also suggest skills
            for name in skills.discover_skills():
                skill_cmd = f"/{name}"
                if skill_cmd.startswith(text) and skill_cmd not in COMMANDS:
                    yield Completion(skill_cmd, start_position=-len(text),
                                     display_meta="skill")
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


def get_input(context: str = "main") -> str | None:
    try:
        # Show agent status bar if there are running agents
        status_bar = agent_manager.format_status_bar()
        if status_bar:
            console.print(status_bar)
        _sep()

        if context == "main":
            prompt_text = HTML("<b fg='ansicyan'>❯ </b>")
        else:
            prompt_text = HTML(f"<b fg='ansimagenta'>[{context}]</b> <b fg='ansicyan'>❯ </b>")

        result = pt_prompt(
            prompt_text,
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
    console.print(f"  [dim]v0.4.0[/dim]")
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

    # Skills status
    skill_list = skills.discover_skills()
    if skill_list:
        console.print(f"  [#808080]skills[/#808080]  [green]⊙[/green] {len(skill_list)} loaded")

    # Agents status
    agent_list = agents.discover_agents()
    if agent_list:
        console.print(f"  [#808080]agents[/#808080]  [green]⊙[/green] {len(agent_list)} loaded")

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


# ── Switch picker ─────────────────────────────────────────────


def _show_agent_header(entry, target: str):
    """Show agent header + result/status when switching context."""
    style, icon = agent_manager.STATUS_ICONS[entry.status]
    console.print()
    console.print(
        f"  ─── [magenta]{target}[/magenta] "
        f"{style}{icon}[/] "
        f"{'─' * max(1, console.width - len(target) - 10)}"
    )
    console.print(f"  [dim]Task: {entry.task}[/dim]")
    console.print()
    if entry.status == agent_manager.AgentStatus.COMPLETED and entry.result:
        from rich.markdown import Markdown
        console.print(Markdown(entry.result))
        console.print()
    elif entry.status == agent_manager.AgentStatus.FAILED:
        console.print(f"  [red]Error: {entry.error}[/red]")
        console.print()
    elif entry.status == agent_manager.AgentStatus.RUNNING:
        console.print("  [bright_yellow]⟳ Still working...[/bright_yellow]")
        console.print()


def _interactive_switch(current_context: str) -> str:
    """Interactive arrow-key picker for /switch. Returns selected context name."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings as KB
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout import Layout

    # Build choices: main + deduplicated agents
    all_tasks = agent_manager.list_all()
    latest: dict[str, agent_manager.SubAgentTask] = {}
    for t in all_tasks:
        latest[t.name] = t

    choices: list[tuple[str, str]] = [("main", "primary agent")]
    for t in latest.values():
        style, icon = agent_manager.STATUS_ICONS[t.status]
        task_preview = t.task[:50] + ("..." if len(t.task) > 50 else "")
        choices.append((t.name, f"{icon} {t.status.value}  {task_preview}"))

    if len(choices) == 1:
        console.print("  [dim]No sub-agents spawned yet.[/dim]")
        return current_context

    # Find initial cursor position
    selected = [0]
    for i, (name, _) in enumerate(choices):
        if name == current_context:
            selected[0] = i
            break

    result = [current_context]

    def _get_text():
        lines = []
        lines.append(("bold", "  Switch context\n"))
        lines.append(("", "\n"))
        for i, (name, desc) in enumerate(choices):
            if i == selected[0]:
                lines.append(("bold fg:ansicyan", f"  → {name}"))
                lines.append(("fg:#808080", f"  {desc}\n"))
            else:
                lines.append(("", f"    {name}"))
                lines.append(("fg:#808080", f"  {desc}\n"))
        lines.append(("", "\n"))
        lines.append(("fg:#808080", "  ↑↓ navigate  enter select  esc cancel"))
        return lines

    kb = KB()

    @kb.add("up")
    def _up(event):
        selected[0] = max(0, selected[0] - 1)

    @kb.add("down")
    def _down(event):
        selected[0] = min(len(choices) - 1, selected[0] + 1)

    @kb.add("enter")
    def _enter(event):
        result[0] = choices[selected[0]][0]
        event.app.exit()

    @kb.add("escape")
    def _escape(event):
        event.app.exit()

    @kb.add("c-c")
    def _ctrl_c(event):
        event.app.exit()

    control = FormattedTextControl(_get_text)
    app = Application(
        layout=Layout(HSplit([Window(content=control)])),
        key_bindings=kb,
        full_screen=False,
    )
    app.run()

    return result[0]


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
        current_context = "main"

        while True:
            user_input = await asyncio.to_thread(get_input, current_context)
            if user_input is None:
                console.print("\n  [dim]Bye![/dim]")
                break

            if not user_input:
                continue

            if user_input == "/quit":
                console.print("  [dim]Bye![/dim]")
                break

            if user_input == "/clear":
                if current_context == "main":
                    messages.clear()
                else:
                    entry = agent_manager.get_by_name(current_context)
                    if entry:
                        entry.messages.clear()
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

            if user_input == "/skills":
                skill_items = skills.list_skills()
                if not skill_items:
                    console.print("  [dim]No skills found.[/dim]")
                    console.print(
                        "  [dim]Create ~/.awesome-code/skills/name.md "
                        "or .awesome-code/skills/name.md[/dim]"
                    )
                else:
                    console.print()
                    console.print("  [bold #fab283]Skills[/bold #fab283]")
                    console.print()
                    for name, source, desc in skill_items:
                        badge = "[dim](project)[/dim]" if source == "project" else "[dim](global)[/dim]"
                        console.print(f"    [bold]/{name:16s}[/bold] {desc}  {badge}")
                    console.print()
                    console.print("  [dim]Usage: /skill-name your message here[/dim]")
                    console.print()
                continue

            if user_input == "/agents":
                agent_items = agents.list_agents()
                if not agent_items:
                    console.print("  [dim]No agents found.[/dim]")
                    console.print(
                        "  [dim]Create ~/.awesome-code/agents/name.md "
                        "or .awesome-code/agents/name.md[/dim]"
                    )
                else:
                    console.print()
                    console.print("  [bold #fab283]Sub-Agents[/bold #fab283]")
                    console.print()
                    for name, source, desc in agent_items:
                        badge = "[dim](project)[/dim]" if source == "project" else "[dim](global)[/dim]"
                        console.print(f"    [bold]{name:16s}[/bold] {desc}  {badge}")
                    console.print()
                    console.print("  [dim]The AI will use spawn_agent tool to delegate tasks[/dim]")
                    console.print()
                continue

            if user_input.startswith("/switch"):
                parts = user_input.split(None, 1)
                if len(parts) == 1:
                    # Interactive picker
                    target = await asyncio.to_thread(
                        _interactive_switch, current_context
                    )
                else:
                    target = parts[1].strip()

                if target == current_context:
                    pass  # no change
                elif target == "main":
                    current_context = "main"
                    console.print("  [dim]Switched to [bold]main[/bold] context.[/dim]")
                else:
                    entry = agent_manager.get_by_name(target)
                    if not entry:
                        console.print(f"  [red]No sub-agent '{target}' found.[/red]")
                        console.print("  [dim]Use /switch to see available contexts.[/dim]")
                    else:
                        current_context = target
                        _show_agent_header(entry, target)
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
                console.print("    [bold]/skill-name[/bold]     [dim]Run a skill (/skills to list)[/dim]")
                console.print("    [bold]Esc+Enter[/bold]       [dim]New line[/dim]")
                console.print("    [bold]Enter[/bold]           [dim]Send message[/dim]")
                console.print()
                continue

            # Try to match a skill: /name rest of message
            if user_input.startswith("/"):
                parts = user_input[1:].split(None, 1)
                skill_name = parts[0] if parts else ""
                skill_content = skills.load_skill(skill_name)
                if skill_content:
                    user_msg = parts[1] if len(parts) > 1 else ""
                    expanded = expand_file_refs(user_msg) if user_msg else ""
                    full_msg = skill_content + "\n\n" + expanded if expanded else skill_content
                    console.print(f"  [dim]Using skill: {skill_name}[/dim]")
                    try:
                        await agent.run(full_msg, messages)
                    except KeyboardInterrupt:
                        console.print("\n  [dim]Interrupted.[/dim]")
                    except Exception as e:
                        console.print(f"  [red]Error: {e}[/red]")
                    continue

                console.print(f"  [red]Unknown: {user_input}[/red] [dim]type /help[/dim]")
                continue

            try:
                expanded = expand_file_refs(user_input)
                if current_context == "main":
                    await agent.run(expanded, messages)
                else:
                    entry = agent_manager.get_by_name(current_context)
                    if entry:
                        await agent.run_in_context(
                            entry.system_prompt, expanded,
                            entry.messages, entry.tools_api, entry.tool_lookup,
                        )
                    else:
                        console.print(f"  [red]Agent '{current_context}' not found. Switching to main.[/red]")
                        current_context = "main"
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
