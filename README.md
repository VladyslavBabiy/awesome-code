# awesome-code

> Terminal-based AI coding assistant built for educational purposes.

A CLI tool that lets you pair-program with LLMs right from your terminal — ask questions, explore codebases, edit files, and run commands through a conversational interface.

## Features

- **Interactive REPL** — conversational interface with slash-command autocomplete
- **AI-Powered Agent** — streams LLM responses in real-time with an iterative tool-use loop
- **Built-in Tools** — read/write files, execute shell commands, list directory trees
- **Multi-Model Support** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter API
- **Setup Wizard** — guided first-run configuration for API key and model selection

## How It Works

awesome-code follows an **agent pattern**:

1. You type a message in the terminal
2. The LLM processes it with access to tools (file I/O, shell, directory listing)
3. The agent executes any requested tool calls and feeds results back to the LLM
4. The loop continues until the LLM completes its response
5. You type the next message

## Installation

**Requirements:** Python 3.10+

```bash
git clone <repo-url>
cd awesome-code
./install.sh
```

## Usage

```bash
awesome-code          # Start the assistant
awesome-code --setup  # Re-run the setup wizard
```

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model` | Switch the active LLM model |
| `/clear` | Clear conversation history |
| `/quit` | Exit |

### Built-in Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with optional line offset and limit |
| `write_file` | Create or overwrite files (auto-creates directories) |
| `bash` | Execute shell commands (30s timeout) |
| `list_dir` | Display directory tree |

## Configuration

`~/.awesome-code/config.json`:

```json
{
  "api_key": "sk-...",
  "model": "anthropic/claude-sonnet-4",
  "base_url": "https://openrouter.ai/api/v1"
}
```

## Project Structure

```
awesome-code/
├── awesome_code/
│   ├── cli.py          # Main REPL loop and slash commands
│   ├── agent.py        # Agent loop — tool execution and LLM interaction
│   ├── llm.py          # LLM client, streaming, system prompt
│   ├── config.py       # Config management (~/.awesome-code/config.json)
│   ├── setup.py        # Interactive setup wizard
│   └── tools/
│       ├── base.py     # BaseTool abstract class
│       ├── read_file.py
│       ├── write_file.py
│       ├── bash.py
│       └── list_dir.py
├── pyproject.toml
├── install.sh
└── README.md
```

## Tech Stack

- **Python 3.10+**
- [openai](https://pypi.org/project/openai/) — OpenAI-compatible API client (works with OpenRouter)
- [rich](https://pypi.org/project/rich/) — terminal UI, panels, and syntax highlighting
- [prompt_toolkit](https://pypi.org/project/prompt_toolkit/) — input handling and autocomplete

## License

This project was created for educational purposes. Learn from it, break it, remix it — that's the whole point.
