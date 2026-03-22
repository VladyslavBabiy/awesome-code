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
- **Hooks** — user-defined shell commands that react to agent lifecycle events (block, validate, log)
- **Memory Bank** — persistent project context that survives across sessions (`/init`)
- **Multi-Model** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter

---

## Hooks

Hooks are user-defined shell commands that execute at specific points in the agent lifecycle. They let you validate, block, modify, or react to agent actions without changing the source code.

### How It Works

```
User submits message
        │
        ▼
  PrePromptSubmit hook ──── block? → message discarded
        │ allow/modify
        ▼
  Agent calls LLM
        │
        ▼
  PostResponse hook
        │
        ▼
  Agent calls tool
        │
  PreToolUse hook ──── block? → tool skipped
        │ allow/modify
        ▼
  Tool executes
        │
        ▼
  PostToolUse hook ──── modify? → result changed
```

### Events

| Event | When it fires | Can block? |
|-------|---------------|-----------|
| `SessionStart` | REPL starts | Yes |
| `SessionEnd` | REPL exits | No |
| `PreToolUse` | Before tool execution | Yes |
| `PostToolUse` | After tool execution | No (can modify result) |
| `PrePromptSubmit` | Before prompt is sent to LLM | Yes |
| `PostResponse` | After LLM responds | No |
| `SubagentSpawn` | When a sub-agent is spawned | Yes |
| `SubagentComplete` | When a sub-agent finishes | No |

### Configuration

Hooks are configured in `~/.awesome-code/config.json` under the `hooks` key:

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "regex_pattern",
        "hooks": [
          {
            "type": "command",
            "command": "shell_command_here",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- **matcher** — regex pattern to filter events (empty `""` = match all). For `PreToolUse`/`PostToolUse` it matches the tool name, for `SubagentSpawn` — agent name, for `PrePromptSubmit` — prompt text
- **type** — currently only `"command"` (shell command)
- **timeout** — timeout in seconds (default 10)

### Protocol

Hook receives JSON on **stdin**:

```json
{
  "event": "PreToolUse",
  "session_id": "a1b2c3d4e5f6",
  "cwd": "/path/to/project",
  "tool_name": "bash",
  "tool_input": { "command": "rm -rf /" }
}
```

Hook responds via **stdout** (JSON) and **exit code**:

| Exit code | Behavior |
|-----------|----------|
| `0` | Success — parses stdout JSON for decision |
| `2` | Block — operation is prevented |
| Other | Non-blocking error — warning logged, execution continues |

Stdout JSON format:

```json
{
  "decision": "allow|block|modify",
  "reason": "human-readable reason",
  "updatedInput": { "tool_input": { "command": "safe_command" } },
  "additionalContext": "context injected for the agent"
}
```

Hook **stderr** is passed directly to the terminal — use it for logging.

### Examples

#### 1. Log all tool calls to terminal

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"[HOOK] $(cat | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d['tool_name'], d.get('tool_input',{}).get('command','')[:50])\")\" >&2"
          }
        ]
      }
    ]
  }
}
```

#### 2. Block dangerous bash commands

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "bash",
        "hooks": [
          {
            "type": "command",
            "command": "CMD=$(cat | python3 -c \"import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))\"); if echo \"$CMD\" | grep -qE '(rm -rf /|mkfs|dd if=|:(){ :|:)'; then echo '{\"decision\": \"block\", \"reason\": \"Dangerous command blocked\"}'; fi"
          }
        ]
      }
    ]
  }
}
```

#### 3. Session start/end notifications

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'awesome-code session started' >&2"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'awesome-code session ended' >&2"
          }
        ]
      }
    ]
  }
}
```

#### 4. Auto-format after file write

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "write_file",
        "hooks": [
          {
            "type": "command",
            "command": "FILE=$(cat | python3 -c \"import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('path',''))\"); if echo \"$FILE\" | grep -qE '\\.py$'; then python3 -m black \"$FILE\" 2>&1 >&2; fi"
          }
        ]
      }
    ]
  }
}
```

#### 5. Block specific sub-agent from spawning

```json
{
  "hooks": {
    "SubagentSpawn": [
      {
        "matcher": "test",
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"decision\": \"block\", \"reason\": \"Test agent is disabled\"}'"
          }
        ]
      }
    ]
  }
}
```

#### 6. Auto-append context to every prompt

```json
{
  "hooks": {
    "PrePromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"decision\": \"modify\", \"updatedInput\": {\"prompt\": \"'\"$(cat | python3 -c \"import sys,json; print(json.load(sys.stdin)['prompt'])\" )\"'\\n\\nAlways write tests for new code.\"}}'"
          }
        ]
      }
    ]
  }
}
```

### /hooks Command

Use `/hooks` in the REPL to see all configured hooks:

```
❯ /hooks

  Hooks

    PreToolUse          bash             ./block-dangerous.sh
    PostToolUse         write_file       ./auto-format.py
    SessionStart        *                echo 'started' >&2
```

### Architecture

```
┌──────────────┐          ┌──────────────┐
│   cli.py     │─────────▶│   hooks.py   │
│   agent.py   │  events  │              │
│   agent_mgr  │◀─────────│  run_hooks() │
└──────────────┘ decision  └──────┬───────┘
                                  │ shell exec
                                  ▼
                           ┌──────────────┐
                           │  user script │
                           │  (stdin JSON)│
                           │  (stdout JSON│
                           │   + exit code│
                           └──────────────┘
```

| File | Role |
|------|------|
| `hooks.py` | Hook engine: config loading, matching, execution, protocol |
| `agent.py` | Integration: PreToolUse/PostToolUse/PostResponse via `_execute_tool_with_hooks()` |
| `cli.py` | Integration: SessionStart/End, PrePromptSubmit, `/hooks` command |
| `agent_manager.py` | Integration: SubagentSpawn/SubagentComplete |

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
| `/hooks` | Show configured hooks |
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
  "mcpServers": {},
  "hooks": {}
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
│   ├── hooks.py            # Hook system — lifecycle event handlers
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
