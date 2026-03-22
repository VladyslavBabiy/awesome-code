import asyncio
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console

_console = Console()


class AgentStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


STATUS_ICONS = {
    AgentStatus.RUNNING: ("[bright_yellow]", "⟳"),
    AgentStatus.COMPLETED: ("[green]", "✓"),
    AgentStatus.FAILED: ("[red]", "✗"),
}


@dataclass
class SubAgentTask:
    id: str
    name: str
    task: str
    status: AgentStatus
    asyncio_task: asyncio.Task
    system_prompt: str = ""
    tools_api: list = field(default_factory=list)
    tool_lookup: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    result: str = ""
    error: str = ""


MAX_CONCURRENT = 3

_tasks: dict[str, SubAgentTask] = {}


def _build_system_prompt(agent_md: str) -> str:
    cwd = os.getcwd()
    return (
        f"{agent_md}\n\n"
        f"Current working directory: {cwd}\n\n"
        "You have access to tools for reading files, writing files, "
        "executing shell commands, and searching the codebase.\n"
        "Be concise and direct. Complete the task and report results."
    )


def spawn(agent_name: str, task: str, agent_md: str) -> str:
    """Spawn a sub-agent as an async task. Returns task_id."""
    running = sum(1 for t in _tasks.values() if t.status == AgentStatus.RUNNING)
    if running >= MAX_CONCURRENT:
        raise RuntimeError(
            f"Max concurrent sub-agents ({MAX_CONCURRENT}) reached. "
            "Wait for a running agent to finish."
        )

    task_id = uuid.uuid4().hex[:8]
    system_prompt = _build_system_prompt(agent_md)

    # Build tool set without spawn_agent (no recursion)
    from awesome_code.tools import ALL_TOOLS

    subagent_tools = [t for t in ALL_TOOLS if t.name != "spawn_agent"]
    tools_api = [t.to_openai_tool() for t in subagent_tools]
    tool_lookup = {t.name: t for t in subagent_tools}

    # Shared messages list — populated by run_background, reusable for /switch
    messages: list[dict] = []

    entry = SubAgentTask(
        id=task_id,
        name=agent_name,
        task=task,
        status=AgentStatus.RUNNING,
        asyncio_task=None,  # set below
        system_prompt=system_prompt,
        tools_api=tools_api,
        tool_lookup=tool_lookup,
        messages=messages,
    )

    async def _run():
        from awesome_code.agent import run_background
        return await run_background(
            system_prompt, task, tools_api, tool_lookup,
            agent_label=agent_name, messages=messages,
        )

    asyncio_task = asyncio.create_task(_run())
    entry.asyncio_task = asyncio_task
    _tasks[task_id] = entry

    def _on_done(fut: asyncio.Task):
        prefix = f"  [magenta]\\[{agent_name}][/magenta]"
        try:
            entry.result = fut.result()
            entry.status = AgentStatus.COMPLETED
            _console.print(f"{prefix} [green]✓ done[/green]")
        except Exception as e:
            entry.error = str(e)
            entry.status = AgentStatus.FAILED
            _console.print(f"{prefix} [red]✗ failed: {e}[/red]")

    asyncio_task.add_done_callback(_on_done)

    return task_id


def check(task_id: str) -> SubAgentTask | None:
    """Check status of a sub-agent task."""
    return _tasks.get(task_id)


def get_by_name(name: str) -> SubAgentTask | None:
    """Get the most recent sub-agent task by agent name."""
    for entry in reversed(list(_tasks.values())):
        if entry.name == name:
            return entry
    return None


def list_all() -> list[SubAgentTask]:
    """Return all tracked sub-agent tasks."""
    return list(_tasks.values())


def format_status_bar() -> str | None:
    """Format a compact status bar. Shows latest instance per agent name."""
    tasks = list_all()
    if not tasks:
        return None

    # Deduplicate: keep only latest per agent name
    latest: dict[str, SubAgentTask] = {}
    for t in tasks:
        latest[t.name] = t

    parts = []
    for t in latest.values():
        style, icon = STATUS_ICONS[t.status]
        parts.append(f"{style}{icon} {t.name}[/]")

    return "  agents: " + "  ".join(parts)
