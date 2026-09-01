"""tests/test_harness — Budget guard shared with agentic paths (over_budget)."""
from framework.config import Config
from framework.harness import Harness


def _harness(tmp_path, budget):
    config = Config(target_dir=str(tmp_path))
    config.token_budget = budget  # force after __post_init__ (env may override)
    return Harness(config)


class TestOverBudget:
    """Harness.over_budget — the gate agentic paths consult before a ReAct loop."""

    def test_unlimited_budget_never_over(self, tmp_path):
        h = _harness(tmp_path, 0)
        assert h.over_budget() is False
        assert h.over_budget(10_000) is False

    def test_within_budget(self, tmp_path):
        h = _harness(tmp_path, 1000)
        assert h.over_budget() is False
        assert h.over_budget(999) is False

    def test_estimated_exceeds(self, tmp_path):
        h = _harness(tmp_path, 1000)
        assert h.over_budget(1001) is True

    def test_recorded_usage_counts(self, tmp_path):
        h = _harness(tmp_path, 1000)
        h.record_usage("verify_fix", "m", 600, 500)  # spent = 1100
        assert h.over_budget() is True

    def test_private_check_delegates(self, tmp_path):
        # Refactor guard: _budget_exceeded must still behave identically.
        h = _harness(tmp_path, 1000)
        assert h._budget_exceeded("a", "b") is False
        h.record_usage("verify_fix", "m", 1000, 0)
        assert h._budget_exceeded("a" * 400, "b" * 400) is True  # est 200 → 1200
