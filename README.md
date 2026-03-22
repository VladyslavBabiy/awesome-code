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
- **Multi-Model** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter

---

## Lesson: Skills & Prompt Engineering

### Why Skills?

Every coding agent — Claude Code, Cursor, Windsurf — has the same challenge: the LLM needs **context** to do its job well. Without instructions, the LLM guesses what you want. With good instructions, it delivers exactly what you need.

But writing good instructions every time is tedious:

```
❯ Review this code. Check for bugs, security issues like SQL injection
  and XSS, performance problems like N+1 queries, and readability.
  For each issue quote the line, explain the problem, and suggest a fix.
  Don't invent problems that don't exist...
```

You end up copying the same paragraph across conversations. Skills solve this by saving instructions as files.

### What are Skills?

A skill is a **markdown file** containing instructions for the LLM. When you type `/skill-name`, awesome-code reads the file and prepends its content to your message.

```
~/.awesome-code/skills/review.md    →  invoke with /review
~/.awesome-code/skills/explain.md   →  invoke with /explain
.awesome-code/skills/deploy.md      →  invoke with /deploy (project-only)
```

The mapping is simple: **filename = command name**.

### How It Works

```
User types: /review @awesome_code/agent.py focus on error handling

┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. PARSE                                                   │
│     skill_name = "review"                                   │
│     user_input = "@awesome_code/agent.py focus on ..."      │
│                                                             │
│  2. LOAD SKILL                                              │
│     Read ~/.awesome-code/skills/review.md                   │
│     ┌─────────────────────────────────────────────────┐     │
│     │ You are performing a code review.                │     │
│     │ Analyze the provided code for:                   │     │
│     │ 1. Bugs: logic errors, null handling             │     │
│     │ 2. Security: injection, XSS, credentials        │     │
│     │ 3. Performance: N+1, unnecessary allocations     │     │
│     │ 4. Readability: naming, complexity, dead code    │     │
│     │                                                  │     │
│     │ For each issue: quote the line, explain, fix.    │     │
│     └─────────────────────────────────────────────────┘     │
│                                                             │
│  3. EXPAND @FILE                                            │
│     Read awesome_code/agent.py → file contents              │
│                                                             │
│  4. COMBINE & SEND                                          │
│     ┌─────────────────────────────────────────────────┐     │
│     │ [skill instructions]                             │     │
│     │                                                  │     │
│     │ focus on error handling                          │     │
│     │                                                  │     │
│     │ <attached_file path="awesome_code/agent.py">     │     │
│     │ import json                                      │     │
│     │ from rich.console import Console                 │     │
│     │ ...                                              │     │
│     │ </attached_file>                                 │     │
│     └─────────────────────────────────────────────────┘     │
│                                        ↓                    │
│  5. LLM receives everything as one message                  │
│     → responds with a structured code review                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Skill Resolution

Skills are discovered from two directories:

```
~/.awesome-code/skills/     ← global (available in any project)
.awesome-code/skills/       ← project-local (overrides global)
```

| Scenario | What happens |
|----------|-------------|
| Only global `review.md` exists | `/review` uses global |
| Only project `review.md` exists | `/review` uses project |
| Both exist | `/review` uses **project** (local overrides global) |
| Neither exists | `/review` → "Unknown command" |

This lets you customize skills per-project. A Python project might have a `/review` that checks for type hints, while a Go project checks for error handling.

### Prompt Engineering: Writing Good Skills

A skill is just text — but **how** you write it determines how useful the LLM's response will be. Here are the principles:

#### 1. Set the Role

Tell the LLM **who** it is for this task:

```markdown
You are a senior security engineer reviewing code for vulnerabilities.
```

vs. the generic "Review this code" — the role focuses the LLM's expertise.

#### 2. Be Specific About What to Check

Don't say "check for issues". List exactly what to look for:

```markdown
Check for:
1. SQL injection via string concatenation in queries
2. XSS through unescaped user input in templates
3. Hardcoded credentials or API keys
4. Path traversal in file operations
5. Missing input validation at API boundaries
```

#### 3. Define the Output Format

Tell the LLM how to structure its response:

```markdown
For each issue found:
- **Location**: file:line
- **Severity**: critical / high / medium / low
- **Problem**: what's wrong and why it matters
- **Fix**: concrete code change

If no issues found, say "No issues found" — don't invent problems.
```

#### 4. Set Boundaries

Prevent the LLM from going off-topic:

```markdown
Only analyze the provided code. Don't:
- Suggest architectural changes
- Add features not asked for
- Rewrite working code for style preferences
```

#### 5. Provide Examples (Few-Shot)

Show the LLM what good output looks like:

```markdown
Example output:

**SQL Injection** (critical)
Location: db/queries.py:42
```python
query = f"SELECT * FROM users WHERE name = '{name}'"
```
Problem: User input is interpolated directly into SQL.
Fix: Use parameterized queries:
```python
query = "SELECT * FROM users WHERE name = %s"
cursor.execute(query, (name,))
```
```

### Example Skills

Here are complete, production-quality skills you can use:

#### `review.md` — Code Review

```markdown
You are performing a thorough code review.

Analyze the provided code for:

1. **Bugs**: Logic errors, off-by-one, null/undefined access, race conditions
2. **Security**: Injection, XSS, credential exposure, path traversal, missing auth
3. **Performance**: N+1 queries, unnecessary allocations, missing caching, blocking I/O
4. **Readability**: Poor naming, excessive complexity, dead code, missing error handling

For each issue:
- Quote the specific line(s)
- Explain why it's a problem
- Provide a concrete fix

If the code is solid, say so briefly. Don't invent issues that don't exist.
Prioritize critical bugs and security issues over style preferences.
```

#### `explain.md` — Code Explanation

```markdown
Explain the provided code clearly.

Structure your explanation:
1. **Summary**: One sentence — what does this code do?
2. **Walk-through**: Step through the logic, explain each section
3. **Key patterns**: Note any design patterns, idioms, or techniques used
4. **Dependencies**: What does this code depend on? What depends on it?
5. **Gotchas**: Any non-obvious behavior, edge cases, or potential pitfalls

Assume the reader is a developer who hasn't seen this codebase before.
Use simple language. Avoid jargon unless you explain it.
```

#### `test.md` — Test Generation

```markdown
Write comprehensive tests for the provided code.

Requirements:
- Detect and use the project's existing test framework (pytest, jest, go test, etc.)
- Cover: happy path, edge cases, error conditions, boundary values
- Use descriptive test names that explain what's being tested
- Mock external dependencies (database, HTTP, file system)
- Each test should be independent — no shared mutable state

Structure:
1. List what you're testing and why
2. Write the tests
3. Note any untestable code and suggest how to make it testable
```

#### `refactor.md` — Code Refactoring

```markdown
Refactor the provided code to improve readability and maintainability.

Rules:
- Keep the same external behavior (inputs/outputs unchanged)
- Extract functions only if they're reused or reduce complexity
- Improve variable/function names to be self-documenting
- Remove dead code and unnecessary comments
- Simplify conditionals and reduce nesting
- Don't over-engineer — three similar lines is better than a premature abstraction

Show the refactored code, then briefly explain what changed and why.
```

### Implementation

**`skills.py`** — two functions:

```python
def discover_skills() -> dict[str, str]:
    """Scan global + project dirs for .md files. Returns {name: path}."""
    skills = {}

    # Global: ~/.awesome-code/skills/*.md
    for path in glob("~/.awesome-code/skills/*.md"):
        skills[stem(path)] = path

    # Project: .awesome-code/skills/*.md (overrides global)
    for path in glob(".awesome-code/skills/*.md"):
        skills[stem(path)] = path

    return skills

def load_skill(name: str) -> str | None:
    """Read skill content. Returns None if not found."""
    path = discover_skills().get(name)
    return read(path) if path else None
```

**Invocation in CLI** — when `/` input doesn't match a built-in command:

```python
# /review @agent.py check error handling
parts = input[1:].split(None, 1)     # ["review", "@agent.py check ..."]
skill = load_skill(parts[0])          # read review.md
if skill:
    msg = skill + "\n\n" + expand_file_refs(parts[1])
    await agent.run(msg, messages)     # send to LLM
```

**Autocomplete** — skills appear in `/` suggestions alongside built-in commands.

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
│   ├── cli.py              # REPL loop and slash commands
│   ├── agent.py            # Agent loop — tool execution and LLM
│   ├── llm.py              # LLM client, streaming, system prompt
│   ├── config.py           # Configuration management
│   ├── setup.py            # Interactive setup wizard
│   ├── skills.py           # Skill discovery and loading
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
│       └── search_codebase.py
├── pyproject.toml
├── install.sh
└── README.md
```

## Tech Stack

- **Python 3.10+**
- [openai](https://pypi.org/project/openai/) — OpenAI-compatible API client (works with OpenRouter)
- [rich](https://pypi.org/project/rich/) — terminal UI and syntax highlighting
- [prompt_toolkit](https://pypi.org/project/prompt_toolkit/) — input handling and autocomplete
- [mcp](https://pypi.org/project/mcp/) — Model Context Protocol SDK
- [httpx](https://pypi.org/project/httpx/) — async HTTP client (for Ollama)
- [numpy](https://pypi.org/project/numpy/) — vector math and cosine similarity

## License

This project was created for educational purposes. Learn from it, break it, remix it.
