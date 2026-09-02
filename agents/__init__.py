"""agents — Agent layer for the Flutter-to-RN conversion pipeline.

FixAgent is the only true agent: a LangGraph ReAct loop (read → write → tsc →
iterate) that fixes TypeScript build errors with a hard feedback signal. The
single-shot scan/convert/reflect capabilities moved to skills/ — they are
deterministic single ``harness.call()`` steps with no tool loop.

Dependency rule: agents do not import skills, and skills do not import
agents; orchestration/verify.py is the only place that wires them together
(via set_fix_agent setter injection).
"""

from agents.base import BaseAgent
from agents.fix_agent import FixAgent

__all__ = [
    "BaseAgent",
    "FixAgent",
]
