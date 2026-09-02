"""orchestration — LangGraph StateGraph-powered pipeline orchestration.

Coordinates the 5-phase pipeline using LangGraph's StateGraph:
1. Setup   → initialize target React Native output environment
2. Scan    → ScanSkill: classify source files by type (rule-based)
3. Convert → ConvertSkill single-shot LLM conversion + ReflectSkill review
4. Verify  → VerifyPhase: tsc build check + FixAgent auto-fix (graph retry loop)

Key LangGraph concepts used:
- StateGraph with typed shared state (PipelineState via TypedDict)
- Deterministic phase nodes + one ReAct agent (FixAgent) for build-error fixing
- Conditional routing (verify→fix loop with edge routing)
- Compilation + invocation via .compile().invoke()
"""

from orchestration.pipeline import Pipeline
from orchestration.setup import ProjectSetup

__all__ = ["Pipeline", "ProjectSetup"]
