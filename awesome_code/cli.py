import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from awesome_code import agent, config
from awesome_code.setup import run_setup

console = Console()

COMMANDS = {
    "/help": "Show available commands",
    "/quit": "Exit AwesomeCode",
    "/clear": "Clear conversation history",
    "/model": "Change the AI model",
    "/setup": "Reconfigure API key & model",
}


class SlashCompleter(Completer):
    """Shows command suggestions as soon as / is typed."""

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for cmd, desc in COMMANDS.items():
            if cmd.startswith(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display_meta=desc,
                )


def get_input() -> str | None:
    try:
        return pt_prompt(
            "> ",
            completer=SlashCompleter(),
            complete_while_typing=True,
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None


def print_welcome():
    from awesome_code.llm import get_model

    model = get_model()
    cwd = os.getcwd()

    info = Text()
    info.append(">_ ", style="bold cyan")
    info.append("awesome-code", style="bold white")
    info.append(" (v0.1.0)\n\n", style="dim")
    info.append("model:     ", style="dim")
    info.append(f"{model}", style="bold")
    info.append("   /model to change\n", style="dim")
    info.append("directory: ", style="dim")
    info.append(f"{cwd}", style="bold")

    console.print()
    console.print(Panel(info, border_style="bright_blue", padding=(1, 2)))
    console.print(
        Panel(
            "Type [bold]/[/bold] to see commands  |  "
            "[dim]/quit[/dim] to exit",
            border_style="dim",
            padding=(0, 2),
        )
    )
    console.print()


def main():
    if "--setup" in sys.argv:
        run_setup()
        return

    if not config.is_configured():
        console.print("[yellow]First run — let's set up awesome-code.[/yellow]")
        if not run_setup():
            return

    print_welcome()

    messages: list[dict] = []

    while True:
        user_input = get_input()
        if user_input is None:
            console.print("\nBye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            console.print("Bye!")
            break

        if user_input == "/clear":
            messages.clear()
            console.print("[dim]History cleared.[/dim]")
            continue

        if user_input == "/setup":
            run_setup()
            continue

        if user_input == "/model":
            from awesome_code.setup import POPULAR_MODELS
            from rich.prompt import Prompt

            cfg = config.load()
            console.print(f"\n[dim]Current model: {cfg.get('model')}[/dim]\n")
            for i, m in enumerate(POPULAR_MODELS, 1):
                console.print(f"  [dim]{i}.[/dim] {m}")
            console.print(f"  [dim]{len(POPULAR_MODELS) + 1}.[/dim] Custom model ID")
            choice = Prompt.ask("\n[bold]Choice[/]", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(POPULAR_MODELS):
                    model = POPULAR_MODELS[idx]
                elif idx == len(POPULAR_MODELS):
                    model = Prompt.ask("[bold]Enter model ID[/]")
                else:
                    model = cfg["model"]
            except ValueError:
                model = choice
            cfg["model"] = model
            config.save(cfg)
            console.print(f"[green]Model set to: {model}[/green]\n")
            continue

        if user_input == "/help":
            rows = "\n".join(
                f"[bold]{cmd:18s}[/bold] {desc}" for cmd, desc in COMMANDS.items()
            )
            console.print(Panel(rows, title="Commands", border_style="cyan"))
            continue

        if user_input.startswith("/"):
            console.print(f"[red]Unknown command: {user_input}[/red] (type /help)")
            continue

        try:
            agent.run(user_input, messages)
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
