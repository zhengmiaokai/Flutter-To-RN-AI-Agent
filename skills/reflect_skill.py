"""skills/reflect_skill — self-correction for conversion quality review.

Single-shot capability (no agent loop): reviews conversion quality via a
harness LLM call with JSON output. Compares original Flutter against
converted React Native and identifies gaps.

Optimizations over the original single-call path:
- json_object response format (fallback to plain JSON parsing when the
  provider rejects it)
- adaptive truncation: each side capped at 8K chars instead of 16K
- reflect_batch(): several files reviewed in one call to amortize the system
  prompt, with per-file fallback on parse failure
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ConfigDict

from framework.config import Config
from skills.base import BaseSkill

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

# Batch-mode override appended to the system prompt. Later instructions win.
_BATCH_SUFFIX = """
## MULTI-FILE MODE

You are reviewing MULTIPLE conversions in one call. Each file is presented as:

### FILE <index>: <filename>
## Original Flutter Source
```
...
```
## Converted React Native Code
```typescript
...
```

For EACH file, apply the 8-dimension review above. Output ONE JSON object
mapping each filename to its report:
{
  "<filename1>": {"pass": true/false, "score": 0-100, "issues": [...], "summary": "..."},
  "<filename2>": {...}
}
Use the exact filenames provided. Output ONLY the JSON object, no markdown."""

# Adaptive truncation — each side capped at 8K chars (16K previously).
_MAX_CODE_CHARS = 8000
_BATCH_SIZE = 10


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


def _normalize_issues(raw_issues: list) -> list[dict]:
    """Normalize issues the LLM might return as strings instead of dicts."""
    if not raw_issues:
        return []
    if isinstance(raw_issues[0], str):
        return [
            {"severity": "warning", "category": "general", "description": i, "suggestion": ""}
            for i in raw_issues
        ]
    return raw_issues


class ReflectSkill(BaseSkill):
    """Skill that reviews conversion output quality and triggers rework.

    Contract: ``reflect(rn_code, flutter_source, filename) -> ReflectResult``
    and ``reflect_batch(items) -> dict[key, ReflectResult]`` (single-shot,
    batched LLM calls with per-file fallback on parse failure).
    """

    name = "reflect"
    description = (
        "Review a Flutter→RN conversion's quality against the original source "
        "(8-dimension check, 0-100 score) via a single-shot LLM call; supports "
        "batched review of multiple files in one call."
    )

    def __init__(self, config: Config, harness=None):
        super().__init__(config, harness)

    # ---- single-file reflection --------------------------------------------

    def reflect(
        self,
        rn_code: str,
        flutter_source: str,
        filename: str,
    ) -> ReflectResult:
        """Review a single file's conversion quality using a harness call."""
        if not self.harness:
            return ReflectResult(
                pass_=False, score=50,
                summary=f"Reviewed {filename} (no LLM)",
            )

        json_prompt = self._build_message(rn_code, flutter_source, filename) + (
            "\n\nOutput your quality report as a raw JSON object "
            "(no markdown, no code fences)."
        )

        try:
            result = self.harness.call(
                task_type="reflect",
                system_prompt=_REFLECT_SYSTEM,
                user_message=json_prompt,
                temperature=0.0,
                response_format="json_object",
                cache=True,
            )
            parsed = self._parse_response(result.content, filename)
            if parsed is not None:
                return parsed
            self.log_warn("Reflect", f"Unparseable response for {filename}")
        except Exception as exc:
            self.log_warn("Reflect", f"Reflection failed for {filename}: {exc}")

        return ReflectResult(
            pass_=False, score=50,
            summary="Reflection skipped due to error.",
        )

    # ---- batched reflection (amortizes system prompt across files) ---------

    def reflect_batch(
        self,
        items: list[tuple],
    ) -> dict[str, ReflectResult]:
        """Review multiple files in one batched LLM call.

        Args:
            items: list of (key, rn_code, flutter_source, filename) tuples.

        Returns:
            {key: ReflectResult}. Files that fail batch parsing are reviewed
            individually as a fallback, so every input file gets a result.
        """
        if not self.harness or not items:
            return {}

        results: dict[str, ReflectResult] = {}
        remaining = list(items)
        batches = [remaining[i:i + _BATCH_SIZE] for i in range(0, len(remaining), _BATCH_SIZE)]

        for batch in batches:
            parts = ["Review the following conversions:\n"]
            for i, (key, rn_code, flutter_source, filename) in enumerate(batch, 1):
                parts.append(
                    f"### FILE {i}: {filename}\n"
                    f"## Original Flutter Source\n```\n{flutter_source[:_MAX_CODE_CHARS]}\n```\n\n"
                    f"## Converted React Native Code\n"
                    f"```typescript\n{rn_code[:_MAX_CODE_CHARS]}\n```\n"
                )
            user_message = "\n".join(parts)

            try:
                result = self.harness.call(
                    task_type="reflect",
                    system_prompt=_REFLECT_SYSTEM + "\n\n" + _BATCH_SUFFIX,
                    user_message=user_message,
                    temperature=0.0,
                    response_format="json_object",
                    cache=True,
                )
            except Exception as exc:
                self.log_warn("Reflect", f"Batch reflect failed: {exc}")
                result = None

            parsed_map: dict[str, ReflectResult] = {}
            if result is not None:
                parsed_map = self._parse_batch(result.content)
                if not parsed_map:
                    self.log_warn("Reflect", "Batch reflect produced no parseable reports")

            # Route: parsed keys → batch results; unparsed keys → individual fallback
            fallback = []
            for key, rn_code, flutter_source, filename in batch:
                if filename in parsed_map:
                    results[key] = parsed_map[filename]
                else:
                    fallback.append((key, rn_code, flutter_source, filename))
            for key, rn_code, flutter_source, filename in fallback:
                results[key] = self.reflect(rn_code, flutter_source, filename)

        return results

    # ---- prompt / parse helpers --------------------------------------------

    @staticmethod
    def _build_message(rn_code: str, flutter_source: str, filename: str) -> str:
        return (
            f"Review the following Flutter-to-RN conversion for '{filename}':\n\n"
            f"## Original Flutter Source\n"
            f"```\n{flutter_source[:_MAX_CODE_CHARS]}\n```\n\n"
            f"## Converted React Native Code\n"
            f"```typescript\n{rn_code[:_MAX_CODE_CHARS]}\n```\n\n"
            "Output the quality report now."
        )

    def _parse_response(self, text: str, filename: str) -> ReflectResult | None:
        """Parse a single-file reflection response into a ReflectResult."""
        json_str = _extract_json(text)
        if not json_str:
            return None
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return ReflectResult(
            pass_=data.get("pass", False),
            score=data.get("score", 50),
            issues=_normalize_issues(data.get("issues", [])),
            summary=data.get("summary", ""),
        )

    def _parse_batch(self, text: str) -> dict[str, ReflectResult]:
        """Parse a batch response into {filename: ReflectResult}."""
        json_str = _extract_json(text)
        if not json_str:
            return {}
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, ReflectResult] = {}
        for filename, report in data.items():
            if not isinstance(report, dict):
                continue
            try:
                out[filename] = ReflectResult(
                    pass_=report.get("pass", False),
                    score=report.get("score", 50),
                    issues=_normalize_issues(report.get("issues", [])),
                    summary=report.get("summary", ""),
                )
            except Exception:
                continue
        return out

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
