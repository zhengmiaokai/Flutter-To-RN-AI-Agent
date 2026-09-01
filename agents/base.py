"""agents/base — Base class for all AI agents in the Flutter-to-RN converter.

Agents hold the Harness (the single LLM entry point) rather than calling
an LLM directly.
"""

from rich.console import Console

from framework.config import Config


class BaseAgent:
    """Base class for all agents in the pipeline.

    Provides harness access and shared logging helpers.
    """

    def __init__(
        self,
        config: Config,
        harness=None,
    ):
        self.config = config
        self.harness = harness
        self.llm = harness.llm if harness is not None else None
        self.console = Console()

    # ---- LangGraph ReAct agent factory --------------------------------------

    def create_agent(
        self,
        tools: list,
        system_prompt: str,
        name: str = "agent",
        model=None,
        base_url=None,
        api_key=None,
    ):
        """Create a compiled LangGraph ReAct agent bound to this agent's LLM.

        Args:
            tools: List of LangChain @tool-decorated functions or BaseTool.
            system_prompt: System prompt for agent behavior.
            name: Agent name (used as graph node identifier).
            model/base_url/api_key: Optional model connection override
                (defaults to the global config connection).

        Returns:
            Compiled LangGraph agent callable via .invoke({'messages': [...]}).
        """
        if self.llm is None:
            raise RuntimeError("LLM not available — cannot create ReAct agent.")
        return self.llm.create_agent(
            tools=tools,
            system_prompt=system_prompt,
            name=name,
            model=model,
            base_url=base_url,
            api_key=api_key,
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
