"""framework/harness — thin LLM call orchestration layer.

The single entry point for all LLM calls in the pipeline. Composes the
cross-cutting concerns:

- per-task adaptation : each request is sized to its task (max_tokens etc.)
- model routing       : task_type picks its own model connection (config
                        model_routes); primary retries, then falls back once
- token ledger        : per-call accounting, persisted to target_dir
- response cache      : key = fully-assembled input + model + temperature + salt
- memory injection    : appended to the USER message (never the system prompt,
                        preserving the stable-prefix disk cache)
- budget guard        : optional hard token cap
- retry cap           : bounded total attempts on the single model
- response_format     : json_object where the provider supports it, else degrade

Not a ReAct/agentic harness — ConvertSkill proved single-shot beats a tool
loop for this domain, so this layer only orchestrates single calls. Agentic
paths (the FixAgent ReAct fix loop) share the same token ledger and budget via
record_usage / over_budget, but run their own loop and never flow through call.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from framework.config import Config
from framework.llm import LLMClient

# Bump to invalidate the whole response cache when prompt assembly changes.
_CACHE_SALT = "harness-v1"

# Max total attempts for a single logical call.
_DEFAULT_RETRY_CAP = 3

# Task names shared with the skills and the fix agent.
TASK_SCAN_CLASSIFY = "scan_classify"
TASK_CONVERT = "convert"
TASK_REFLECT = "reflect"
TASK_CONVERT_FIX = "convert_fix"
TASK_VERIFY_FIX = "verify_fix"

# Per-task call policy. The harness sizes each request to its task: code
# generation gets a big output budget, cheap JSON classification a small one.
# The model itself comes from Config.route_for (see call()).
_TASK_MAX_TOKENS: dict[str, int] = {
    TASK_SCAN_CLASSIFY: 2048,
    TASK_CONVERT: 8192,
    TASK_CONVERT_FIX: 8192,
    TASK_REFLECT: 4096,
    TASK_VERIFY_FIX: 8192,
}


@dataclass
class HarnessResult:
    """Result of a harness.call(), including raw usage metadata."""

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cache_hit: bool = False
    cache_hit_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: int = 0
    raw_usage: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class TokenLedger:
    """Thread-safe token accounting, persisted as JSONL in the target dir."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        self._entries.append(json.loads(line))
            except Exception:
                self._entries = []

    def record(
        self,
        task_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        category: str | None = None,
        cache_hit: bool = False,
        cache_hit_tokens: int = 0,
        reasoning_tokens: int = 0,
        latency_ms: int = 0,
        status: str = "ok",
    ):
        entry = {
            "ts": time.time(),
            "task_type": task_type,
            "category": category,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cache_hit": cache_hit,
            "cache_hit_tokens": cache_hit_tokens,
            "reasoning_tokens": reasoning_tokens,
            "latency_ms": round(latency_ms),
            "status": status,
        }
        with self._lock:
            self._entries.append(entry)
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def spent(self) -> int:
        """Total tokens billed across all recorded calls (cache hits excluded)."""
        with self._lock:
            return sum(
                e["prompt_tokens"] + e["completion_tokens"]
                for e in self._entries
                if not e.get("cache_hit")
            )

    def report(self) -> dict:
        """Per-task totals for the final console summary."""
        with self._lock:
            by_task: dict[str, dict] = {}
            for e in self._entries:
                t = by_task.setdefault(
                    e["task_type"],
                    {"calls": 0, "prompt": 0, "completion": 0, "cache_hits": 0},
                )
                t["calls"] += 1
                t["prompt"] += e["prompt_tokens"]
                t["completion"] += e["completion_tokens"]
                if e.get("cache_hit"):
                    t["cache_hits"] += 1
            return by_task


class ResponseCache:
    """Disk-backed response cache with TTL and thread safety."""

    def __init__(self, path: Path, ttl_hours: int, enabled: bool):
        self._path = path
        self._ttl_hours = ttl_hours
        self._enabled = enabled
        self._lock = threading.Lock()
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self):
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            pass

    def _prune_locked(self):
        if self._ttl_hours <= 0:
            return
        cutoff = time.time() - self._ttl_hours * 3600
        stale = [k for k, v in self._data.items() if v.get("ts", 0) < cutoff]
        for k in stale:
            self._data.pop(k, None)

    def get(self, key: str) -> Optional[str]:
        if not self._enabled:
            return None
        with self._lock:
            self._prune_locked()
            entry = self._data.get(key)
            if not entry:
                return None
            return entry.get("value")

    def set(self, key: str, value: str):
        if not self._enabled:
            return
        with self._lock:
            self._data[key] = {"ts": time.time(), "value": value}
            self._save()


class BudgetExceededError(RuntimeError):
    """Raised when the configured token budget cannot accommodate a call."""


class Harness:
    """Thin orchestration layer — the only way the pipeline talks to an LLM."""

    def __init__(
        self,
        config: Config,
        llm: Optional[LLMClient] = None,
        ledger: Optional[TokenLedger] = None,
        cache: Optional[ResponseCache] = None,
        memory_store=None,
    ):
        self._config = config
        self.llm = llm or LLMClient(config)
        self._ledger = ledger or TokenLedger(
            Path(config.target_dir) / ".token_ledger.jsonl"
        )
        self._cache = cache or ResponseCache(
            Path(config.target_dir) / ".llm_cache.json",
            config.cache_ttl_hours,
            config.cache_enabled,
        )
        self._memory = memory_store
        self._console_import = None

    # ---- public API ---------------------------------------------------------

    def call(
        self,
        task_type: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        category: str | None = None,
        cache: bool | None = None,
        memory: str = "",
        response_format: str | None = None,
        cache_validator: Callable[[str], bool] | None = None,
    ) -> HarnessResult:
        """Orchestrate a single LLM call: cache → invoke → account.

        Args:
            task_type: Task key (scan_classify/convert/reflect/...). Selects
                the per-task call policy (max_tokens) when the caller doesn't
                pass an explicit value.
            system_prompt: Stable prefix — part of the cache key, must stay
                byte-identical to hit the provider's disk prefix cache.
            user_message: Task content; memory is appended here, never to
                the system prompt.
            temperature: Explicit — reasoning-type models may ignore it.
            max_tokens: Overrides the per-task policy budget (None = task policy).
            category: Convert category (screens/models/...) — used for the
                few-shot memory lookup.
            cache: None=auto (enabled when temperature == 0), else forced.
            memory: Extra memory block appended to the user message.
            response_format: "json_object" to request structured JSON when
                the provider supports it (degraded to plain text otherwise).
            cache_validator: If provided, a response is only stored in the
                cache when it returns True (e.g. the caller extracted a
                valid code block).
        """
        route = self._config.route_for(task_type)
        use_cache = self._cache_decision(cache, temperature)
        if memory and self._config.memory_enabled:
            user_message = user_message + "\n\n" + memory
        # Auto-inject few-shots + project digest for conversion tasks
        auto_memory = self._auto_memory(task_type, category)
        if auto_memory:
            user_message = user_message + "\n\n" + auto_memory

        if max_tokens is None:
            max_tokens = _TASK_MAX_TOKENS.get(task_type)

        # Connection chain: primary retried up to the cap, then fallback once.
        plan = [
            ((route.model, route.base_url, route.api_key), _DEFAULT_RETRY_CAP),
        ]
        if route.fallback_model:
            plan.append(
                (
                    (route.fallback_model, route.fallback_base_url, route.fallback_api_key),
                    1,
                )
            )

        # Cache lookup for the primary model — mirrors the single-model fast path.
        model = route.model
        cache_key = self._cache_key(
            system_prompt, user_message, max_tokens, temperature, model, route.base_url
        )
        cached = self._cache.get(cache_key) if use_cache else None
        if cached is not None:
            self._ledger.record(
                task_type, model, 0, 0, category=category, cache_hit=True,
            )
            return HarnessResult(
                content=cached,
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                cache_hit=True,
            )

        last_error: Exception | None = None
        for (m, b, k), attempts in plan:
            for _ in range(attempts):
                if self._budget_exceeded(system_prompt, user_message):
                    continue
                try:
                    result = self._invoke_attempt(
                        task_type, category,
                        system_prompt, user_message, temperature,
                        max_tokens, response_format, m, b, k,
                    )
                    if use_cache and (cache_validator is None or cache_validator(result.content)):
                        self._cache.set(
                            self._cache_key(
                                system_prompt, user_message, max_tokens,
                                temperature, m, b,
                            ),
                            result.content,
                        )
                    return result
                except BudgetExceededError:
                    raise
                except Exception as exc:
                    last_error = exc
                    self._warn(f"LLM call failed ({m}): {str(exc)[:200]}")
                    continue

        if self._budget_exceeded(system_prompt, user_message):
            raise BudgetExceededError(
                f"Token budget ({self._config.token_budget}) exceeded for {task_type}."
            )
        raise last_error or RuntimeError(f"LLM call failed for {task_type}")

    # ---- reporting ----------------------------------------------------------

    def report(self) -> dict:
        """Per-task token totals, printed by the pipeline at run end."""
        return self._ledger.report()

    def record_usage(
        self,
        task_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        category: str | None = None,
    ):
        """Record an aggregated usage entry (for calls that bypass `call`).

        ReAct agents invoke the model directly through the LLMClient pool, so
        they don't flow through Harness.call. This keeps the token ledger /
        budget guard / report accounting complete for those calls.
        """
        self._ledger.record(
            task_type,
            model,
            prompt_tokens,
            completion_tokens,
            category=category,
        )

    def over_budget(self, estimated_tokens: int = 0) -> bool:
        """True if spending ~estimated_tokens more would exceed the budget.

        Public so agentic paths that bypass `call` (the ReAct fix loop) can
        consult the same shared ledger/budget before starting a multi-step
        loop — their internal calls can't be gated per-call, so they check
        once up front and their recursion_limit bounds the worst case.
        """
        budget = self._config.token_budget
        if budget <= 0:
            return False
        return self._ledger.spent() + estimated_tokens > budget

    # ---- internals ----------------------------------------------------------

    def _cache_decision(self, cache: bool | None, temperature: float) -> bool:
        if cache is not None:
            return cache
        # Auto: only cache deterministic (temperature == 0) calls
        return self._config.cache_enabled and temperature == 0

    def _cache_key(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None,
        temperature: float,
        model: str,
        base_url: str | None = None,
    ) -> str:
        # base_url is in the key so the same model name on two providers
        # doesn't share cache entries.
        raw = (
            f"{_CACHE_SALT}|{base_url or ''}|{model}|{max_tokens}|{temperature}|"
            f"{system_prompt}|{user_message}"
        )
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _budget_exceeded(self, system_prompt: str, user_message: str) -> bool:
        estimated_input = (len(system_prompt) + len(user_message)) // 4
        return self.over_budget(estimated_input)

    def _auto_memory(self, task_type: str, category: str | None) -> str:
        """Auto-inject conversion few-shots + project digest into user message."""
        if not self._config.memory_enabled or self._memory is None:
            return ""
        if task_type not in (TASK_CONVERT, TASK_CONVERT_FIX):
            return ""
        blocks = []
        digest = self._memory.get_project_digest()
        if digest:
            blocks.append(digest)
        few_shots = self._memory.query_few_shots(category or "other", top_k=2)
        if few_shots:
            blocks.append(few_shots)
        return "\n\n".join(blocks)

    def _invoke_attempt(
        self,
        task_type: str,
        category: str | None,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int | None,
        response_format: str | None,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> HarnessResult:
        llm = self.llm.get_llm(model=model, base_url=base_url, api_key=api_key)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        kwargs: dict = {"temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        start = time.monotonic()
        if response_format:
            try:
                response = llm.invoke(messages, **kwargs, response_format={"type": response_format})
            except Exception as exc:
                if self._response_format_rejected(exc):
                    self._warn(
                        f"response_format={response_format} rejected by "
                        f"{model}; degrading to plain text JSON."
                    )
                    response = llm.invoke(messages, **kwargs)
                else:
                    raise
        else:
            response = llm.invoke(messages, **kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        result = self._parse_result(response, model, latency_ms)
        self._ledger.record(
            task_type,
            model,
            result.prompt_tokens,
            result.completion_tokens,
            category=category,
            cache_hit_tokens=result.cache_hit_tokens,
            reasoning_tokens=result.reasoning_tokens,
            latency_ms=latency_ms,
        )
        return result

    def _parse_result(self, response, model: str, latency_ms: int) -> HarnessResult:
        content = response.content
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    parts.append(str(p.get("text", "")))
                else:
                    parts.append(str(p))
            content = "".join(parts)
        content = str(content or "")

        um: dict = {}
        raw: dict = {}
        try:
            um = getattr(response, "usage_metadata", None) or {}
            raw = (
                (getattr(response, "response_metadata", None) or {})
                .get("token_usage", {})
                or {}
            )
        except Exception:
            pass

        prompt_tokens = um.get("input_tokens") or raw.get("prompt_tokens") or 0
        completion_tokens = um.get("output_tokens") or raw.get("completion_tokens") or 0
        cache_hit_tokens = raw.get("prompt_cache_hit_tokens") or 0
        details = raw.get("completion_tokens_details") or {}
        reasoning_tokens = details.get("reasoning_tokens") or 0

        return HarnessResult(
            content=content,
            model=model,
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            cache_hit_tokens=int(cache_hit_tokens),
            reasoning_tokens=int(reasoning_tokens),
            latency_ms=latency_ms,
            raw_usage=raw,
        )

    @staticmethod
    def _response_format_rejected(exc: Exception) -> bool:
        text = str(exc)
        status = getattr(exc, "status_code", None)
        return (
            status == 400
            or "response_format" in text
            or "BadRequest" in type(exc).__name__
            or "unsupported" in text
            or "Invalid" in text and "parameter" in text
        )

    def _warn(self, message: str):
        try:
            from rich.console import Console
            Console().print(f"[yellow][Harness][/yellow] {message}")
        except Exception:
            pass
