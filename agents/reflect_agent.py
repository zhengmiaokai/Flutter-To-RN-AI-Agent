"""agents/reflect_agent — Self-correction for conversion quality review.

Reviews conversion quality using an LLM call with a Pydantic
output schema. Compares original Flutter against converted React Native
and identifies gaps.

Uses a two-tier approach:
1. Try LangChain's with_structured_output() (requires tool-calling support)
2. Fall back to plain chat + JSON parsing when structured output is unavailable

"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import HumanMessage, SystemMessage

from framework.config import Config
from framework.llm import LLMClient
from agents.base import BaseAgent

_REFLECT_SYSTEM = """You are an expert code reviewer specializing in Flutter to React Native migrations.

Your task is to compare a CONVERTED React Native file against the ORIGINAL Flutter source and identify quality issues. Be precise — flag real issues but don't invent problems that don't exist.

## Check 8 dimensions

1. **Missing widgets** — any Flutter widget not mapped to a React Native equivalent (e.g., Container→View, ListView→FlatList, Stack→absolute position View)
2. **Missing props** — Flutter widget props not carried over to RN components (e.g., padding, alignment, onPressed not mapped)
3. **State management gaps** — Provider/ChangeNotifier/Bloc not converted to React Context/hooks; setState missing; useEffect deps wrong
4. **Layout issues** — Column/Row/Stack/Expanded not correctly mapped to flexbox; mainAxisAlignment/crossAxisAlignment lost
5. **Style issues** — BoxDecoration/EdgeInsets/TextStyle not converted to StyleSheet; Colors not mapped to hex/rgba; MediaQuery not converted to useWindowDimensions
6. **Import issues** — lingering Dart/Flutter imports, missing react-native imports, wrong relative paths to companion files
7. **Navigation issues** — Navigator.push/pop/replace not converted to React Navigation
8. **Lifecycle & typing issues** — initState/dispose not mapped to useEffect; props typed as `any` instead of proper interface; missing TypeScript types

## How to score

Start from 100 and deduct ONLY for real issues:
- -3 per missing widget or wrong widget mapping
- -3 per missing prop
- -2 per layout or style mapping issue
- -5 per state management gap
- -2 per lint/import issue
- -2 per `any` type that should be specific
- -10 if the file would not compile (broken imports, syntax errors)

Be conservative — if you're not sure whether something is an issue, don't flag it.

## Scoring guide
- 90-100: Good to excellent conversion, all details preserved (passes)
- 75-89: Minor issues that don't break functionality (passes)
- 60-74: Notable gaps that need improvement (needs rework)
- Below 60: Significant missing functionality or broken conversion (must rework)

## Important
- A conversion can be good even if it chooses different but equivalent patterns (e.g., inline styles vs StyleSheet, functional components vs class). Prefer pragmatic equivalence over literal 1:1 mapping.
- Missing onDoubleTap or onLongPress is a minor issue (max -3), not a critical failure.
- Using Platform.OS checks instead of conditional imports is acceptable.
- Default exports are fine.
- Score related to truly unmappable patterns (e.g., Flutter's const in widget tree) should not be deducted.

Output a JSON object:
{
  "pass": true/false,
  "score": 0-100,
  "issues": [
    {
      "severity": "critical|warning|info",
      "category": "missing_widget|state_management_gap|layout_issue|style_issue|import_issue|navigation_issue|lifecycle_issue|typing_issue",
      "description": "human-readable issue description",
      "suggestion": "how to fix"
    }
  ],
  "summary": "one-line summary of findings"
}

Output ONLY the JSON object, no explanations, no markdown formatting."""


class ReflectResult(BaseModel):
    """Structured result from a reflection pass."""

    pass_: bool = Field(
        alias="pass",
        default=True,
        description="Whether the conversion passes quality check",
    )
    score: int = Field(
        default=100, ge=0, le=100,
        description="Quality score 0-100, lower means more issues",
    )
    issues: list[dict] = Field(
        default_factory=list,
        description="List of issues found during review",
    )
    summary: str = Field(
        default="",
        description="One-line summary of findings",
    )

    model_config = ConfigDict(populate_by_name=True)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.get("severity") == "critical")

    def needs_rework(self) -> bool:
        """Return True if re-conversion is needed (score < 90 or any critical)."""
        return not self.pass_ or self.score < 90 or self.critical_count > 0


_MAX_CODE_CHARS = 16000


def _extract_json(text: str) -> str | None:
    """Extract a JSON object from LLM response text.

    Tries (in order):
    1. ```json ... ``` code block
    2. ``` ... ``` code block (assuming it's JSON)
    3. Raw JSON object via regex
    4. Trimmed text as-is (if it looks like JSON)
    """
    # Pattern 1: ```json ... ```
    m = re.search(r"```json\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Pattern 2: ``` ... ```
    m = re.search(r"```\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("{"):
            return candidate

    # Pattern 3: raw {...} block (handles streaming without fences)
    m = re.search(r"(\{.*\"score\".*\})", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Pattern 4: trimmed text if it starts with {
    text = text.strip()
    if text.startswith("{"):
        return text

    return None


class ReflectAgent(BaseAgent):
    """Agent that reviews conversion output quality and triggers rework.

    Uses a two-tier approach:
    1. Try LangChain's with_structured_output() (tool-calling path).
    2. Fall back to plain chat + JSON parsing when structured output is
       unavailable (e.g., models that don't support tool calling).

    """

    def __init__(self, config: Config, llm: LLMClient):
        super().__init__(config, llm)

    def reflect(
        self,
        rn_code: str,
        flutter_source: str,
        filename: str,
    ) -> ReflectResult:
        """Review a single file's conversion quality using a structured LLM call.

        Two-tier approach:
        - Tier 1: LangChain's with_structured_output() (fast, schema-enforced).
        - Tier 2: Plain chat + JSON parsing (works with any model).

        Args:
            rn_code: The converted React Native code.
            flutter_source: The original Flutter Dart source code.
            filename: Original file name.

        Returns:
            ReflectResult with pass/fail, score, and issue list.
        """
        if not self.llm:
            return ReflectResult(
                pass_=False, score=50,
                summary=f"Reviewed {filename} (no LLM)",
            )

        # Build the reflection message content
        msg_content = (
            f"Review the following Flutter-to-RN conversion for '{filename}':\n\n"
            f"## Original Flutter Source\n"
            f"```\n{flutter_source[:_MAX_CODE_CHARS]}\n```\n\n"
            f"## Converted React Native Code\n"
            f"```typescript\n{rn_code[:_MAX_CODE_CHARS]}\n```\n\n"
        )

        msg_content += "Output the quality report now."

        result: ReflectResult | None = None

        # ── Tier 1: Plain chat + JSON parsing ───────────────────────────
        # Note: Structured output via tool calling is intentionally skipped.
        # The API provider may run in "thinking mode" which is incompatible with
        # function calling / tool_choice. Plain chat + JSON extraction is the
        # most compatible approach across all OpenAI-compatible backends.
        try:
            json_prompt = msg_content + (
                "\n\nOutput your quality report as a raw JSON object "
                "(no markdown, no code fences)."
            )
            response = self.llm.chat(_REFLECT_SYSTEM, json_prompt)
            json_str = _extract_json(response)
            if json_str:
                data = json.loads(json_str)
                # Normalize issues: the LLM might return strings instead of dicts
                raw_issues = data.get("issues", [])
                if raw_issues and isinstance(raw_issues[0], str):
                    issues = [
                        {"severity": "warning", "category": "general", "description": i, "suggestion": ""}
                        for i in raw_issues
                    ]
                else:
                    issues = raw_issues
                result = ReflectResult(
                    pass_=data.get("pass", False),
                    score=data.get("score", 50),
                    issues=issues,
                    summary=data.get("summary", ""),
                )
        except Exception as exc:
            self.log_warn("Reflect", f"JSON fallback also failed for {filename}: {exc}")

        # Fallback: no result obtained
        if result is None:
            self.log_warn("Reflect", f"All reflection methods failed for {filename}")
            result = ReflectResult(
                pass_=False, score=50,
                summary="Reflection skipped due to error.",
            )

        return result

    def should_retry(self, result: ReflectResult, attempt: int, max_retries: int = 2) -> bool:
        """Decide whether to trigger re-conversion based on reflection result."""
        if attempt >= max_retries:
            self.log_warn("Reflect", f"Max retries ({max_retries}) reached. Accepting current output.")
            return False

        if not result.needs_rework():
            self.log_success("Reflect", f"Quality OK (score: {result.score})")
            return False

        issue_detail = "; ".join(
            i.get("description", "")[:80] for i in result.issues[:3]
        )
        self.log_warn(
            "Reflect",
            f"Score {result.score} < 90 ({len(result.issues)} issues, "
            f"{result.critical_count} critical). {issue_detail}",
        )

        return True
