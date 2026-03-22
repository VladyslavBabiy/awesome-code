from awesome_code.tools.base import BaseTool


class LoadSkillTool(BaseTool):
    name = "load_skill"
    description = (
        "Load a skill (prompt template) by name and apply it to the current task. "
        "Use this when the user's request matches an available skill. "
        "Call list_skills first to see what's available."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name to load (e.g. 'review', 'explain', 'test')",
            },
        },
        "required": ["name"],
    }

    def execute(self, **kwargs) -> str:
        from awesome_code.skills import load_skill

        name = kwargs["name"]
        content = load_skill(name)
        if content is None:
            return f"Skill '{name}' not found. Use list_skills to see available skills."
        return content
