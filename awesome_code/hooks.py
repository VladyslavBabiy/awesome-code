"""Hook system for lifecycle events.

Hooks are user-defined shell commands that execute at specific lifecycle
points in awesome-code. They allow validation, blocking, modification,
and custom reactions to agent actions without modifying core code.

Configuration lives in ~/.awesome-code/config.json under the "hooks" key.
Hook commands receive JSON on stdin and communicate decisions via exit codes
(0 = allow, 2 = block) and optional JSON on stdout.
"""

import asyncio
import json
import os
import re
import uuid
import shlex # Added shlex import
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rich.console import Console

from awesome_code import config

console = Console()


# ── Event types ───────────────────────────────────────────────


class HookEvent(str, Enum):
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    PRE_PROMPT_SUBMIT = "PrePromptSubmit"
    POST_RESPONSE = "PostResponse"
    SUBAGENT_SPAWN = "SubagentSpawn"
    SUBAGENT_COMPLETE = "SubagentComplete"


class HookDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    ERROR = "error"


# ── Data classes ──────────────────────────────────────────────


@dataclass
class HookConfig:
    type: str
    command: str
    timeout: int = 10

    @staticmethod
    def from_dict(d: dict) -> "HookConfig":
        return HookConfig(
            type=d.get("type", "command"),
            command=d["command"],
            timeout=d.get("timeout", 10),
        )


@dataclass
class HookGroup:
    matcher: str
    hooks: list[HookConfig]

    @staticmethod
    def from_dict(d: dict) -> "HookGroup":
        return HookGroup(
            matcher=d.get("matcher", ""),
            hooks=[HookConfig.from_dict(h) for h in d.get("hooks", [])],
        )


@dataclass
class HookResult:
    decision: HookDecision
    reason: str = ""
    updated_input: dict | None = None
    additional_context: str = ""


# ── Session state ─────────────────────────────────────────────

_session_id: str = ""


def init_session() -> str:
    global _session_id
    _session_id = uuid.uuid4().hex[:12]
    return _session_id


def get_session_id() -> str:
    return _session_id


# ── Config loading ────────────────────────────────────────────


def load_hook_groups(event: HookEvent) -> list[HookGroup]:
    cfg = config.load()
    hooks_cfg = cfg.get("hooks", {})
    event_hooks = hooks_cfg.get(event.value, [])
    if not isinstance(event_hooks, list):
        return []
    groups = []
    for g in event_hooks:
        try:
            groups.append(HookGroup.from_dict(g))
        except (KeyError, TypeError):
            continue
    return groups


def _matches(matcher: str, value: str) -> bool:
    if not matcher:
        return True
    try:
        return bool(re.search(matcher, value, re.IGNORECASE))
    except re.error:
        return False


# ── Execution ─────────────────────────────────────────────────


def _build_input_payload(
    event: HookEvent, session_id: str, **event_fields: Any
) -> dict:
    return {
        "event": event.value,
        "session_id": session_id,
        "cwd": os.getcwd(),
        **event_fields,
    }


async def _execute_single_hook(
    hook: HookConfig, input_payload: dict
) -> HookResult:
    input_json = json.dumps(input_payload)

    try:
        command_args = shlex.split(hook.command)
        proc = await asyncio.create_subprocess_exec(
            command_args[0],  # The executable
            *command_args[1:], # Its arguments
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, # Capture stderr
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=input_json.encode()),
            timeout=hook.timeout,
        )
        exit_code = proc.returncode

        if exit_code == 0:
            output = stdout.decode().strip()
            if output:
                try:
                    data = json.loads(output)
                    decision_str = data.get("decision", "allow")
                    if decision_str == "block":
                        return HookResult(
                            decision=HookDecision.BLOCK,
                            reason=data.get("reason", ""),
                        )
                    if decision_str == "modify":
                        return HookResult(
                            decision=HookDecision.MODIFY,
                            reason=data.get("reason", ""),
                            updated_input=data.get("updatedInput"),
                            additional_context=data.get("additionalContext", ""),
                        )
                    return HookResult(
                        decision=HookDecision.ALLOW,
                        reason=data.get("reason", ""),
                        additional_context=data.get("additionalContext", ""),
                    )
                except json.JSONDecodeError:
                    pass
            return HookResult(decision=HookDecision.ALLOW)

        elif exit_code == 2:
            output = stdout.decode().strip()
            reason = ""
            if output:
                try:
                    data = json.loads(output)
                    reason = data.get("reason", "")
                except json.JSONDecodeError:
                    reason = output
            return HookResult(decision=HookDecision.BLOCK, reason=reason or "blocked by hook")

        else:
            err_output = stderr.decode().strip() # Use captured stderr
            err_msg = f"Hook exited with code {exit_code}. Output: {err_output or 'No output'}"
            console.print(f"  [yellow]Hook warning: {err_msg}[/yellow]")
            return HookResult(decision=HookDecision.ERROR, reason=err_msg)

    except asyncio.TimeoutError:
        console.print(
            f"  [yellow]Hook timed out after {hook.timeout}s: {hook.command}[/yellow]"
        )
        return HookResult(decision=HookDecision.ERROR, reason="Hook timed out")
    except Exception as e:
        console.print(f"  [yellow]Hook error: {e}[/yellow]")
        return HookResult(decision=HookDecision.ERROR, reason=str(e))


async def run_hooks(
    event: HookEvent,
    match_value: str = "",
    session_id: str = "",
    **event_fields: Any,
) -> HookResult:
    """Run all matching hooks for an event sequentially.

    If any hook returns BLOCK, execution stops immediately.
    MODIFY results are chained through subsequent hooks.
    """
    groups = load_hook_groups(event)
    if not groups:
        return HookResult(decision=HookDecision.ALLOW)

    payload = _build_input_payload(event, session_id, **event_fields)
    context_parts: list[str] = []
    modified = False

    for group in groups:
        if not _matches(group.matcher, match_value):
            continue

        for hook in group.hooks:
            result = await _execute_single_hook(hook, payload)

            if result.decision == HookDecision.BLOCK:
                return result

            if result.decision == HookDecision.MODIFY and result.updated_input:
                payload.update(result.updated_input)
                modified = True

            if result.additional_context:
                context_parts.append(result.additional_context)

    final = HookResult(decision=HookDecision.ALLOW)
    if context_parts:
        final.additional_context = "\n".join(context_parts)
    if modified:
        final.decision = HookDecision.MODIFY
        final.updated_input = {
            k: v for k, v in payload.items()
            if k not in ("event", "session_id", "cwd")
        }

    return final


# ── Convenience functions ─────────────────────────────────────


async def on_pre_tool_use(tool_name: str, tool_input: dict) -> HookResult:
    return await run_hooks(
        HookEvent.PRE_TOOL_USE,
        match_value=tool_name,
        session_id=_session_id,
        tool_name=tool_name,
        tool_input=tool_input,
    )


async def on_post_tool_use(
    tool_name: str, tool_input: dict, tool_output: str
) -> HookResult:
    return await run_hooks(
        HookEvent.POST_TOOL_USE,
        match_value=tool_name,
        session_id=_session_id,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
    )


async def on_session_start() -> HookResult:
    return await run_hooks(
        HookEvent.SESSION_START, session_id=_session_id
    )


async def on_session_end() -> HookResult:
    return await run_hooks(
        HookEvent.SESSION_END, session_id=_session_id
    )


async def on_pre_prompt_submit(prompt: str) -> HookResult:
    return await run_hooks(
        HookEvent.PRE_PROMPT_SUBMIT,
        match_value=prompt,
        session_id=_session_id,
        prompt=prompt,
    )


async def on_post_response(response_text: str) -> HookResult:
    return await run_hooks(
        HookEvent.POST_RESPONSE,
        match_value=response_text,
        session_id=_session_id,
        response_text=response_text[:2000],
    )


async def on_subagent_spawn(agent_name: str, task: str) -> HookResult:
    return await run_hooks(
        HookEvent.SUBAGENT_SPAWN,
        match_value=agent_name,
        session_id=_session_id,
        agent_name=agent_name,
        task=task,
    )


async def on_subagent_complete(
    agent_name: str, task: str, status: str, result: str = ""
) -> HookResult:
    return await run_hooks(
        HookEvent.SUBAGENT_COMPLETE,
        match_value=agent_name,
        session_id=_session_id,
        agent_name=agent_name,
        task=task,
        status=status,
        result=result[:2000],
    )


# ── Display helper ────────────────────────────────────────────


def list_configured_hooks() -> list[tuple[str, str, list[str]]]:
    """Returns [(event_name, matcher, [commands])] for /hooks display."""
    cfg = config.load()
    hooks_cfg = cfg.get("hooks", {})
    result = []
    for event_name, groups in hooks_cfg.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            matcher = group.get("matcher", "*") or "*"
            commands = [h.get("command", "?") for h in group.get("hooks", [])]
            result.append((event_name, matcher, commands))
    return result


def validate_hooks_config(hooks_cfg: dict) -> list[str]:
    """Validate hooks configuration. Returns list of warnings."""
    warnings = []
    valid_events = {e.value for e in HookEvent}

    for event_name, groups in hooks_cfg.items():
        if event_name not in valid_events:
            warnings.append(f"Unknown hook event: '{event_name}'")
            continue
        if not isinstance(groups, list):
            warnings.append(f"hooks.{event_name} must be an array")
            continue
        for i, group in enumerate(groups):
            if not isinstance(group, dict):
                warnings.append(f"hooks.{event_name}[{i}] must be an object")
                continue
            hooks_list = group.get("hooks")
            if not isinstance(hooks_list, list):
                warnings.append(f"hooks.{event_name}[{i}].hooks must be an array")
                continue
            for j, hook in enumerate(hooks_list):
                if "command" not in hook:
                    warnings.append(
                        f"hooks.{event_name}[{i}].hooks[{j}] missing 'command'"
                    )

    return warnings