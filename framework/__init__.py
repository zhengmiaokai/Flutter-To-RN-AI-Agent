"""framework — Infrastructure layer for the Flutter-to-RN converter.

Provides configuration, LangChain-powered LLM client, JSON-file-backed
state persistence, and LangGraph StateGraph-based state machine — with
zero business logic.

All LLM interactions flow through LangChain (ChatOpenAI) and all
workflow orchestration flows through LangGraph (StateGraph).

Modules:
- config.py          → Config dataclass + env loading
- llm.py             → LangChain ChatOpenAI-powered LLM client
- state.py           → JSON file backed checkpoint/resume state
- state_machine.py   → LangGraph StateGraph-based workflow state machine
"""

from framework.config import Config, get_config, init_config
from framework.llm import LLMClient
from framework.state import StateManager
from framework.state_machine import StateMachine, StepResult, StepStatus

__all__ = [
    "Config", "get_config", "init_config",
    "LLMClient", "StateManager",
    "StateMachine", "StepResult", "StepStatus",
]
