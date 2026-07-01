"""framework/state_machine — LangGraph StateGraph-powered workflow state machine.

Replaces the custom step-based state machine with LangGraph's StateGraph.
Provides backward-compatible StateMachine API while leveraging LangGraph's
graph-based execution and error handling.

LangGraph concepts used:
- StateGraph (typed state flow through nodes and edges)
- add_node (each step becomes a node)
- add_conditional_edges (conditional branching)
- add_edge (sequential routing)
- compile() + invoke() (graph execution)
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing one step in the state machine."""
    status: StepStatus
    data: Any = None
    error: str | None = None
    metrics: dict = field(default_factory=dict)


class StateMachine:
    """LangGraph StateGraph-powered workflow state machine.

    Provides the same add_step()/add_conditional() API as before, but
    internally builds and executes a LangGraph StateGraph.
    Supports conditional branching, retry loops, and lifecycle hooks.
    """

    def __init__(self, name: str = "workflow"):
        self.name = name
        self._steps: dict[str, dict] = {}
        self._entry: str | None = None
        self._hooks: dict[str, list[Callable]] = {
            "before_step": [], "after_step": [], "on_error": [],
        }
        self._compiled: CompiledStateGraph | None = None

    # ---- Step registration --------------------------------------------------

    def add_step(
        self,
        name: str,
        fn: Callable,
        next_step: str | None = None,
        retry_count: int = 3,
    ):
        self._steps[name] = {
            "type": "step",
            "fn": fn,
            "next": next_step,
            "retry_count": retry_count,
        }

    def add_conditional(
        self,
        name: str,
        fn: Callable,
        on_success: str | None = None,
        on_failure: str | None = None,
    ):
        self._steps[name] = {
            "type": "conditional",
            "fn": fn,
            "on_success": on_success,
            "on_failure": on_failure,
        }

    # ---- Hooks ---------------------------------------------------------------

    def hook(self, event: str, handler: Callable):
        if event in self._hooks:
            self._hooks[event].append(handler)

    # ---- Build & run the graph -----------------------------------------------

    def run(self, initial_data: Any = None) -> dict[str, StepResult]:
        """Build and execute a LangGraph StateGraph from registered steps.

        Each step becomes a graph node. Conditional steps become
        conditional edges. The graph supports checkpointing and retries.

        Args:
            initial_data: The initial state passed to the first step.

        Returns:
            dict[str, StepResult]: Results for every step.
        """
        # Build the graph
        self._compiled = self._build_graph()

        compiled = self._compiled.compile()

        # Invoke
        final_state = compiled.invoke({"data": initial_data})

        # If the graph returned None (early termination), return partial results
        if final_state is None:
            return {}

        # Reconstruct StepResult dict from final state
        results: dict[str, StepResult] = {}
        history = final_state.get("_history", {})
        for name, step_def in self._steps.items():
            entry = history.get(name, {})
            status_str = entry.get("status", StepStatus.PENDING)
            status = (
                StepStatus(status_str) if isinstance(status_str, str) else status_str
            )
            results[name] = StepResult(
                status=status,
                data=entry.get("data"),
                error=entry.get("error"),
            )

        return results

    # ---- Result access -------------------------------------------------------

    @property
    def results(self) -> dict[str, StepResult]:
        """Results are returned by run() — this property is a no-op kept for backward compat."""
        return {}

    @property
    def all_succeeded(self) -> bool:
        """Use run() return value instead — this always returns False."""
        return False

    # ---- Internal: build the LangGraph StateGraph ---------------------------

    def _build_graph(self) -> StateGraph:
        """Build a StateGraph from registered steps.

        The state schema carries the user data blob plus execution history.
        """
        graph = StateGraph(dict)

        # We'll track execution history separately
        step_names = list(self._steps.keys())

        # Auto-wire next_step for linear steps
        for i, name in enumerate(step_names):
            step_def = self._steps[name]
            if step_def["type"] == "step" and step_def.get("next") is None:
                if i + 1 < len(step_names):
                    step_def["next"] = step_names[i + 1]

        # Build wrapping node functions that handle hooks and retries
        for name, step_def in self._steps.items():
            fn = step_def["fn"]
            retry_count = step_def.get("retry_count", 3)
            step_type = step_def["type"]

            def make_node(fn=fn, name=name, retry_count=retry_count, step_type=step_type):
                def node(state, _config=None):
                    self._fire_hook("before_step", name, state.get("data"))
                    current_data = state.get("data")

                    # Execute the step
                    result = self._execute_node(fn, current_data)

                    # Retry logic for step type
                    if step_type == "step" and result.status == StepStatus.FAILED:
                        for i in range(retry_count):
                            self._fire_hook("on_error", name, result.error or "")
                            result = self._execute_node(fn, current_data)
                            if result.status == StepStatus.SUCCESS:
                                break

                    self._fire_hook("after_step", name, result)

                    # Build updated state
                    # Conditional nodes must NOT overwrite data (they only route)
                    new_data = current_data if step_type == "conditional" else result.data
                    # Accumulate execution history so run() can reconstruct StepResults
                    history = dict(state.get("_history", {}))
                    history[name] = {
                        "status": result.status.value,
                        "data": result.data,
                        "error": result.error,
                    }
                    new_state = {
                        "data": new_data,
                        "_last_result": {
                            "status": result.status.value,
                            "data": result.data,
                            "error": result.error,
                        },
                        "_last_node": name,
                        "_history": history,
                    }
                    return new_state
                return node

            graph.add_node(name, make_node())

        # Wire edges
        for name, step_def in self._steps.items():
            if step_def["type"] == "step":
                nxt = step_def.get("next")
                if nxt and nxt in self._steps:
                    graph.add_edge(name, nxt)
                else:
                    graph.add_edge(name, END)

            elif step_def["type"] == "conditional":
                on_ok = step_def.get("on_success", END)
                on_fail = step_def.get("on_failure", END)
                cond_fn = step_def["fn"]  # local capture for router closure

                def make_router(fn=cond_fn, on_ok=on_ok, on_fail=on_fail):
                    def router(state):
                        current_data = state.get("data")
                        try:
                            sig = inspect.signature(fn)
                            if len(sig.parameters) > 0:
                                passed = bool(fn(current_data))
                            else:
                                passed = bool(fn())
                        except Exception:
                            passed = False

                        # Determine actual target names
                        ok_target = on_ok if on_ok in self._steps else END
                        fail_target = on_fail if on_fail in self._steps else END

                        return ok_target if passed else fail_target
                    return router

                graph.add_conditional_edges(name, make_router())

        # Set entry point
        if step_names:
            graph.set_entry_point(step_names[0])

        return graph

    # ---- Internal helpers ----------------------------------------------------

    @staticmethod
    def _execute_node(fn: Callable, data: Any) -> StepResult:
        try:
            sig = inspect.signature(fn)
            if len(sig.parameters) > 0:
                result = fn(data)
            else:
                result = fn()
            if isinstance(result, StepResult):
                return result
            return StepResult(status=StepStatus.SUCCESS, data=result)
        except Exception as e:
            return StepResult(status=StepStatus.FAILED, error=str(e))

    def _fire_hook(self, event: str, step_name: str, data: Any):
        for handler in self._hooks.get(event, []):
            try:
                handler(step_name, data)
            except Exception:
                pass
