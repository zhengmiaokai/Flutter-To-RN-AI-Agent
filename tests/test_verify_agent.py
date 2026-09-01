"""tests/test_verify_agent — VerifyAgent error parsing + ReAct fix-loop helpers.

Pure-logic tests only (no LLM calls): structured tsc parsing, the pipeline's
no-progress error signature, the ReAct write-detection helper, and the verify
StateMachine topology (gave_up short-circuit vs success loop-back).
"""
from types import SimpleNamespace

from agents.verify_agent import VerifyAgent, parse_tsc_errors
from framework.state_machine import StateMachine, StepResult, StepStatus
from orchestration.pipeline import _auto_fix, _error_signature


class TestParseTscErrors:
    """Structured tsc output parsing."""

    def test_parses_errors_and_groups_by_file(self):
        output = (
            "src/screens/LoginPage.tsx(20,3): error TS2724: "
            "'\"../providers/LoginMainViewModel\"' has no exported member 'LoginMainViewModel'. "
            "Did you mean 'useLoginMainViewModel'?\n"
            "src/utils/main.ts(6,13): error TS2339: Property 'init' does not exist "
            "on type 'FC<AppContainerProps>'.\n"
        )
        group = parse_tsc_errors(output, target_dir="")
        assert set(group.by_file) == {
            "src/screens/LoginPage.tsx",
            "src/utils/main.ts",
        }
        assert group.by_file["src/utils/main.ts"][0].code == "TS2339"
        # TS2724 is unmapped → "other"; TS2339 → "declaration"
        assert group.by_file["src/screens/LoginPage.tsx"][0].category == "other"
        assert group.by_file["src/utils/main.ts"][0].category == "declaration"

    def test_fix_order_puts_declaration_before_other(self):
        output = (
            "src/screens/LoginPage.tsx(20,3): error TS2724: no export\n"
            "src/utils/main.ts(6,13): error TS2339: no property\n"
        )
        group = parse_tsc_errors(output, target_dir="")
        assert group.file_fix_order == ["src/utils/main.ts", "src/screens/LoginPage.tsx"]

    def test_ignores_garbage_lines(self):
        output = "> webpack 5.0 compiled\nnpm ERR! something\nsrc/a.ts(1,1): error TS2307: no module\n"
        group = parse_tsc_errors(output, target_dir="")
        assert set(group.by_file) == {"src/a.ts"}

    def test_strips_target_dir_prefix(self, tmp_path):
        output = f"{tmp_path}/src/a.ts(1,1): error TS2307: no module\n"
        group = parse_tsc_errors(output, target_dir=str(tmp_path))
        assert list(group.by_file) == ["src/a.ts"]


class TestErrorSignature:
    """Pipeline no-progress detection signature."""

    def test_extracts_file_and_code(self):
        sig = _error_signature(
            "src/screens/LoginPage.tsx(20,3): error TS2724: no export\n"
            "> src/utils/main.ts(6,13): error TS2339: no property\n"
        )
        assert sig == frozenset(
            {"src/screens/LoginPage.tsx|TS2724", "src/utils/main.ts|TS2339"}
        )

    def test_empty_input(self):
        assert _error_signature("") == frozenset()

    def test_identical_errors_identical_signature(self):
        a = _error_signature("src/a.ts(1,1): error TS2307: x")
        b = _error_signature("src/a.ts(1,1): error TS2307: y")
        assert a == b


class TestAgentWroteFile:
    """ReAct write_output_file detection."""

    def _agent(self, *messages):
        return {"messages": list(messages)}

    def test_detects_modern_tool_calls(self):
        msg = SimpleNamespace(
            tool_calls=[{"name": "write_output_file", "args": {"output_path": "/x.ts"}}],
            additional_kwargs={},
            content="",
        )
        assert VerifyAgent._agent_wrote_file(self._agent(msg)) is True

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
        assert VerifyAgent._agent_wrote_file(self._agent(msg)) is True

    def test_ignores_other_tools(self):
        msg = SimpleNamespace(
            tool_calls=[{"name": "run_tsc_check", "args": {"target_dir": "/x"}}],
            additional_kwargs={},
            content="",
        )
        assert VerifyAgent._agent_wrote_file(self._agent(msg)) is False

    def test_empty(self):
        assert VerifyAgent._agent_wrote_file({"messages": []}) is False


class TestVerifyLoopRouting:
    """Verify StateMachine topology: gave_up short-circuits to END."""

    def _make_sm(self, build_fn, fix_fn):
        sm = StateMachine("verify-loop")
        sm.add_step("install", lambda _: StepResult(status=StepStatus.SUCCESS, data={}), retry_count=1)
        sm.add_step("build", build_fn, retry_count=0)
        sm.add_conditional(
            "check",
            lambda d: d.get("build_ok", False) if d else False,
            on_success="done",
            on_failure="fix",
        )
        sm.add_step("fix", fix_fn, retry_count=0)
        sm.add_conditional(
            "fix_router",
            lambda d: not (d.get("gave_up", False) if d else False),
            on_success="build",
            on_failure="done",
        )
        return sm

    def test_gave_up_short_circuits(self):
        """fix giving up must end immediately — no second build round."""
        build_calls = []
        fix_calls = []

        def build(data):
            build_calls.append(1)
            return StepResult(
                status=StepStatus.FAILED,
                data={**data, "build_ok": False, "errors": "src/a.ts(1,1): error TS2307: x"},
            )

        def fix(data):
            fix_calls.append(1)
            return StepResult(
                status=StepStatus.FAILED,
                data={**data, "build_ok": False, "gave_up": True},
                error="gave up",
            )

        results = self._make_sm(build, fix).run({"build_ok": False, "errors": ""})
        assert len(build_calls) == 1
        assert len(fix_calls) == 1
        assert results["fix"].data["gave_up"] is True

    def test_success_loops_back_to_build(self):
        """fix succeeding (not gave_up) must route back to build."""
        build_calls = []
        fix_calls = []

        def build(data):
            build_calls.append(1)
            ok = len(build_calls) >= 2  # pass on the second round
            return StepResult(
                status=StepStatus.SUCCESS if ok else StepStatus.FAILED,
                data={**data, "build_ok": ok, "errors": "" if ok else "src/a.ts(1,1): error TS2307: x"},
            )

        def fix(data):
            fix_calls.append(1)
            return StepResult(status=StepStatus.SUCCESS, data={**data, "build_ok": False, "errors": ""})

        results = self._make_sm(build, fix).run({"build_ok": False, "errors": ""})
        assert len(build_calls) == 2
        assert len(fix_calls) == 1
        assert results["build"].data["build_ok"] is True


class TestAutoFixNoProgress:
    """Pipeline no-progress detection inside the fix loop.

    The data dict (including _prev_error_sig) carries through
    build → check → fix in the real StateMachine; these tests chain the
    returned data the same way.
    """

    ERR_1 = "src/a.ts(1,1): error TS2307: no module"
    ERR_2 = "src/b.ts(2,2): error TS2339: no property"

    class _FakeVerifier:
        def __init__(self, fix_return=0):
            self.config = SimpleNamespace(max_retries=3)
            self.last_fix_results = {}
            self.calls = 0
            self._fix_return = fix_return

        def _auto_fix(self, errors):
            self.calls += 1
            return self._fix_return

    def test_same_errors_across_cycles_stop(self):
        verifier = self._FakeVerifier()
        r1 = _auto_fix(verifier, {"build_ok": False, "errors": self.ERR_1})
        r2 = _auto_fix(verifier, r1.data)  # data chained like the StateMachine does
        assert r2.error == "No progress across fix cycles"
        assert r2.data["gave_up"] is True
        assert verifier.calls == 1  # engine never re-invoked on identical errors

    def test_changed_errors_run_again(self):
        verifier = self._FakeVerifier()
        r1 = _auto_fix(verifier, {"build_ok": False, "errors": self.ERR_1})
        r2 = _auto_fix(verifier, {**r1.data, "errors": self.ERR_2})
        assert verifier.calls == 2

    def test_spurious_success_then_no_progress(self):
        """Fix claims SUCCESS (wrote files), but build re-fails with the same
        error set — cycle 2 must stop without re-invoking the engine."""
        verifier = self._FakeVerifier(fix_return=1)
        r1 = _auto_fix(verifier, {"build_ok": False, "errors": self.ERR_1})
        assert r1.status is StepStatus.SUCCESS
        # build runs again and fails with an identical error set; data preserved
        build_data = {**r1.data, "build_ok": False, "errors": self.ERR_1}
        r2 = _auto_fix(verifier, build_data)
        assert r2.error == "No progress across fix cycles"
        assert r2.data["gave_up"] is True
        assert verifier.calls == 1

    def test_max_retries_still_guards(self):
        verifier = self._FakeVerifier(fix_return=0)
        data = {"build_ok": False, "errors": self.ERR_1}
        r = _auto_fix(verifier, {**data, "_fix_cycle": verifier.config.max_retries})
        assert r.error == "Max auto-fix retries reached"
        assert verifier.calls == 0

    def test_budget_exhausted_marks_gave_up(self):
        """BudgetExceededError from the fix engine must short-circuit to END
        (gave_up=True), not loop build/check/fix without tokens."""
        from framework.harness import BudgetExceededError

        class _BrokeVerifier:
            config = SimpleNamespace(max_retries=3)
            last_fix_results = {}

            def _auto_fix(self, errors):
                raise BudgetExceededError("Token budget (1000) exceeded")

        r = _auto_fix(_BrokeVerifier(), {"build_ok": False, "errors": self.ERR_1})
        assert r.data["gave_up"] is True
        assert "budget" in r.error.lower()
