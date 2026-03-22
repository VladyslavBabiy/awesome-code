from awesome_code.tools.base import BaseTool


class SpawnAgentTool(BaseTool):
    name = "spawn_agent"
    description = (
        "Spawn a sub-agent to work on a task asynchronously with a clean context. "
        "The sub-agent uses a specialized system prompt from its AGENT.md definition "
        "and has access to all tools (read_file, write_file, bash, etc.). "
        "The agent runs in background — the user sees live progress and a notification "
        "when done. The user can use /switch to view results. Do NOT poll or wait."
    )
    parameters = {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Name of the agent definition to use (from agents/ directory)",
            },
            "task": {
                "type": "string",
                "description": "Detailed description of the task for the sub-agent to complete",
            },
        },
        "required": ["agent_name", "task"],
    }

    async def execute_async(self, **kwargs) -> str:
        from awesome_code.agents import load_agent, list_agents
        from awesome_code import agent_manager

        agent_name = kwargs["agent_name"]
        task = kwargs["task"]

        agent_md = load_agent(agent_name)
        if agent_md is None:
            available = [name for name, _, _ in list_agents()]
            return (
                f"Agent '{agent_name}' not found. "
                f"Available agents: {', '.join(available) if available else 'none'}"
            )

        try:
            task_id = agent_manager.spawn(agent_name, task, agent_md)
        except RuntimeError as e:
            return f"Error: {e}"

        return (
            f"Sub-agent '{agent_name}' spawned successfully (task_id: {task_id}).\n"
            f"The agent is working in the background. The user sees live progress.\n"
            f"The user can use /switch {agent_name} to view results when done."
        )

    def execute(self, **kwargs) -> str:
        return "Error: spawn_agent must be called asynchronously."
