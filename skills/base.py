"""skills/base — base class for single-shot conversion skills.

A Skill is a deterministic, code-orchestrated capability that performs a
single fixed-batch ``harness.call()`` (or pure local logic) with no tool
calling loop and no feedback loop — unlike agents/, which own ReAct loops
(the only one being ``agents.fix_agent.FixAgent``).

Every Skill declares a ``name`` and ``description`` so it is self-describing
and can later be discovered/dispatched by a real agent orchestrator.
"""

from rich.console import Console

from framework.config import Config


class BaseSkill:
    """Base class for single-shot skills in the pipeline.

    Provides harness access and shared logging helpers. Skills are stateless
    capabilities: inputs in, ``harness.call()`` out — they never build or
    drive a tool-calling agent.
    """

    # Skill contract (for future agent orchestration / discovery).
    name = "base"
    description = ""

    def __init__(self, config: Config, harness=None):
        self.config = config
        self.harness = harness
        self.llm = harness.llm if harness is not None else None
        self.console = Console()

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
