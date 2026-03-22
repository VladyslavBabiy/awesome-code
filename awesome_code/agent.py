import json

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from awesome_code import hooks
from awesome_code.hooks import HookDecision
from awesome_code.llm import get_client, stream_response
from awesome_code.tools import TOOLS_BY_NAME

console = Console()

# Tool icons and colors (OpenCode-inspired)
TOOL_ICONS = {
    "bash": "$",
    "read_file": "→",
    "write_file": "←",
    "list_dir": "⊞",
    "search_codebase": "⇄",
    "index_codebase": "⊕",
    "spawn_agent": "⊳",
}

TOOL_COLORS = {
    "bash": "bright_yellow",
    "read_file": "green",
    "write_file": "yellow",
    "list_dir": "blue",
    "search_codebase": "cyan",
    "index_codebase": "cyan",
    "spawn_agent": "magenta",
}


def _format_tool_call(fn_name: str, fn_args: dict) -> str:
    icon = TOOL_ICONS.get(fn_name, "⚡")
    color = TOOL_COLORS.get(fn_name, "dim")
    args_str = ", ".join(f"{k}={v!r}" for k, v in fn_args.items())
    if len(args_str) > 100:
        args_str = args_str[:97] + "..."
    return f"  [{color}]{icon} {fn_name}[/{color}]  [dim]{args_str}[/dim]"


def _format_tool_result(result: str) -> str:
    preview = result[:200].replace("\n", " ")
    if len(result) > 200:
        preview += "..."
    return f"    [dim]{preview}[/dim]"


async def _execute_tool_with_hooks(
    fn_name: str,
    fn_args: dict,
    tool_lookup: dict,
    show_output: bool = True,
    prefix: str = "",
) -> str:
    """Execute a single tool call with pre/post hooks."""
    # Pre-tool hook
    pre = await hooks.on_pre_tool_use(fn_name, fn_args)
    if pre.decision == HookDecision.BLOCK:
        reason = pre.reason or "blocked by hook"
        if show_output:
            console.print(f"{prefix}  [yellow]⊘ {fn_name} blocked: {reason}[/yellow]")
        return f"Tool '{fn_name}' blocked by hook: {reason}"

    if pre.decision == HookDecision.MODIFY and pre.updated_input:
        fn_args = pre.updated_input.get("tool_input", fn_args)

    tool = tool_lookup.get(fn_name)
    if not tool:
        return f"Error: Unknown tool '{fn_name}'"

    if show_output:
        console.print(f"{prefix}{_format_tool_call(fn_name, fn_args)}")

    result = await tool.execute_async(**fn_args)

    if show_output:
        console.print(f"{prefix}{_format_tool_result(result)}")

    # Post-tool hook
    post = await hooks.on_post_tool_use(fn_name, fn_args, result)
    if post.decision == HookDecision.MODIFY and post.updated_input:
        result = post.updated_input.get("tool_output", result)
    if post.additional_context:
        result += f"\n[Hook context: {post.additional_context}]"

    return result


async def run(user_message: str, messages: list[dict]):
    """Run the agent loop: send message, handle tool calls, repeat until done."""
    client = get_client()
    messages.append({"role": "user", "content": user_message})

    while True:
        console.print()

        # Collect streamed text
        text_parts: list[str] = []

        def on_text(t: str):
            text_parts.append(t)
            console.print(t, end="")

        assistant_msg = await stream_response(client, messages, on_text=on_text)
        console.print()
        messages.append(assistant_msg)

        if assistant_msg.get("content"):
            await hooks.on_post_response(assistant_msg["content"])

        tool_calls = assistant_msg.get("tool_calls")
        if not tool_calls:
            break

        # Execute each tool call
        console.print()
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            result = await _execute_tool_with_hooks(
                fn_name, fn_args, TOOLS_BY_NAME
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        console.print()


async def run_background(
    system_prompt: str,
    task: str,
    tools_api: list[dict],
    tool_lookup: dict,
    agent_label: str = "",
    messages: list[dict] | None = None,
) -> str:
    """Run agent loop in background with live prefixed output. Returns collected text."""
    client = get_client()
    if messages is None:
        messages = []
    messages.append({"role": "user", "content": task})
    collected_text: list[str] = []

    prefix = f"  [magenta]\\[{agent_label}][/magenta]" if agent_label else ""

    while True:
        assistant_msg = await stream_response(
            client, messages, system_prompt=system_prompt, tools_override=tools_api
        )
        messages.append(assistant_msg)

        if assistant_msg.get("content"):
            collected_text.append(assistant_msg["content"])

        tool_calls = assistant_msg.get("tool_calls")
        if not tool_calls:
            break

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            result = await _execute_tool_with_hooks(
                fn_name, fn_args, tool_lookup,
                show_output=bool(agent_label),
                prefix=f"{prefix} " if agent_label else "",
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    return "\n".join(collected_text)


async def run_in_context(
    system_prompt: str,
    user_message: str,
    messages: list[dict],
    tools_api: list[dict],
    tool_lookup: dict,
):
    """Run agent loop in a sub-agent context with console output (interactive mode)."""
    client = get_client()
    messages.append({"role": "user", "content": user_message})

    while True:
        console.print()

        text_parts: list[str] = []

        def on_text(t: str):
            text_parts.append(t)
            console.print(t, end="")

        assistant_msg = await stream_response(
            client, messages, on_text=on_text,
            system_prompt=system_prompt, tools_override=tools_api,
        )
        console.print()
        messages.append(assistant_msg)

        tool_calls = assistant_msg.get("tool_calls")
        if not tool_calls:
            break

        console.print()
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            result = await _execute_tool_with_hooks(
                fn_name, fn_args, tool_lookup
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        console.print()
