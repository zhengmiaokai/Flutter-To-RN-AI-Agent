"""tests/test_routing — Model routing: env parsing, route resolution, fallback.

Covers the routing logic without touching a real LLM: MODEL_ROUTES parsing,
route inheritance, CLI-override merge semantics, and the harness fallback
chain via a stub LLMClient.
"""

import json

import pytest

from framework.config import Config
from framework.harness import Harness


@pytest.fixture(autouse=True)
def _clean_routes_env(monkeypatch):
    """Keep Config construction hermetic: no MODEL_ROUTES unless a test sets it."""
    monkeypatch.delenv("MODEL_ROUTES", raising=False)


# =========================================================================
# Env parsing
# =========================================================================


def test_env_routes_parsed(monkeypatch):
    monkeypatch.setenv(
        "MODEL_ROUTES",
        json.dumps({"convert": {"model": "strong", "fallback_model": "weak"}}),
    )
    config = Config(api_key="k")
    assert config.model_routes["convert"]["model"] == "strong"
    assert config.model_routes["convert"]["fallback_model"] == "weak"


def test_invalid_env_json_ignored(monkeypatch):
    monkeypatch.setenv("MODEL_ROUTES", "not-json{{{")
    config = Config(api_key="k")
    assert config.model_routes == {}


def test_no_env_route_empty(monkeypatch):
    config = Config(api_key="k")
    assert config.model_routes == {}


# =========================================================================
# route_for inheritance
# =========================================================================


def test_route_for_unrouted_task_uses_global():
    config = Config(api_key="gk", base_url="https://global", model="global-model")
    route = config.route_for("convert")
    assert route.model == "global-model"
    assert route.base_url == "https://global"
    assert route.api_key == "gk"
    assert route.fallback_model is None


def test_route_for_inherits_global_connection():
    config = Config(
        api_key="gk",
        base_url="https://global",
        model_routes={"convert": {"model": "strong"}},
    )
    route = config.route_for("convert")
    assert route.model == "strong"
    assert route.base_url == "https://global"  # inherits global
    assert route.api_key == "gk"  # inherits global


def test_route_for_fallback_inherits_primary_then_global():
    config = Config(
        api_key="gk",
        base_url="https://global",
        model_routes={"convert": {"model": "strong", "fallback_model": "weak"}},
    )
    route = config.route_for("convert")
    assert route.fallback_model == "weak"
    # fallback base_url/api_key inherit the primary connection, then global
    assert route.fallback_base_url == "https://global"
    assert route.fallback_api_key == "gk"


def test_route_for_explicit_fallback_connection():
    config = Config(
        api_key="gk",
        base_url="https://global",
        model_routes={
            "convert": {
                "model": "strong",
                "base_url": "https://strong",
                "api_key": "sk",
                "fallback_model": "weak",
                "fallback_base_url": "https://weak",
                "fallback_api_key": "wk",
            }
        },
    )
    route = config.route_for("convert")
    assert route.model == "strong"
    assert route.base_url == "https://strong"
    assert route.api_key == "sk"
    assert route.fallback_base_url == "https://weak"
    assert route.fallback_api_key == "wk"


def test_route_for_unknown_task_untouched():
    config = Config(
        api_key="k",
        base_url="https://global",
        model_routes={"convert": {"model": "strong"}},
    )
    route = config.route_for("reflect")
    assert route.model == "deepseek-v4-pro"
    assert route.base_url == "https://global"


# =========================================================================
# CLI-override merge semantics (kwargs routes override env per-field)
# =========================================================================


def test_cli_route_overrides_env_fieldwise(monkeypatch):
    monkeypatch.setenv(
        "MODEL_ROUTES",
        json.dumps(
            {
                "convert": {
                    "model": "env-model",
                    "base_url": "https://env",
                    "fallback_model": "env-fb",
                }
            }
        ),
    )
    # CLI: --route convert=cli-model (only the primary model field)
    config = Config(api_key="k", model_routes={"convert": {"model": "cli-model"}})
    entry = config.model_routes["convert"]
    assert entry["model"] == "cli-model"  # overridden
    assert entry["base_url"] == "https://env"  # preserved from env
    assert entry["fallback_model"] == "env-fb"  # preserved from env


# =========================================================================
# Harness fallback chain (stub LLM, no real calls)
# =========================================================================


class _Resp:
    def __init__(self, content: str):
        self.content = content
        self.usage_metadata = None
        self.response_metadata = None


class _StubLLM:
    def __init__(self, make):
        self._make = make

    def invoke(self, messages, **kwargs):
        return _Resp(self._make(messages, kwargs))


class StubLLMClient:
    """get_llm() returns a fake LLM that fails 'primary' the first N times."""

    def __init__(self):
        self.calls: list[str] = []
        self._fail_times: dict[str, int] = {}

    def fail_primary_times(self, n: int):
        self._fail_times["primary"] = n

    def get_llm(self, model=None, base_url=None, api_key=None):
        def make(messages, kwargs):
            self.calls.append(model)
            remaining = self._fail_times.get(model, 0)
            if remaining > 0:
                self._fail_times[model] = remaining - 1
                raise RuntimeError(f"boom: {model}")
            return f"ok-{model}"

        return _StubLLM(make)


def _harness(tmp_path, stub):
    config = Config(
        source_dir=".",
        target_dir=str(tmp_path),
        api_key="k",
        model="global",
        model_routes={"convert": {"model": "primary", "fallback_model": "backup"}},
    )
    return Harness(config, llm=stub)


def test_harness_routes_to_primary_success(tmp_path):
    stub = StubLLMClient()
    harness = _harness(tmp_path, stub)
    result = harness.call(task_type="convert", system_prompt="s", user_message="u")
    assert result.content == "ok-primary"
    assert result.model == "primary"
    assert stub.calls == ["primary"]


def test_harness_retries_primary_then_succeeds(tmp_path):
    stub = StubLLMClient()
    stub.fail_primary_times(1)
    harness = _harness(tmp_path, stub)
    result = harness.call(task_type="convert", system_prompt="s", user_message="u")
    assert result.content == "ok-primary"
    assert stub.calls == ["primary", "primary"]


def test_harness_falls_back_after_primary_exhausted(tmp_path):
    stub = StubLLMClient()
    # Primary fails all its retries; fallback succeeds on first try.
    from framework.harness import _DEFAULT_RETRY_CAP
    stub.fail_primary_times(_DEFAULT_RETRY_CAP)
    harness = _harness(tmp_path, stub)
    result = harness.call(task_type="convert", system_prompt="s", user_message="u")
    assert result.content == "ok-backup"
    assert result.model == "backup"
    assert stub.calls.count("primary") == _DEFAULT_RETRY_CAP
    assert stub.calls.count("backup") == 1
    # Ledger records the successful fallback call with the fallback model.
    ledger_path = harness._ledger._path
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    assert entry["model"] == "backup"
    assert entry["task_type"] == "convert"


def test_harness_raises_when_fallback_also_fails(tmp_path):
    stub = StubLLMClient()
    from framework.harness import _DEFAULT_RETRY_CAP
    stub.fail_primary_times(_DEFAULT_RETRY_CAP)
    stub._fail_times["backup"] = 1
    harness = _harness(tmp_path, stub)
    with pytest.raises(RuntimeError, match="boom: backup"):
        harness.call(task_type="convert", system_prompt="s", user_message="u")
