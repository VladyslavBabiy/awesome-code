# awesome-code

> Terminal-based AI coding assistant built for educational purposes.

A CLI tool that lets you pair-program with LLMs right from your terminal — ask questions, explore codebases, edit files, and run commands through a conversational interface.

## Features

- **Interactive REPL** — conversational interface with `/` commands and `@file` attachments
- **AI-Powered Agent** — streams LLM responses with an iterative tool-use loop
- **Built-in Tools** — read/write files, execute shell commands, list directory trees
- **Semantic Code Search** — index your codebase with Ollama embeddings, search by meaning
- **MCP Support** — connect external MCP servers for additional tools
- **Skills** — reusable prompt templates loaded from markdown files
- **Sub-Agents** — spawn specialized agents that work asynchronously with clean context
- **Memory Bank** — persistent project context that survives across sessions (`/init`)
- **Multi-Model** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter

---

## Memory Bank

### The Problem

Every time you start a new session with the agent, it knows nothing about your project. It has to re-discover the tech stack, project structure, and conventions from scratch — either by you explaining it, or by the agent spending tool calls to explore.

This is wasteful. The project doesn't change that much between sessions. If the agent could **remember** what it learned, it would be useful from the very first message.

### What is Memory Bank?

Memory Bank is a persistent project description stored in `.awesome-code/memory.md`. When you run `/init`, the agent analyzes your project — reads config files, scans the directory tree, checks git history — and writes a structured summary. This summary is automatically injected into the system prompt on every subsequent session.

```
Session 1:  /init → agent analyzes project → writes .awesome-code/memory.md
Session 2:  agent starts with project context already loaded
Session 3:  agent starts with project context already loaded
...
Project changes significantly?  /init again → memory updated
```

### How It Works

#### 1. Initialize

Run `/init` in your project directory. The agent will:

1. `list_dir` — scan the project structure
2. `read_file` — read config files (pyproject.toml, package.json, pom.xml, etc.)
3. `bash` — check `git remote -v` and `git log --oneline -5`
4. `write_file` — write the analysis to `.awesome-code/memory.md`

#### 2. Memory File Format

The generated file follows a fixed structure:

```markdown
# Project: awesome-code

## Overview
Terminal-based AI coding assistant built for educational purposes.

## Tech Stack
- Python 3.10+, AsyncOpenAI, Rich, prompt_toolkit, MCP SDK, NumPy

## Architecture
- Entry point: cli.py (REPL loop)
- Agent loop: agent.py (run, run_background, run_in_context)
- LLM client: llm.py (AsyncOpenAI with streaming)
...

## Key Files
- cli.py — REPL loop, commands, input handling
- agent.py — agent execution loop with tool calls
...

## Conventions
- No Lombok, no unnecessary abstractions
- Tools follow BaseTool abstract class pattern
...
```

#### 3. Automatic Loading

On every session, `llm.py` checks for `.awesome-code/memory.md`. If found, its content is appended to the system prompt under "Project Memory Bank". The agent sees this context before any user message.

#### 4. Re-initialization

Run `/init` again to re-analyze. The agent overwrites the existing memory file with fresh analysis. Useful after major refactors or dependency changes.

### Architecture

```
┌──────────────┐     /init      ┌──────────────────┐
│   cli.py     │ ──────────────▶│   agent.run()    │
│   REPL loop  │                │   with INIT_PROMPT│
└──────────────┘                └────────┬─────────┘
                                         │ uses tools
                                         ▼
                                ┌──────────────────┐
                                │ list_dir, read,  │
                                │ bash, write_file │
                                └────────┬─────────┘
                                         │ writes
                                         ▼
                                .awesome-code/memory.md

Next session:
┌──────────────┐  builds prompt  ┌──────────────────┐
│   llm.py     │ ◀──────────────│   memory.py      │
│   system     │   load_memory() │   load/check     │
│   prompt     │                 └──────────────────┘
└──────────────┘
```

**Key modules:**

| File | Purpose |
|------|---------|
| `memory.py` | Load memory bank, check if initialized |
| `llm.py` | Inject memory into system prompt via `_build_memory_section()` |
| `cli.py` | `/init` command handler, welcome screen status |

### Why This Design?

- **Agent does the analysis** — the LLM understands code better than any hardcoded heuristic. It reads what matters and summarizes intelligently.
- **No new tools needed** — reuses existing `list_dir`, `read_file`, `bash`, `write_file`.
- **Simple persistence** — a single markdown file, human-readable, version-controllable.
- **Lazy loading** — memory is only read when building the system prompt, not at startup.

---

## Installation

**Requirements:** Python 3.10+, [Ollama](https://ollama.com) (for code indexing)

```bash
git clone <repo-url>
cd awesome-code
./install.sh
```

For code indexing:
```bash
ollama pull nomic-embed-text
```

## Usage

```bash
awesome-code          # Start the assistant
awesome-code --setup  # Configure API key and model
```

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/init` | Initialize memory bank (persistent project context) |
| `/model` | Change the AI model |
| `/mcp` | Show connected MCP servers |
| `/index` | Index codebase for semantic search |
| `/skills` | List available skills |
| `/agents` | List available sub-agents |
| `/switch` | Switch context between main and sub-agents |
| `/skill-name` | Run a skill (e.g. `/review @file.py`) |
| `/clear` | Clear conversation history |
| `/quit` | Exit |

### @file Attachment

Attach files to your message with `@path`:

```
❯ explain @awesome_code/agent.py
❯ compare @agent.py and @llm.py
❯ /review @tools/bash.py
```

### Input

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Esc → Enter` | New line |
| `@` + type | File autocomplete |
| `/` + type | Command / skill autocomplete |

## Configuration

`~/.awesome-code/config.json`:

```json
{
  "api_key": "sk-...",
  "model": "anthropic/claude-sonnet-4",
  "base_url": "https://openrouter.ai/api/v1",
  "ollama_url": "http://localhost:11434",
  "embed_model": "nomic-embed-text",
  "auto_index": false,
  "mcpServers": {}
}
```

## Project Structure

```
awesome-code/
├── awesome_code/
│   ├── cli.py              # REPL loop, /switch, status bar
│   ├── agent.py            # Agent loop — run, run_background, run_in_context
│   ├── llm.py              # AsyncOpenAI client, async streaming
│   ├── config.py           # Configuration management
│   ├── memory.py           # Memory bank — persistent project context
│   ├── setup.py            # Interactive setup wizard
│   ├── skills.py           # Skill discovery and loading
│   ├── agents.py           # Agent discovery and loading
│   ├── agent_manager.py    # Sub-agent lifecycle and status tracking
│   ├── indexing/
│   │   ├── __init__.py     # Orchestrator
│   │   ├── scanner.py      # File discovery and SHA-256
│   │   ├── chunker.py      # Semantic code splitting
│   │   ├── embedder.py     # Ollama API client
│   │   └── store.py        # Vector store (cosine similarity)
│   ├── mcp/
│   │   ├── manager.py      # MCP server management
│   │   └── tool.py         # MCP tool wrapper
│   └── tools/
│       ├── base.py         # BaseTool abstract class
│       ├── read_file.py
│       ├── write_file.py
│       ├── bash.py
│       ├── list_dir.py
│       ├── index_codebase.py
│       ├── search_codebase.py
│       ├── load_skill.py
│       └── spawn_agent.py
├── pyproject.toml
├── install.sh
└── README.md
```

## Tech Stack

- **Python 3.10+**
- [openai](https://pypi.org/project/openai/) — AsyncOpenAI client (works with OpenRouter)
- [rich](https://pypi.org/project/rich/) — terminal UI and syntax highlighting
- [prompt_toolkit](https://pypi.org/project/prompt_toolkit/) — input handling, autocomplete, interactive picker
- [mcp](https://pypi.org/project/mcp/) — Model Context Protocol SDK
- [httpx](https://pypi.org/project/httpx/) — async HTTP client (for Ollama)
- [numpy](https://pypi.org/project/numpy/) — vector math and cosine similarity

## License

This project was created for educational purposes. Learn from it, break it, remix it.
