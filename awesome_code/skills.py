import os
import glob

from awesome_code import config

SKILLS_DIR_NAME = "skills"
SKILL_FILE = "SKILL.md"
REFERENCES_DIR = "references"


def _global_skills_dir() -> str:
    return os.path.join(config.CONFIG_DIR, SKILLS_DIR_NAME)


def _project_skills_dir() -> str:
    return os.path.join(os.getcwd(), ".awesome-code", SKILLS_DIR_NAME)


def _scan_skills_dir(base_dir: str) -> dict[str, str]:
    """Scan a directory for skill folders containing SKILL.md.

    Structure:
        skills/
        ├── review/
        │   └── SKILL.md
        ├── java-architect/
        │   ├── SKILL.md
        │   └── references/
        │       ├── setup.md
        │       └── testing.md
    """
    skills: dict[str, str] = {}
    if not os.path.isdir(base_dir):
        return skills

    for entry in os.listdir(base_dir):
        skill_dir = os.path.join(base_dir, entry)
        skill_file = os.path.join(skill_dir, SKILL_FILE)
        if os.path.isdir(skill_dir) and os.path.isfile(skill_file):
            skills[entry] = skill_dir

    return skills


def discover_skills() -> dict[str, str]:
    """Find all skills. Returns {name: skill_dir_path}.

    Project skills override global skills with the same name.
    """
    skills: dict[str, str] = {}

    # Global: ~/.awesome-code/skills/*/SKILL.md
    skills.update(_scan_skills_dir(_global_skills_dir()))

    # Project: .awesome-code/skills/*/SKILL.md (overrides global)
    skills.update(_scan_skills_dir(_project_skills_dir()))

    return skills


def load_skill(name: str) -> str | None:
    """Load skill content by name.

    Returns SKILL.md content + all references/*.md concatenated.
    """
    skills = discover_skills()
    skill_dir = skills.get(name)
    if not skill_dir:
        return None

    skill_file = os.path.join(skill_dir, SKILL_FILE)
    try:
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # Load references if they exist
    refs_dir = os.path.join(skill_dir, REFERENCES_DIR)
    if os.path.isdir(refs_dir):
        ref_parts = []
        for ref_path in sorted(glob.glob(os.path.join(refs_dir, "*.md"))):
            ref_name = os.path.basename(ref_path)
            try:
                with open(ref_path, "r", encoding="utf-8") as f:
                    ref_content = f.read()
                ref_parts.append(f"\n\n--- Reference: {ref_name} ---\n\n{ref_content}")
            except OSError:
                continue
        if ref_parts:
            content += "\n" + "".join(ref_parts)

    return content


def list_skills() -> list[tuple[str, str, str]]:
    """Returns [(name, source, first_line_of_SKILL.md)] for display."""
    skills = discover_skills()
    result = []

    global_dir = _global_skills_dir()

    for name, skill_dir in sorted(skills.items()):
        source = "project" if not skill_dir.startswith(global_dir) else "global"

        # Read first meaningful line from SKILL.md
        skill_file = os.path.join(skill_dir, SKILL_FILE)
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("#"):
                    first_line = first_line.lstrip("# ").strip()
        except OSError:
            first_line = "(unreadable)"

        # Count references
        refs_dir = os.path.join(skill_dir, REFERENCES_DIR)
        ref_count = 0
        if os.path.isdir(refs_dir):
            ref_count = len(glob.glob(os.path.join(refs_dir, "*.md")))

        if ref_count:
            first_line += f" (+{ref_count} refs)"

        result.append((name, source, first_line))

    return result
