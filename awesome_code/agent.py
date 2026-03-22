import json

from rich.console import Console
from rich.panel import Panel

from awesome_code.llm import get_client, stream_response
from awesome_code.tools import TOOLS_BY_NAME

console = Console()


async def run(user_message: str, messages: list[dict]):
    """Run the agent loop: send message, handle tool calls, repeat until done."""
    client = get_client()
    messages.append({"role": "user", "content": user_message})

    while True:
        # Stream LLM response
        console.print()
        assistant_msg = stream_response(
            client, messages, on_text=lambda t: console.print(t, end="")
        )
        console.print()
        messages.append(assistant_msg)

        # If no tool calls, we're done
        tool_calls = assistant_msg.get("tool_calls")
        if not tool_calls:
            break

        # Execute each tool call
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
                # Show tool invocation
                console.print(
                    Panel(
                        f"[bold]{fn_name}[/bold]({', '.join(f'{k}={v!r}' for k, v in fn_args.items())})",
                        title="tool call",
                        border_style="dim",
                    )
                )
                result = await tool.execute_async(**fn_args)

                # Show truncated result
                preview = result[:500] + ("..." if len(result) > 500 else "")
                console.print(f"[dim]{preview}[/dim]")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        # Loop back to get LLM's next response after tool results
