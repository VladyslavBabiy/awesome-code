from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from awesome_code import config

console = Console()

POPULAR_MODELS = [
    "anthropic/claude-sonnet-4",
    "anthropic/claude-haiku-4",
    "openai/gpt-4.1",
    "openai/gpt-4.1-mini",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
    "deepseek/deepseek-r1",
    "meta-llama/llama-4-maverick",
]


def run_setup():
    console.print()
    console.print(
        Panel(
            "[bold cyan]Welcome to AwesomeCode![/]\n\n"
            "Let's set up your configuration.\n"
            "You'll need an OpenRouter API key from [link=https://openrouter.ai/keys]openrouter.ai/keys[/link]",
            border_style="cyan",
        )
    )

    # API Key
    cfg = config.load()
    existing_key = cfg.get("api_key", "")
    if existing_key:
        masked = existing_key[:8] + "..." + existing_key[-4:]
        console.print(f"\n[dim]Current API key: {masked}[/dim]")

    api_key = Prompt.ask(
        "\n[bold]OpenRouter API key[/]",
        default=existing_key or None,
        password=True,
    )
    if not api_key:
        console.print("[red]API key is required.[/red]")
        return False

    # Model selection
    console.print("\n[bold]Select a model:[/bold]\n")
    for i, model in enumerate(POPULAR_MODELS, 1):
        marker = " [cyan]<- current[/]" if model == cfg.get("model") else ""
        console.print(f"  [dim]{i}.[/dim] {model}{marker}")
    console.print(f"  [dim]{len(POPULAR_MODELS) + 1}.[/dim] Custom model ID")

    choice = Prompt.ask(
        "\n[bold]Choice[/]",
        default="1",
    )

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(POPULAR_MODELS):
            model = POPULAR_MODELS[idx]
        elif idx == len(POPULAR_MODELS):
            model = Prompt.ask("[bold]Enter model ID[/]")
        else:
            model = POPULAR_MODELS[0]
    except ValueError:
        # Treat as custom model ID
        model = choice

    cfg["api_key"] = api_key
    cfg["model"] = model
    config.save(cfg)

    console.print(
        f"\n[green]Config saved![/green] Model: [bold]{model}[/bold]\n"
        f"[dim]Config file: {config.CONFIG_FILE}[/dim]\n"
    )
    return True
