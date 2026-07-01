"""agents/base — Base class for all AI agents in the Flutter-to-RN converter.

Provides shared infrastructure built on LangChain/LangGraph:
- self.llm         → LLMClient wrapping ChatOpenAI (LangChain powered)
- self.config      → Application configuration
- self.create_agent() → Factory for LangGraph ReAct agents

Each subclass defines its system prompt and tool set, then calls
self.create_agent() to get a compiled LangGraph agent.
"""

from rich.console import Console

from framework.config import Config
from framework.llm import LLMClient


class BaseAgent:
    """Base class for all agents in the pipeline.

    Provides LLM client access and a factory method for creating
    LangGraph ReAct agents.
    """

    def __init__(
        self,
        config: Config,
        llm: LLMClient | None = None,
    ):
        self.config = config
        self.llm = llm
        self.console = Console()

    # ---- LangGraph agent factory --------------------------------------------

    def create_agent(self, tools: list, system_prompt: str, name: str = "agent"):
        """Create a LangGraph ReAct agent bound to this agent's LLM.

        Args:
            tools: List of LangChain @tool-decorated functions or BaseTool.
            system_prompt: System prompt for agent behavior.
            name: Agent name (used as graph node identifier).

        Returns:
            Compiled LangGraph agent callable via .invoke({'messages': [...]}).
        """
        if self.llm is None:
            raise RuntimeError("LLM not available — cannot create ReAct agent.")
        return self.llm.create_agent(
            tools=tools,
            system_prompt=system_prompt,
            name=name,
        )

    # ---- logging ------------------------------------------------------------

    def log_info(self, tag: str, message: str):
        self.console.print(f"[cyan][{tag}][/cyan] {message}")

    def log_success(self, tag: str, message: str):
        self.console.print(f"[green][{tag}][/green] {message}")

    def log_warn(self, tag: str, message: str):
        self.console.print(f"[yellow][{tag}][/yellow] {message}")

    def log_error(self, tag: str, message: str):
        self.console.print(f"[red][{tag}][/red] {message}")

    def log_dim(self, tag: str, message: str):
        self.console.print(f"[dim][{tag}][/dim] {message}")
