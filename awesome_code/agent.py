import json

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

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
}

TOOL_COLORS = {
    "bash": "bright_yellow",
    "read_file": "green",
    "write_file": "yellow",
    "list_dir": "blue",
    "search_codebase": "cyan",
    "index_codebase": "cyan",
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

        assistant_msg = stream_response(client, messages, on_text=on_text)
        console.print()
        messages.append(assistant_msg)

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

            tool = TOOLS_BY_NAME.get(fn_name)
            if not tool:
                result = f"Error: Unknown tool '{fn_name}'"
            else:
                console.print(_format_tool_call(fn_name, fn_args))
                result = await tool.execute_async(**fn_args)
                console.print(_format_tool_result(result))

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        console.print()
