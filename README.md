# awesome-code

> Terminal-based AI coding assistant built for educational purposes.

A CLI tool that lets you pair-program with LLMs right from your terminal — ask questions, explore codebases, edit files, and run commands through a conversational interface. Extensible via MCP (Model Context Protocol).

## Features

- **Interactive REPL** — conversational interface with slash-command autocomplete
- **AI-Powered Agent** — streams LLM responses in real-time with an iterative tool-use loop
- **Built-in Tools** — read/write files, execute shell commands, list directory trees
- **MCP Support** — connect external MCP servers for additional tools
- **Multi-Model Support** — works with Claude, GPT-4, Gemini, DeepSeek, Llama and more via OpenRouter API

---

## Lesson: MCP (Model Context Protocol)

### What is MCP?

**MCP (Model Context Protocol)** is an open standard that defines how AI applications (clients) communicate with external services (servers) to extend the model's capabilities.

Think of an LLM as a brain, and MCP servers as hands, eyes, and ears. The brain is smart on its own, but without hands it can't press a button, without eyes it can't see a database, without ears it can't hear a Slack message. MCP provides a standard way to connect these "senses" to any AI application.

**Key idea**: instead of every AI app writing its own integration with every service, MCP creates a universal protocol. One MCP server works with any MCP client — just like USB works with any computer.

### MCP Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Application (Host)                 │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ MCP      │    │ MCP      │    │ MCP      │          │
│  │ Client 1 │    │ Client 2 │    │ Client 3 │          │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘          │
│       │               │               │                 │
└───────┼───────────────┼───────────────┼─────────────────┘
        │ stdio         │ stdio         │ stdio
        ▼               ▼               ▼
  ┌───────────┐   ┌───────────┐   ┌───────────┐
  │ MCP       │   │ MCP       │   │ MCP       │
  │ Server A  │   │ Server B  │   │ Server C  │
  │ (e.g.     │   │ (e.g.     │   │ (e.g.     │
  │ filesystem│   │ GitHub)   │   │ database) │
  └───────────┘   └───────────┘   └───────────┘
```

MCP has three roles:

| Role | Description | In awesome-code |
|------|-------------|-----------------|
| **Host** | The app that runs clients and contains the LLM | `cli.py` — REPL loop |
| **Client** | Maintains a 1:1 connection with a server | `McpManager` — connection manager |
| **Server** | External process that provides tools | Any MCP server (e.g. `@upstash/context7-mcp`) |

### What does an MCP server provide?

An MCP server can expose three types of primitives:

| Primitive | Description | Example |
|-----------|-------------|---------|
| **Tools** | Functions that the LLM can invoke | `search_docs`, `query_database` |
| **Resources** | Data that the client can read | Files, DB records, API responses |
| **Prompts** | Message templates for the LLM | Ready-made prompts for specific tasks |

awesome-code implements support for **Tools** — the most common primitive.

### Transport: how do client and server communicate?

MCP uses the **JSON-RPC 2.0** protocol over a transport layer. The most common transport is **stdio** (standard input/output):

```
Client                             Server
   │                                  │
   │──── stdin (JSON-RPC) ───────────▶│   Client launches the server as a
   │                                  │   child process and writes to its stdin
   │◀─── stdout (JSON-RPC) ──────────│   Server responds via stdout
   │                                  │
```

---

## MCP Implementation in awesome-code

### Step 1: Server Configuration

MCP servers are configured in `~/.awesome-code/config.json`:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {}
    }
  }
}
```

### Step 2: Base Tool Class (`tools/base.py`)

All tools — both built-in and MCP — inherit from `BaseTool`:

```python
class BaseTool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema

    def to_openai_tool(self) -> dict:
        """Converts to OpenAI function calling format."""
        ...

    @abstractmethod
    def execute(self, **kwargs) -> str: ...

    async def execute_async(self, **kwargs) -> str:
        return self.execute(**kwargs)
```

### Step 3: MCP Tool Wrapper (`mcp/tool.py`)

```python
class McpTool(BaseTool):
    def __init__(self, server_name, tool_name, description, input_schema, session):
        self.name = f"{server_name}__{tool_name}"   # namespace
        self._session = session

    async def execute_async(self, **kwargs) -> str:
        result = await self._session.call_tool(self._original_name, kwargs)
        # extract text blocks from response
```

### Step 4: MCP Manager (`mcp/manager.py`)

Orchestrates server connections:

```
1. StdioServerParameters     2. stdio_client(params)
   ┌──────────────────┐         ┌──────────────────┐
   │ command: "npx"   │ ──────▶ │ Spawns process   │
   │ args: ["-y",...] │         │ Creates streams   │
   └──────────────────┘         └────────┬─────────┘
                                         │
                                         ▼
3. ClientSession(read, write)   4. session.list_tools()
   ┌──────────────────┐         ┌──────────────────┐
   │ JSON-RPC client  │ ──────▶ │ Discovers tools  │
   │ initialize()     │         │ Creates McpTool  │
   └──────────────────┘         └──────────────────┘
```

### Step 5: Tool Registration

```python
def register_tools(tools):
    for t in tools:
        ALL_TOOLS.append(t)
        TOOLS_BY_NAME[t.name] = t
```

After registration, MCP tools are indistinguishable from built-in tools.

### Full MCP Call Flow

```
User: "Find docs on React hooks"
  → LLM sees tools: [read_file, bash, context7__search_docs, ...]
  → LLM calls: context7__search_docs(query="React hooks")
  → McpTool.execute_async() → JSON-RPC → MCP server → response
  → Result returned to LLM → LLM responds to user
```

---

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
awesome-code --setup  # Configure API key and model
```

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model` | Change the AI model |
| `/mcp` | Show connected MCP servers |
| `/clear` | Clear conversation history |
| `/quit` | Exit |

## Configuration

`~/.awesome-code/config.json`:

```json
{
  "api_key": "sk-...",
  "model": "anthropic/claude-sonnet-4",
  "base_url": "https://openrouter.ai/api/v1",
  "mcpServers": {
    "server_name": {
      "command": "npx",
      "args": ["-y", "@vendor/mcp-package"],
      "env": {}
    }
  }
}
```

## Project Structure

```
awesome-code/
├── awesome_code/
│   ├── cli.py          # REPL loop and slash commands
│   ├── agent.py        # Agent loop — tool execution and LLM
│   ├── llm.py          # LLM client, streaming, system prompt
│   ├── config.py       # Configuration management
│   ├── setup.py        # Interactive setup wizard
│   ├── mcp/
│   │   ├── manager.py  # MCP server management
│   │   └── tool.py     # McpTool wrapper
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
- [rich](https://pypi.org/project/rich/) — terminal UI and syntax highlighting
- [prompt_toolkit](https://pypi.org/project/prompt_toolkit/) — input handling and autocomplete
- [mcp](https://pypi.org/project/mcp/) — Model Context Protocol SDK

## License

This project was created for educational purposes. Learn from it, break it, remix it.
