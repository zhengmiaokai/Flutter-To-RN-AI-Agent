"""tests/test_fix_agent — FixAgent strategy-ladder behavior.

Pure-logic tests with a fake harness / fake compiled graph (no real LLM):
the single-shot degraded modes, fallback-connection retry, the ReAct
write-output detection helper, and the flag-based budget guard (LangChain
swallows callback exceptions, so the callback sets a flag and FixAgent
raises after invoke() returns).
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from framework.config import Config
from framework.harness import BudgetExceededError
from agents.fix_agent import FixAgent, _BudgetCallback


class FakeHarness:
    """Minimal harness stand-in for FixAgent tests.

    ``call()`` returns a fenced code block; ``over_budget`` is configurable so
    tests can exercise the budget guard without a real ledger.
    """

    def __init__(self, content=None, llm=None, over_budget=False):
        self._content = content or (
            "```tsx\n"
            "const fixedValue = 1;\n"
            "const untouchedValue = 2;\n"
            "const longEnough = 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz';\n"
            "```"
        )
        self.llm = llm
        self._over_budget = over_budget
        self.recorded = []

    def call(self, **kwargs):
        return SimpleNamespace(content=self._content)

    def over_budget(self, estimated_tokens=0):
        return self._over_budget

    def record_usage(self, **kwargs):
        self.recorded.append(kwargs)


def _make_config(tmp_path, **overrides):
    kwargs = {
        "target_dir": str(tmp_path),
        "api_key": "test-key",
        "_loaded": True,
    }
    kwargs.update(overrides)
    return Config(**kwargs)


class _NoWriteAgent:
    """Compiled-graph stand-in whose ReAct loop never calls write_output_file."""

    def invoke(self, input, config):
        return {"messages": []}


class _WroteMsg:
    tool_calls = [{"name": "write_output_file", "args": {"output_path": "/x.ts"}}]
    additional_kwargs = {}
    content = ""


class _WroteAgent:
    """Compiled-graph stand-in that wrote the file via the tool."""

    def invoke(self, input, config):
        return {"messages": [_WroteMsg()]}


class TestFixSingleShot:
    """Strategy-ladder degraded modes."""

    def test_no_llm_uses_single_shot(self, tmp_path):
        """Fallback ①: no LLM → straight to the single-shot harness fix."""
        harness = FakeHarness(llm=None)
        agent = FixAgent(_make_config(tmp_path), harness)
        file = tmp_path / "src" / "A.ts"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("bad")

        assert agent.fix(file, "src/A.ts(1,1): error TS2307: no module", "src/A.ts", tmp_path) is True
        assert "const fixedValue = 1;" in file.read_text()

    def test_react_no_write_falls_back_to_single_shot(self, tmp_path):
        """Fallback ③: ReAct wrote nothing → single-shot harness fix."""
        harness = FakeHarness(llm=object())
        agent = FixAgent(_make_config(tmp_path), harness)
        agent.create_agent = lambda *a, **k: _NoWriteAgent()
        file = tmp_path / "src" / "A.ts"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("bad")

        assert agent.fix(file, "src/A.ts(1,1): error TS2307: no module", "src/A.ts", tmp_path) is True
        assert "const fixedValue = 1;" in file.read_text()

    def test_react_success_via_tool_write(self, tmp_path):
        """ReAct wrote via the tool → True, no single-shot fallback."""
        harness = FakeHarness(llm=object())
        agent = FixAgent(_make_config(tmp_path), harness)
        agent.create_agent = lambda *a, **k: _WroteAgent()
        file = tmp_path / "src" / "A.ts"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("bad")

        assert agent.fix(file, "err", "src/A.ts", tmp_path) is True


class TestAgentWroteFile:
    """ReAct write_output_file detection (strategy-ladder step 6)."""

    def _agent(self, *messages):
        return {"messages": list(messages)}

    def test_detects_modern_tool_calls(self):
        msg = SimpleNamespace(
            tool_calls=[{"name": "write_output_file", "args": {"output_path": "/x.ts"}}],
            additional_kwargs={},
            content="",
        )
        assert FixAgent._agent_wrote_file(self._agent(msg)) is True

    def test_detects_legacy_additional_kwargs(self):
        msg = SimpleNamespace(
            tool_calls=[],
            additional_kwargs={
                "tool_calls": [
                    {"function": {"name": "write_output_file", "arguments": "{}"}}
                ]
            },
            content="",
        )
        assert FixAgent._agent_wrote_file(self._agent(msg)) is True

    def test_ignores_other_tools(self):
        msg = SimpleNamespace(
            tool_calls=[{"name": "run_tsc_check", "args": {"target_dir": "/x"}}],
            additional_kwargs={},
            content="",
        )
        assert FixAgent._agent_wrote_file(self._agent(msg)) is False

    def test_empty(self):
        assert FixAgent._agent_wrote_file({"messages": []}) is False


class TestFallbackConnection:
    """Primary-connection failure retries on the configured fallback."""

    def test_primary_failure_retries_fallback(self, tmp_path):
        calls = []

        def fake_create_agent(tools, system_prompt, name="agent", model=None, base_url=None, api_key=None):
            calls.append(model)
            if model == "primary-model":
                raise RuntimeError("primary connection down")
            return _WroteAgent()

        harness = FakeHarness(llm=object())
        config = _make_config(
            tmp_path,
            model="primary-model",
            model_routes={
                "verify_fix": {"model": "primary-model", "fallback_model": "fallback-model"}
            },
        )
        agent = FixAgent(config, harness)
        agent.create_agent = fake_create_agent
        file = tmp_path / "src" / "A.ts"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("bad")

        assert agent.fix(file, "err", "src/A.ts", tmp_path) is True
        assert calls == ["primary-model", "fallback-model"]

    def test_compiled_graph_cached_per_connection(self, tmp_path):
        """Same connection key → create_agent called once, graph reused."""
        create_calls = []

        def fake_create_agent(tools, system_prompt, name="agent", model=None, base_url=None, api_key=None):
            create_calls.append(model)
            return _WroteAgent()

        harness = FakeHarness(llm=object())
        config = _make_config(tmp_path, model="m", model_routes={"verify_fix": {"model": "m"}})
        agent = FixAgent(config, harness)
        agent.create_agent = fake_create_agent
        file_a = tmp_path / "A.ts"
        file_a.write_text("bad")
        file_b = tmp_path / "B.ts"
        file_b.write_text("bad")

        assert agent.fix(file_a, "err", "A.ts", tmp_path) is True
        assert agent.fix(file_b, "err", "B.ts", tmp_path) is True
        assert create_calls == ["m"]  # second file reused the cached graph


class TestBudgetGuard:
    """Flag-based budget guard (callbacks cannot raise in LangChain)."""

    def test_callback_sets_flag_when_over_budget(self):
        class OverHarness:
            def over_budget(self, estimated_tokens=0):
                return True

        cb = _BudgetCallback(OverHarness(), "m", "screens")
        cb.on_llm_start({}, [])
        assert cb.budget_exceeded is True

    def test_callback_records_per_step_usage(self):
        harness = FakeHarness(llm=object())
        cb = _BudgetCallback(harness, "m", "screens")

        class Gen:
            generation_info = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}

        class Response:
            llm_output = {}
            generations = [[Gen()]]

        cb.on_llm_end(Response())
        assert len(harness.recorded) == 1
        assert harness.recorded[0]["prompt_tokens"] == 10
        assert harness.recorded[0]["completion_tokens"] == 5
        assert harness.recorded[0]["category"] == "screens"

    def test_run_react_raises_when_flag_set(self, tmp_path):
        """on_llm_start over budget → flag set → invoke() returns → raise."""
        harness = FakeHarness(llm=object(), over_budget=True)
        agent = FixAgent(_make_config(tmp_path), harness)

        class FlagAgent:
            def invoke(self, input, config):
                for cb in config.get("callbacks", []):
                    cb.on_llm_start({}, [])
                return {"messages": []}

        agent.create_agent = lambda *a, **k: FlagAgent()
        route = agent.config.route_for("verify_fix")

        with pytest.raises(BudgetExceededError):
            agent._run_react(route, "prompt", str(tmp_path / "A.ts"), str(tmp_path), "src/A.ts")

    def test_budget_exceeded_propagates_not_degraded(self, tmp_path):
        """BudgetExceededError must propagate — never degrade to single-shot."""
        harness = FakeHarness(llm=object())
        agent = FixAgent(_make_config(tmp_path), harness)
        file = tmp_path / "src" / "A.ts"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("bad")

        with patch.object(agent, "_run_react", side_effect=BudgetExceededError("budget exceeded")):
            with pytest.raises(BudgetExceededError):
                agent.fix(file, "err", "src/A.ts", tmp_path)
