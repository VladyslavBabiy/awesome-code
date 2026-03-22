import os

from awesome_code import config

AGENTS_DIR_NAME = "agents"


def _global_agents_dir() -> str:
    return os.path.join(config.CONFIG_DIR, AGENTS_DIR_NAME)


def _project_agents_dir() -> str:
    return os.path.join(os.getcwd(), ".awesome-code", AGENTS_DIR_NAME)


def _scan_agents_dir(base_dir: str) -> dict[str, str]:
    """Scan a directory for agent .md files. Filename (without .md) = agent name."""
    agents: dict[str, str] = {}
    if not os.path.isdir(base_dir):
        return agents

    for entry in os.listdir(base_dir):
        if entry.endswith(".md"):
            name = entry[:-3]  # strip .md
            agents[name] = os.path.join(base_dir, entry)

    return agents


def discover_agents() -> dict[str, str]:
    """Find all agents. Returns {name: file_path}.

    Project agents override global agents with the same name.
    """
    agents: dict[str, str] = {}
    agents.update(_scan_agents_dir(_global_agents_dir()))
    agents.update(_scan_agents_dir(_project_agents_dir()))
    return agents


def load_agent(name: str) -> str | None:
    """Load agent content by name. Returns .md file content."""
    agents = discover_agents()
    agent_file = agents.get(name)
    if not agent_file:
        return None

    try:
        with open(agent_file, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def list_agents() -> list[tuple[str, str, str]]:
    """Returns [(name, source, first_line)] for display."""
    agents = discover_agents()
    result = []

    global_dir = _global_agents_dir()

    for name, file_path in sorted(agents.items()):
        source = "project" if not file_path.startswith(global_dir) else "global"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                in_frontmatter = False
                first_line = ""
                for line in f:
                    stripped = line.strip()
                    if stripped == "---":
                        in_frontmatter = not in_frontmatter
                        continue
                    if in_frontmatter or not stripped:
                        continue
                    if stripped.startswith("#"):
                        first_line = stripped.lstrip("# ").strip()
                    else:
                        first_line = stripped
                    break
                if not first_line:
                    first_line = name
        except OSError:
            first_line = "(unreadable)"

        result.append((name, source, first_line))

    return result
