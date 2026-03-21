import subprocess

from awesome_code.tools.base import BaseTool


class BashTool(BaseTool):
    name = "bash"
    description = "Execute a shell command and return its output (stdout and stderr)."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
            },
        },
        "required": ["command"],
    }

    def execute(self, **kwargs) -> str:
        command = kwargs["command"]
        timeout = kwargs.get("timeout", 30)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=None,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += ("" if not output else "\n") + result.stderr
            if not output:
                output = "(no output)"
            if result.returncode != 0:
                output += f"\n(exit code: {result.returncode})"
            return output
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
