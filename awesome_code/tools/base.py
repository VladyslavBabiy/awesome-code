from abc import ABC, abstractmethod


class BaseTool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    def execute(self, **kwargs) -> str:
        ...

    async def execute_async(self, **kwargs) -> str:
        """Async execution. Default falls back to sync execute()."""
        return self.execute(**kwargs)
