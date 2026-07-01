"""orchestration — LangGraph StateGraph-powered pipeline orchestration.

Coordinates the 5-phase pipeline using LangGraph's StateGraph:
1. Setup   → initialize target React Native output environment
2. Scan    → ScanAgent: classify source files by type (rule-based)
3. Convert → LLM-driven code generation via ReAct agents + quality reflection
4. Verify  → build check + AI auto-fix (graph-based retry loop)

Key LangGraph concepts used:
- StateGraph with typed shared state (PipelineState via TypedDict)
- Multi-agent graph (4 agents as nodes sharing one state)
- Conditional routing (verify→fix loop with edge routing)
- Compilation + invocation via .compile().invoke()
"""

from orchestration.pipeline import Pipeline
from orchestration.setup import ProjectSetup

__all__ = ["Pipeline", "ProjectSetup"]
