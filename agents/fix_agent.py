"""agents/fix_agent — the pipeline's only true ReAct agent.

Fixes TypeScript build errors with a self-verifying tool loop: the agent is
given read_source_file / write_output_file / run_tsc_check / run_build_check
so it can read companion files, write the fix, and run tsc to verify BEFORE
returning. This is the one place in the pipeline where an LLM drives a
decision loop with a hard feedback signal (tsc) — hence an Agent, not a Skill.

Strategy ladder (ReAct first, single-shot as the internal degraded mode):

1. read the source — fail → False
2. no LLM available → single-shot (fallback ①)
3. pre-loop budget guard — exhausted → raise BudgetExceededError
4. run the compiled ReAct graph on the primary model connection
5. non-budget failure → retry once on the fallback connection (if configured);
   when both fail → single-shot (fallback ②)
6. agent wrote via write_output_file → True
7. else extract a code block from the final message → write → True
8. no write at all → single-shot (fallback ③)

BudgetExceededError always propagates (the pipeline gives up) — it is never
degraded to single-shot.

Budget guard notes: langchain callback handlers swallow exceptions (verified
empirically), so on_llm_start cannot raise to stop the loop. Instead the
callback sets a budget_exceeded flag, records per-step usage in on_llm_end
(so the shared ledger grows during the loop), and FixAgent checks the flag
AFTER invoke() returns and raises then. Worst case one file's loop runs
(bounded by recursion_limit=20) before the verify phase gives up.
"""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage

from framework.config import Config, ModelRoute
from framework.file_categories import infer_file_category
from framework.harness import BudgetExceededError
from agents.base import BaseAgent
from tools import VERIFY_FIX_TOOLS
from prompts.verify import (
    BUILD_FIX_SYSTEM,
    get_fix_prompt,
    HYBRID_FIX_SYSTEM,
    get_hybrid_fix_prompt,
)

# Cap on source code sent to the fix prompt (bounds per-call token cost).
_MAX_FIX_SOURCE_CHARS = 16000

_CODE_BLOCK_RE = re.compile(
    r"```(?:tsx|typescript|ts|jsx|javascript|js|json)\n(.*?)```",
    re.DOTALL,
)


def _extract_code_block(text: str) -> str | None:
    """Extract the first fenced code block from an LLM response."""
    m = _CODE_BLOCK_RE.search(text or "")
    return m.group(1).strip() if m else None


def _llm_usage(response) -> tuple[int, int]:
    """Best-effort (prompt_tokens, completion_tokens) from a LangChain LLMResult.

    Token usage lives in different places depending on the provider/model:
    llm_output["token_usage"] (OpenAI via callbacks) or
    generations[i][0].generation_info["token_usage"]. Try both, fall back to 0.
    """
    usage: dict = {}
    try:
        llm_output = getattr(response, "llm_output", None) or {}
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or {}
    except Exception:
        pass
    if not usage:
        try:
            gens = getattr(response, "generations", None) or [[]]
            first = (gens[0] or [None])[0]
            info = getattr(first, "generation_info", None) or {}
            usage = info.get("token_usage") or {}
        except Exception:
            pass
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    return int(prompt), int(completion)


class _BudgetCallback(BaseCallbackHandler):
    """Per-run budget guard for one ReAct fix loop.

    on_llm_start: set budget_exceeded when the shared ledger is exhausted.
    on_llm_end:  record this step's tokens into the ledger so the next
    on_llm_start check sees them (per-step accounting is what makes the
    in-loop guard meaningful).

    Exceptions raised in a callback are swallowed by LangChain, so we set a
    flag and let FixAgent.fix() raise BudgetExceededError after invoke()
    returns — the loop is bounded by recursion_limit=20 meanwhile.
    """

    def __init__(self, harness, model: str, category: str | None):
        self.harness = harness
        self.model = model
        self.category = category
        self.budget_exceeded = False

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs):
        if self.harness is not None and self.harness.over_budget():
            self.budget_exceeded = True

    def on_llm_end(self, response, **kwargs):
        if self.harness is None:
            return
        try:
            prompt_tokens, completion_tokens = _llm_usage(response)
            if prompt_tokens + completion_tokens > 0:
                self.harness.record_usage(
                    task_type="verify_fix",
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    category=self.category,
                )
        except Exception:
            pass


class FixAgent(BaseAgent):
    """Fixes TypeScript build errors with a self-verifying ReAct tool loop.

    The only true agent in the pipeline: an LLM-driven loop over
    read → write → tsc → iterate (decision space + hard feedback + iteration
    value). Single-shot fix is a degraded internal mode, not a separate skill.

    Contract:
        fix(file_path, errors, filename, target_dir,
            cross_file_context="", memo="") -> bool

        Writes the corrected file itself when a fix is produced; returns
        whether a fix was applied. BudgetExceededError propagates (the
        pipeline stops the verify phase) rather than degrading.
    """

    def __init__(self, config: Config, harness=None):
        super().__init__(config, harness)
        # Compiled ReAct graphs, cached per connection key so one pipeline
        # run reuses a compiled graph across every file (compiled graphs are
        # stateless and re-entrant).
        self._agent_cache: dict[str, object] = {}

    # =========================================================================
    # Public contract
    # =========================================================================

    def fix(
        self,
        file_path: Path,
        errors: str,
        filename: str,
        target_dir: Path,
        cross_file_context: str = "",
        memo: str = "",
    ) -> bool:
        """Fix a single file, ReAct first with single-shot degradation.

        Args:
            file_path: Path to the erroring file (written in place on success).
            errors: The file's structured error lines.
            filename: Target-relative name (src/screens/Foo.tsx) for prompts.
            target_dir: Project root — run_tsc_check / run_build_check need it.
            cross_file_context: Companion-file exports (already computed once
                by VerifyPhase).
            memo: Fix-memo memory block (already computed once by VerifyPhase).

        Returns:
            True if a fix was written, False otherwise. BudgetExceededError
            is raised (never degraded) when the token budget is exhausted.
        """
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return False

        # Fallback ①: no LLM → straight to single-shot (no ReAct possible).
        if self.llm is None:
            return self._fix_single_shot(
                file_path, source, errors, filename, cross_file_context, memo
            )

        # Pre-loop budget guard: the ReAct loop's internal calls bypass
        # Harness.call, so consult the shared ledger once up front. Raised
        # before the try so the single-shot fallback below isn't triggered
        # (it would fail identically).
        if self.harness is not None and self.harness.over_budget():
            raise BudgetExceededError(
                f"Token budget ({self.config.token_budget}) exhausted — "
                f"skipping ReAct fix for {filename}."
            )

        # Build the ReAct prompt once (source + errors + companion context + memo).
        prompt = get_fix_prompt(source[:_MAX_FIX_SOURCE_CHARS], errors, filename)
        if cross_file_context:
            prompt += f"\n\n## Companion File Context (exports from imported files)\n{cross_file_context}"
        if memo:
            prompt += f"\n\n{memo}"

        abs_path = str(file_path.resolve())
        abs_target = str(Path(target_dir).resolve())

        # Connection ladder: primary once, then fallback once (if configured).
        route = self.config.route_for("verify_fix")
        attempts = [route]
        if route.fallback_model:
            attempts.append(
                ModelRoute(
                    model=route.fallback_model,
                    base_url=route.fallback_base_url,
                    api_key=route.fallback_api_key,
                )
            )

        result = None
        for r in attempts:
            try:
                result = self._run_react(r, prompt, abs_path, abs_target, filename)
                break
            except BudgetExceededError:
                raise
            except Exception as exc:
                self.log_warn("Fix", f"ReAct fix failed for {filename} on {r.model}: {exc}")

        # Both attempts failed (or no fallback configured) → single-shot ②.
        if result is None:
            return self._fix_single_shot(
                file_path, source, errors, filename, cross_file_context, memo
            )

        # Success = the agent wrote at least one file via the write tool.
        if self._agent_wrote_file(result):
            self.log_info("Fix", f"ReAct fix applied to {filename}")
            return True

        # Fallback: extract a fenced code block from the final message.
        messages = result.get("messages", []) or []
        final_content = ""
        if messages:
            final_content = getattr(messages[-1], "content", "") or ""
        code = _extract_code_block(str(final_content))
        if code and len(code) >= 50:
            file_path.write_text(code, encoding="utf-8")
            self.log_info("Fix", f"ReAct fix applied to {filename} (code block)")
            return True

        # Fallback ③: single-shot harness fix (cheap last attempt).
        self.log_warn(
            "Fix",
            f"ReAct agent produced no write for {filename}; falling back to single-shot",
        )
        return self._fix_single_shot(
            file_path, source, errors, filename, cross_file_context, memo
        )

    # =========================================================================
    # ReAct segment
    # =========================================================================

    def _run_react(
        self,
        route: ModelRoute,
        prompt: str,
        abs_path: str,
        abs_target: str,
        filename: str,
    ) -> dict:
        """Run the compiled ReAct loop on one connection; returns final state.

        Raises BudgetExceededError if the budget was exhausted mid-loop.
        """
        # Compiled graphs are stateless and re-entrant — cache one per
        # connection key and reuse it for every file in the run.
        key = f"{route.base_url or ''}|{route.model}|{route.api_key or ''}"
        agent = self._agent_cache.get(key)
        if agent is None:
            agent = self.create_agent(
                tools=VERIFY_FIX_TOOLS,
                system_prompt=BUILD_FIX_SYSTEM,
                name="fix_agent",
                model=route.model,
                base_url=route.base_url,
                api_key=route.api_key,
            )
            self._agent_cache[key] = agent

        callback = _BudgetCallback(self.harness, route.model, infer_file_category(filename))
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            f"Fix the build errors in {filename}.\n\n{prompt}\n\n"
                            f"## Instructions\n"
                            f"1. Read the file: use read_source_file('{abs_path}')\n"
                            f"2. Write the corrected file: use write_output_file "
                            f"(output_path='{abs_path}')\n"
                            f"3. Verify: use run_tsc_check(target_dir='{abs_target}').\n"
                            f"   If node_modules are missing, first use "
                            f"run_build_check(target_dir='{abs_target}').\n"
                            f"4. If BUILD_ERRORS remain, read the file again and "
                            f"fix, then verify again.\n"
                            f"5. Stop when run_tsc_check returns BUILD_OK.\n"
                            f"Target directory: {abs_target}"
                        )
                    ),
                ]
            },
            config={"recursion_limit": 20, "callbacks": [callback]},
        )

        # The callback cannot raise mid-loop (LangChain swallows callback
        # exceptions), so check its flag after invoke() returns.
        if callback.budget_exceeded:
            raise BudgetExceededError(
                f"Token budget ({self.config.token_budget}) exceeded during ReAct "
                f"fix for {filename}."
            )
        return result

    # =========================================================================
    # Single-shot degraded mode
    # =========================================================================

    def _fix_single_shot(
        self,
        file_path: Path,
        source: str,
        errors: str,
        filename: str,
        cross_file_context: str = "",
        memo: str = "",
    ) -> bool:
        """Single-shot harness fix: complete corrected file in one call.

        No tool loop — works with any model, including reasoning-type models
        that lack function calling.
        """
        if not self.harness:
            return False

        prompt = get_hybrid_fix_prompt(
            source[:_MAX_FIX_SOURCE_CHARS],
            errors,
            filename,
            cross_file_context,
        )
        if memo:
            prompt += f"\n\n{memo}"

        try:
            result = self.harness.call(
                task_type="verify_fix",
                system_prompt=HYBRID_FIX_SYSTEM,
                user_message=prompt,
                temperature=0.2,
                category=infer_file_category(filename),
            )
        except Exception as exc:
            self.log_warn("Fix", f"Fix call failed for {filename}: {exc}")
            return False

        code = _extract_code_block(result.content)
        if not code or len(code) < 50:
            self.log_warn("Fix", f"No valid fix produced for {filename}")
            return False

        file_path.write_text(code, encoding="utf-8")
        self.log_info("Fix", f"Applied hybrid fix to {filename}")
        return True

    # =========================================================================
    # ReAct result inspection
    # =========================================================================

    @staticmethod
    def _agent_wrote_file(result: dict) -> bool:
        """True if the ReAct agent called write_output_file at least once."""
        for msg in result.get("messages", []) or []:
            for tc in getattr(msg, "tool_calls", None) or []:
                if isinstance(tc, dict) and tc.get("name") == "write_output_file":
                    return True
            # Older serializations keep tool calls under additional_kwargs
            ak = getattr(msg, "additional_kwargs", None) or {}
            for tc in ak.get("tool_calls", []) or []:
                if (
                    isinstance(tc, dict)
                    and tc.get("function", {}).get("name") == "write_output_file"
                ):
                    return True
        return False
