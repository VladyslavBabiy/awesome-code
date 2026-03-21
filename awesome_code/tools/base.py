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
