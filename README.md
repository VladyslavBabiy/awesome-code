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
- **Multi-Model** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter

---

## Lesson Sub-Agents

### The Problem

A single LLM agent tries to do everything in one conversation: review code, write tests, check security, optimize performance. This creates two problems:

1. **Context pollution** — the conversation fills up with intermediate tool results (file contents, command output). By the time the agent gets to the third task, it has 50 messages of context from the first two, and its quality drops.

2. **Sequential execution** — the agent works on one thing at a time. If you ask it to review 3 files, it reviews them one after another. You wait for all three.

This is exactly how humans work too — if you ask one person to do five different jobs, they context-switch, get tired, and the quality of the last job suffers. The solution? **Delegate to specialists.**

### What are Sub-Agents?

A sub-agent is a **separate LLM instance** that:

- Has its own **clean conversation context** (empty message history)
- Uses a **specialized system prompt** from a markdown file
- Has access to all the same **tools** (read_file, write_file, bash, etc.)
- Runs **asynchronously** — the main agent and user don't wait for it
- **Cannot spawn other sub-agents** (no recursion)

Think of it like this:

```
Main Agent (general purpose)
  ├── spawns → code-reviewer   (clean context, review prompt)
  ├── spawns → test-automator  (clean context, testing prompt)
  └── spawns → security-engineer (clean context, security prompt)

Each sub-agent works independently, in parallel.
The user sees live progress and switches between them with /switch.
```

### Why Clean Context Matters

When the main agent has been working for a while, its context looks like this:

```
messages = [
  user: "explain the project structure"
  assistant: (text + tool calls)
  tool: (list_dir results — 200 lines)
  tool: (read_file results — 300 lines)
  assistant: (explanation)
  user: "now review agent.py"        ← by this point, 500+ lines of context
  assistant: (text + tool calls)
  tool: (read_file — 150 lines)
  ...
]
```

The review quality degrades because the LLM is processing all that irrelevant context from the previous task.

A sub-agent starts fresh:

```
messages = [
  user: "Review agent.py for bugs, security, performance..."
]
```

It gets the full system prompt with review instructions, reads the file it needs, and focuses entirely on the review. No noise.

### How It Works

#### 1. Define Agents

Agents are markdown files in the `agents/` directory. The filename is the agent name:

```
~/.awesome-code/agents/          ← global (available in any project)
    code-reviewer.md
    test-automator.md
    security-engineer.md
.awesome-code/agents/            ← project-local (overrides global)
    deploy-checker.md
```

An agent file is a system prompt — it tells the LLM who it is and how to behave:

```markdown
# Code Reviewer

You are a senior code reviewer. Analyze the provided code for:

1. **Bugs**: logic errors, null handling, race conditions
2. **Security**: injection, XSS, credential exposure
3. **Performance**: N+1 queries, unnecessary allocations
4. **Readability**: naming, complexity, dead code

For each issue: quote the line, explain the problem, provide a fix.
If the code is solid, say so. Don't invent issues.
```

#### 2. Spawning

The main agent has a `spawn_agent` tool. When the user asks to review code, the main agent calls:

```
spawn_agent(agent_name="code-reviewer", task="Review agent.py for ...")
```

What happens internally:

```
┌─────────────────────────────────────────────────────────────────┐
│  spawn_agent("code-reviewer", "Review agent.py ...")            │
│                                                                 │
│  1. LOAD AGENT                                                  │
│     Read ~/.awesome-code/agents/code-reviewer.md                │
│     → system prompt for the sub-agent                           │
│                                                                 │
│  2. BUILD TOOL SET                                              │
│     All tools EXCEPT spawn_agent (no recursion)                 │
│     [read_file, write_file, bash, list_dir, ...]               │
│                                                                 │
│  3. CREATE CLEAN CONTEXT                                        │
│     messages = []  ← empty, fresh start                         │
│     system_prompt = agent.md content + cwd + guidelines         │
│                                                                 │
│  4. LAUNCH ASYNC TASK                                           │
│     asyncio.create_task(run_background(...))                    │
│     → sub-agent runs concurrently with the main agent           │
│                                                                 │
│  5. RETURN IMMEDIATELY                                          │
│     Main agent tells user: "spawned, use /switch to see results"│
└─────────────────────────────────────────────────────────────────┘
```

#### 3. Async Execution

The sub-agent runs as an `asyncio.Task` on the same event loop. The key that makes this work: **async streaming**.

```python
# llm.py uses AsyncOpenAI — yields control between chunks
stream = await client.chat.completions.create(stream=True, ...)
async for chunk in stream:   # ← yields to event loop between chunks
    ...
```

With sync `OpenAI`, `for chunk in stream:` blocks the entire event loop. Nothing else can run. With `AsyncOpenAI`, the `async for` yields control between chunks, allowing the main agent and all sub-agents to interleave execution.

While the sub-agent works, the user sees live output with a prefix:

```
  [code-reviewer] → read_file  path='awesome_code/agent.py'
  [code-reviewer]   import json from rich.console import Console...
  [code-reviewer] ✓ done
```

#### 4. Switching Context

The `/switch` command opens an interactive picker:

```
  Switch context

  → main       primary agent
    code-reviewer  ✓ completed  Review agent.py for bugs...
    test-automator ⟳ running    Write tests for agent.py...

  ↑↓ navigate  enter select  esc cancel
```

When you switch to a completed agent, you see:

```
  ─── code-reviewer ✓ ────────────────────────────────────
  Task: Review agent.py for bugs, security, performance

  [full review result rendered as markdown]

[code-reviewer] ❯ _
```

You can now send follow-up messages to the sub-agent — it remembers its conversation context:

```
[code-reviewer] ❯ can you also check the error handling in run_background?
```

Type `/switch main` or `/switch` → select main to go back.

### Architecture

```
┌────────────────────────────────────────────────┐
│                   cli.py                        │
│  REPL loop · /switch · status bar · context    │
│                                                 │
│  current_context = "main" | "code-reviewer"     │
│                                                 │
│  if main → agent.run(msg, messages)             │
│  if sub  → agent.run_in_context(               │
│              system_prompt, msg,                │
│              entry.messages, entry.tools)       │
└────────────┬───────────────────────┬────────────┘
             │                       │
     ┌───────▼───────┐      ┌───────▼────────┐
     │   agent.py     │      │ agent_manager   │
     │                │      │                 │
     │ run()          │      │ spawn()         │
     │ run_background │      │ get_by_name()   │
     │ run_in_context │      │ format_status() │
     └───────┬────────┘      └────────┬────────┘
             │                        │
     ┌───────▼────────────────────────▼──────────┐
     │              llm.py                        │
     │  AsyncOpenAI · async streaming             │
     │  system prompt with agents section         │
     └───────────────────────────────────────────┘
```

**Key modules:**

| File | Purpose |
|------|---------|
| `agents.py` | Discovery — scan `~/.awesome-code/agents/` and `.awesome-code/agents/` for `.md` files |
| `agent_manager.py` | Lifecycle — spawn async tasks, track status, deduplicate by name |
| `agent.py: run_background()` | Execute sub-agent loop silently with prefixed live output |
| `agent.py: run_in_context()` | Interactive mode — same as `run()` but with custom system prompt |
| `tools/spawn_agent.py` | Tool exposed to the LLM — calls `agent_manager.spawn()` |

### Skills vs Agents

Both are markdown files with instructions for the LLM. The difference is **context**:

| | Skills | Agents |
|---|--------|--------|
| **Context** | Shares the main conversation | Gets a clean, empty context |
| **Execution** | Synchronous — main agent runs it inline | Asynchronous — runs in background |
| **System prompt** | Added to the user message | Replaces the system prompt |
| **Interaction** | One-shot, part of main flow | Persistent, switchable via `/switch` |
| **Use case** | Quick task with current context | Independent task needing focus |

**When to use skills:** "Review this file I'm already looking at" — the skill needs the current context.

**When to use agents:** "Run a full security audit on the project" — the agent needs to independently explore and shouldn't pollute the main conversation.

### Implementation Details

#### Agent Discovery (`agents.py`)

Follows the same pattern as skills — scan two directories, project overrides global:

```python
def discover_agents() -> dict[str, str]:
    """Returns {name: file_path}. Project agents override global."""
    agents = {}
    agents.update(_scan("~/.awesome-code/agents/"))  # global
    agents.update(_scan(".awesome-code/agents/"))     # project (overrides)
    return agents
```

#### Concurrency Control (`agent_manager.py`)

Maximum 3 concurrent sub-agents. Each spawned agent creates an `asyncio.Task` with a done-callback:

```python
MAX_CONCURRENT = 3

def spawn(agent_name, task, agent_md) -> task_id:
    # 1. Check limit
    # 2. Build system prompt from agent.md
    # 3. Build tool set (all tools minus spawn_agent)
    # 4. Create asyncio.Task → run_background(...)
    # 5. Register done-callback → update status + print notification
    # 6. Return task_id
```

Sub-agents cannot spawn other sub-agents — `spawn_agent` is filtered out of their tool set.

#### Status Bar

Before each prompt, the CLI shows a compact status bar:

```
  agents: ⟳ code-reviewer  ✓ test-automator  ✗ security-engineer
```

Deduplicated by name — if the same agent is spawned twice, only the latest instance is shown.

### Writing Good Agent Prompts

Agent prompts follow the same principles as skill prompts, with one addition: **the agent needs to be self-sufficient**. It can't ask the user for clarification. It needs to know:

1. **What to do** — clear objective
2. **How to find what it needs** — which tools to use, what to look for
3. **What format to report in** — structured output the user can act on
4. **When to stop** — boundaries to prevent infinite exploration

Example of a well-structured agent:

```markdown
# Security Engineer

You are a security engineer performing a security audit.

## Process
1. Use list_dir to understand the project structure
2. Use read_file to examine entry points (API routes, CLI handlers)
3. Search for common vulnerability patterns:
   - SQL/NoSQL injection
   - XSS (unescaped user input in templates)
   - Path traversal (user input in file operations)
   - Hardcoded secrets (API keys, passwords in code)
   - Missing authentication/authorization checks
   - Insecure deserialization

## Output Format
For each finding:
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW
- **File**: path:line
- **Issue**: what's wrong
- **Impact**: what an attacker could do
- **Fix**: concrete code change

End with a summary: total findings by severity, overall risk assessment.
If the codebase is clean, say so — don't invent issues.
```

---

## Previous Lessons

### Lesson 4: Skills & Prompt Engineering

Skills are reusable prompt templates — markdown files that get prepended to your message when you type `/skill-name`. See the [skills section](#what-are-skills) for details.

### Lesson 3: Semantic Code Search (RAG)

Index your codebase with Ollama embeddings and search by meaning, not just keywords.

### Lesson 2: MCP (Model Context Protocol)

Connect external tools via MCP servers — extend the agent with any capability.

### Lesson 1: Agent Loop

The core: stream LLM responses, execute tool calls, repeat until done.

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
