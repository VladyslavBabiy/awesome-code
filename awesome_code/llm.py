import os
from openai import OpenAI

from awesome_code import config
from awesome_code.tools import get_tools_for_api

SYSTEM_PROMPT = """You are AwesomeCode, a chill coding assistant running in the user's terminal.
You have access to tools for reading files, writing files, and executing shell commands.

Current working directory: {cwd}

Guidelines:
- Use tools to explore and modify the codebase
- Be concise and direct
- When reading code, use the read_file tool rather than bash cat
- When writing code, use the write_file tool
- For shell operations (git, npm, pip, etc.), use the bash tool
- If a task requires multiple steps, execute them one by one
"""


def get_client() -> OpenAI:
    cfg = config.load()
    api_key = os.environ.get("OPENROUTER_API_KEY") or cfg.get("api_key")
    if not api_key:
        raise SystemExit(
            "Error: No API key configured.\n"
            "Run `awesome-code --setup` or set OPENROUTER_API_KEY env var."
        )
    base_url = cfg.get("base_url", "https://openrouter.ai/api/v1")
    return OpenAI(base_url=base_url, api_key=api_key)


def get_model() -> str:
    cfg = config.load()
    return os.environ.get("AWESOME_CODE_MODEL") or cfg.get("model", "anthropic/claude-sonnet-4")


def stream_response(client: OpenAI, messages: list[dict], on_text=None):
    """Call LLM with streaming. Returns the complete assistant message (with tool_calls if any)."""
    model = get_model()
    tools = get_tools_for_api()

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(cwd=os.getcwd())},
            *messages,
        ],
        tools=tools,
        stream=True,
        max_tokens=16384,
    )

    text_content = ""
    tool_calls_map: dict[int, dict] = {}

    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if not delta:
            continue

        if delta.content:
            text_content += delta.content
            if on_text:
                on_text(delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_map:
                    tool_calls_map[idx] = {
                        "id": tc.id or "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                if tc.id:
                    tool_calls_map[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tool_calls_map[idx]["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

    msg: dict = {"role": "assistant"}
    if text_content:
        msg["content"] = text_content
    tool_calls = [tool_calls_map[i] for i in sorted(tool_calls_map)]
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg
