# AwesomeCode

> Terminal-based AI coding assistant built for educational purposes.

A CLI tool that lets you pair-program with LLMs right from your terminal — ask questions, explore codebases, edit files, and run commands through a conversational interface. Built with extensibility in mind: MCP protocol support, semantic code search via local embeddings, and file attachments.

## Features

- **Interactive REPL** — conversational interface with `/` commands and `@file` attachments
- **AI-Powered Agent** — streams LLM responses with an iterative tool-use loop
- **Built-in Tools** — read/write files, execute shell commands, list directory trees
- **Semantic Code Search** — index your codebase with Ollama embeddings, search by meaning
- **MCP Support** — connect external MCP servers for additional tools
- **Multi-Model** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter

---

## Lesson: RAG (Retrieval-Augmented Generation)

### The Problem

LLMs have a fixed context window. You can't paste an entire codebase (thousands of files, millions of lines) into a single prompt. Even if you could, the model would struggle to find the relevant parts.

So how do coding agents like Cursor, Windsurf, or Claude Code know where to look in your code?

The answer is **RAG** — Retrieval-Augmented Generation.

### What is RAG?

RAG is a pattern that combines **retrieval** (finding relevant information) with **generation** (LLM producing a response). Instead of feeding the entire codebase to the model, you:

1. **Index** the codebase once (pre-process)
2. **Retrieve** only the relevant pieces when the user asks a question
3. **Generate** a response using those pieces as context

```
Without RAG:
  User question + ENTIRE CODEBASE → LLM → answer
  ❌ Too much data, too expensive, too slow

With RAG:
  User question → RETRIEVAL → top 5-10 relevant snippets → LLM → answer
  ✅ Focused context, fast, cheap
```

### How RAG Works in Coding Agents

```
┌─────────────────────────────────────────────────┐
│              INDEXING (one-time)                 │
│                                                  │
│  Source Code                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ file1.py │  │ file2.js │  │ file3.go │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │              │              │            │
│       ▼              ▼              ▼            │
│  ┌──────────────────────────────────────┐       │
│  │         Chunking                     │       │
│  │  Split files into semantic blocks    │       │
│  │  (functions, classes, fixed-size)    │       │
│  └─────────────────┬────────────────────┘       │
│                    │                             │
│                    ▼                             │
│  ┌──────────────────────────────────────┐       │
│  │      Embedding Model (Ollama)        │       │
│  │  text → vector [0.12, -0.34, ...]    │       │
│  └─────────────────┬────────────────────┘       │
│                    │                             │
│                    ▼                             │
│  ┌──────────────────────────────────────┐       │
│  │      Vector Store (on disk)          │       │
│  │  chunks.json + vectors.npy           │       │
│  └──────────────────────────────────────┘       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│              RETRIEVAL (per query)               │
│                                                  │
│  "how does auth work?"                           │
│       │                                          │
│       ▼                                          │
│  Embed query → [0.11, -0.31, ...]                │
│       │                                          │
│       ▼                                          │
│  Cosine similarity vs ALL stored vectors         │
│       │                                          │
│       ▼                                          │
│  Top-K most similar chunks →                     │
│    auth/login.py:10-45  (score: 0.85)            │
│    middleware/session.py:1-30  (score: 0.79)      │
│    models/user.py:5-22  (score: 0.72)            │
│       │                                          │
│       ▼                                          │
│  LLM receives: question + these 3 snippets       │
│       │                                          │
│       ▼                                          │
│  Answer with full context about auth              │
└─────────────────────────────────────────────────┘
```

### What are Embeddings?

Embeddings are numerical representations of text as vectors (arrays of numbers). The key property: **texts with similar meaning produce similar vectors**.

```
"user authentication login"  → [0.12, -0.34, 0.56, 0.78, ...]
"sign-in flow with JWT"      → [0.11, -0.31, 0.58, 0.75, ...]  ← close!

"CSS border radius"          → [-0.82, 0.44, -0.12, 0.03, ...]  ← far away
```

This is what enables searching code **by meaning** rather than by exact text match. The query "how does user authentication work?" will find code related to login, sessions, tokens — even if none of those files contain the word "authentication".

### What are Chunks?

You can't embed an entire file as one vector — it would lose too much detail. Instead, files are split into **chunks**: smaller, meaningful pieces of code.

**Smart chunking** detects code boundaries:

```python
# This file gets split into 3 chunks:

# ── Chunk 1: class definition ──────────
class UserService:
    def __init__(self, db):
        self.db = db

# ── Chunk 2: login method ──────────────
    def login(self, email, password):
        user = self.db.find_by_email(email)
        if user and verify_password(password, user.hash):
            return create_session(user)
        raise AuthError("Invalid credentials")

# ── Chunk 3: registration ─────────────
    def register(self, email, password):
        if self.db.find_by_email(email):
            raise AuthError("Email already exists")
        user = User(email=email, hash=hash_password(password))
        self.db.save(user)
        return user
```

Each chunk gets its own embedding vector. When you search for "login flow", chunk 2 will score highest because its vector is closest to the query vector.

**Chunking strategies:**

| Strategy | How it works | Best for |
|----------|-------------|----------|
| **Boundary-based** | Split at `def`, `class`, `function` | Code with clear structure |
| **Fixed-size** | N lines with overlap | Config files, prose, unstructured |
| **Tree-sitter** | Parse AST, extract nodes | Production-grade, language-aware |

AwesomeCode uses boundary-based chunking with fixed-size fallback.

### Cosine Similarity

The math behind "how similar are two vectors":

```
                    A · B
cos(θ) = ─────────────────────
          ‖A‖ × ‖B‖

Where:
  A · B  = dot product (sum of element-wise multiplication)
  ‖A‖    = magnitude (sqrt of sum of squares)
```

| Score | Meaning |
|-------|---------|
| **1.0** | Identical meaning |
| **0.7+** | Very relevant |
| **0.5** | Somewhat related |
| **0.0** | Unrelated |

In NumPy:

```python
scores = matrix @ query / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(query))
```

One line. Compares the query against ALL chunks simultaneously.

### Incremental Indexing

Re-indexing the entire project every time is wasteful. Instead, we track file hashes:

```
First run:
  file_hashes = {}  →  index ALL files

Second run (nothing changed):
  stored: {auth.py: "abc123", db.py: "def456"}
  current: {auth.py: "abc123", db.py: "def456"}  ← same!
  → "Index is up to date" (instant)

After editing auth.py:
  stored: {auth.py: "abc123", db.py: "def456"}
  current: {auth.py: "xyz789", db.py: "def456"}  ← changed!
  → remove old auth.py chunks, re-chunk, re-embed, save
```

SHA-256 hash per file. Only changed files get re-processed.

### Why Ollama?

Ollama runs embedding models **locally**:
- **Free** — no API keys or costs
- **Private** — code never leaves your machine
- **Fast** — no network latency
- **Model**: `nomic-embed-text` produces 768-dimensional vectors

### RAG vs. Full Context

| Approach | Pros | Cons |
|----------|------|------|
| **Full context** | Simple, no indexing | Limited by context window, expensive |
| **RAG** | Scales to any codebase, cheap | Requires indexing, may miss context |
| **Hybrid** | Best of both | More complex |

Production coding agents use a hybrid: RAG to find relevant files, then read them fully into context.

---

## RAG Implementation in AwesomeCode

### Architecture

```
awesome_code/indexing/
├── scanner.py    # Walk directory, filter files, compute SHA-256
├── chunker.py    # Split files into semantic blocks (regex boundaries)
├── embedder.py   # Async Ollama API client (POST /api/embed)
└── store.py      # Vector store: chunks.json + vectors.npy + meta.json

awesome_code/tools/
├── index_codebase.py   # Tool for LLM to trigger indexing
└── search_codebase.py  # Tool for LLM to search by meaning
```

### Storage

Index is stored per-project in `~/.awesome-code/index/{project-hash}/`:

```
~/.awesome-code/index/
└── a1b2c3d4e5f6g7h8/        ← SHA-256(project path)[:16]
    ├── chunks.json            ← chunk metadata (file, lines, content)
    ├── vectors.npy            ← numpy array (N × 768 floats)
    └── meta.json              ← file hashes for incremental indexing
```

- `vectors.npy` — binary NumPy format, ~5x smaller than JSON, loads instantly
- `chunks.json` — inspectable metadata, stores first 500 chars per chunk
- `meta.json` — `{rel_path: sha256}` map for change detection

### How the LLM Uses It

The system prompt instructs the LLM to use `search_codebase` automatically when the user asks about code:

```
User: "where is the database connection code?"
  │
  ├─ LLM calls: search_codebase(query="database connection")
  │  → returns top-10 relevant code snippets with file paths
  │
  ├─ LLM calls: read_file(path="db/connection.py")
  │  → reads the full file for detailed understanding
  │
  └─ LLM responds with a complete answer
```

No manual search required — the agent finds code by meaning.

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
| `/clear` | Clear conversation history |
| `/quit` | Exit |

### @file Attachment

Attach files to your message with `@path`:

```
❯ explain @awesome_code/agent.py
❯ compare @agent.py and @llm.py
❯ refactor the error handling in @tools/bash.py
```

### Input

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Esc → Enter` | New line (multiline input) |
| `@` + type | File autocomplete |
| `/` + type | Command autocomplete |

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
  "mcpServers": {
    "server_name": {
      "command": "npx",
      "args": ["-y", "@vendor/mcp-package"],
      "env": {}
    }
  }
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `api_key` | — | OpenRouter API key (required) |
| `model` | `anthropic/claude-sonnet-4` | LLM model |
| `base_url` | `https://openrouter.ai/api/v1` | API endpoint |
| `ollama_url` | `http://localhost:11434` | Ollama server URL |
| `embed_model` | `nomic-embed-text` | Embedding model for indexing |
| `auto_index` | `false` | Auto-index on startup |
| `mcpServers` | `{}` | MCP server configurations |

## Project Structure

```
awesome-code/
├── awesome_code/
│   ├── cli.py              # REPL loop and slash commands
│   ├── agent.py            # Agent loop — tool execution and LLM
│   ├── llm.py              # LLM client, streaming, system prompt
│   ├── config.py           # Configuration management
│   ├── setup.py            # Interactive setup wizard
│   ├── indexing/
│   │   ├── __init__.py     # Orchestrator — index_project(), search_project()
│   │   ├── scanner.py      # File discovery and SHA-256 hashing
│   │   ├── chunker.py      # Split files into semantic blocks
│   │   ├── embedder.py     # Async Ollama API client
│   │   └── store.py        # Vector store with cosine similarity
│   ├── mcp/
│   │   ├── __init__.py     # Exports McpManager
│   │   ├── manager.py      # MCP server management
│   │   └── tool.py         # McpTool — server tool wrapper
│   └── tools/
│       ├── __init__.py     # Tool registry
│       ├── base.py         # BaseTool — abstract class
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
- [httpx](https://pypi.org/project/httpx/) — async HTTP client (for Ollama API)
- [numpy](https://pypi.org/project/numpy/) — vector math and cosine similarity

## License

This project was created for educational purposes. Learn from it, break it, remix it — that's the whole point.
