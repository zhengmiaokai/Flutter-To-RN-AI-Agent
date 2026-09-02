"""skills/ — single-shot capability layer.

Each skill is a deterministic, code-orchestrated capability: inputs in,
``harness.call()`` out. No tool-calling loop, no feedback loop (contrast
``agents/fix_agent.FixAgent``, the only true agent). Every skill declares
``name`` / ``description`` + an IO contract in its docstring so it is
discoverable and dispatchable by a future agent orchestrator.
"""

from skills.base import BaseSkill
from skills.scan_skill import ScanSkill
from skills.convert_skill import ConvertSkill
from skills.reflect_skill import ReflectSkill, ReflectResult

__all__ = [
    "BaseSkill",
    "ScanSkill",
    "ConvertSkill",
    "ReflectSkill",
    "ReflectResult",
]
