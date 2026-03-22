import os
from openai import OpenAI

from awesome_code import config
from awesome_code.tools import get_tools_for_api

SYSTEM_PROMPT = """You are AwesomeCode, an AI coding assistant running in the user's terminal.
You have access to tools for reading files, writing files, executing shell commands, and semantically searching the codebase.

Current working directory: {cwd}

Guidelines:
- When the user asks about code, architecture, or "where is X" — use search_codebase first to find relevant files by meaning, then read_file to examine them in detail
- Use search_codebase for: finding implementations, understanding patterns, locating code by description, answering "how does X work?" questions
- Use list_dir to understand project structure
- Use read_file to read specific files (not bash cat)
- Use write_file to create or modify files
- Use bash for shell operations (git, npm, pip, tests, etc.)
- Use index_codebase if the user asks to index or if search_codebase returns no index
- If a task requires multiple steps, execute them one by one
- Be concise and direct
{skills_section}"""


def _build_skills_section() -> str:
    from awesome_code.skills import list_skills

    items = list_skills()
    if not items:
        return ""

    lines = [
        "\nAvailable skills (use load_skill tool to load instructions before executing the task):",
    ]
    for name, source, description in items:
        lines.append(f"  - {name}: {description}")
    lines.append(
        "\nWhen the user's request matches a skill, load it with load_skill "
        "and follow its instructions. Apply the skill automatically — "
        "don't ask the user whether to use it."
    )
    return "\n".join(lines)


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

    system_content = SYSTEM_PROMPT.format(
        cwd=os.getcwd(),
        skills_section=_build_skills_section(),
    )

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_content},
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
