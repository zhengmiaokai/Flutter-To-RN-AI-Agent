"""agents/scan_agent — Hybrid file scanner (rule-based + AI enhancement).

Two-phase approach:
1. Fast rule-based pass (directory heuristics) — unchanged from original.
2. Optional AI pass that batch-classifies uncertain files by analyzing actual
   source content, catching files in non-standard directory structures.

Three scan modes:
- ``fast``  — rule-based only, zero AI cost (original behavior)
- ``smart`` — AI reclassifies Dart files that rules marked as "other" or
              ambiguous root-level "utils" (balanced cost/accuracy)
- ``deep``  — AI reclassifies ALL Dart files for maximum accuracy

Files are sent to the LLM in batches (up to 25 per call) so the system prompt
is amortized across many files. Each file preview is limited to ~20 lines
(~500-800 chars) to keep token usage low.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from framework.config import Config
from framework.llm import LLMClient
from tools import scan_source_directory
from prompts.scanner import BATCH_CLASSIFY_SYSTEM, build_batch_prompt

# ── Valid categories ───────────────────────────────────────────────────────

CATEGORIES = [
    "screens", "widgets", "services", "models",
    "providers", "utils", "assets", "config", "other",
]

# Dart-file categories that CAN accept new files during reclassification
_DART_CATEGORIES = {"screens", "widgets", "services", "models", "providers", "utils"}

# Content preview limit (lines)
_MAX_PREVIEW_LINES = 20

# Batch size for AI classification calls
_BATCH_SIZE = 50


class ScanAgent:
    """Scans a Flutter project directory and classifies files by category.

    Two-phase classification:
    1. Rule-based pass via ``classify_file`` tool (directory heuristics).
    2. Optional AI batch pass that reclassifies uncertain files by content.

    Pass ``scan_mode="fast"`` to skip the AI pass entirely.
    """

    def __init__(
        self,
        config: Config,
        llm: LLMClient | None = None,
        scan_mode: str | None = None,
    ):
        self.config = config
        self.llm = llm
        self.scan_mode = scan_mode or config.scan_mode
        self.console = Console()

    # ---- public API ---------------------------------------------------------

    def scan(self) -> dict[str, list[Path]]:
        """Scan source directory and classify files.

        1. Rule-based pass (directory heuristics).
        2. AI batch enhancement pass if llm is available and mode != "fast".

        Returns:
            { "screens": [Path(...)], "widgets": [...], ... }
        """
        self._log_info("ScanAgent", f"Starting scan (mode={self.scan_mode})...")

        result_json = scan_source_directory.invoke({"source_dir": self.config.source_dir})
        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError:
            self._log_error("ScanAgent", "Failed to parse scan result")
            return {}

        # Convert file path strings back to Path objects
        groups: dict[str, list[Path]] = {c: [] for c in CATEGORIES}
        for cat in list(groups.keys()):
            for fp_str in parsed.get(cat, []):
                groups[cat].append(Path(fp_str))

        # ── Phase 2: AI enhancement ──────────────────────────────────────
        if self.scan_mode != "fast" and self.llm is not None:
            moved = self._enhance_with_ai(groups)
            if moved:
                self._log_info("ScanAgent", f"AI reclassified {moved} file(s)")
        else:
            self._log_info("ScanAgent", "Enhancement skipped")

        self._print_summary(groups)
        return groups

    # ---- internal: AI enhancement --------------------------------------------

    def _enhance_with_ai(self, groups: dict[str, list[Path]]) -> int:
        """Reclassify uncertain Dart files using batched AI calls.

        In ``smart`` mode: only files in "other" + root-level "utils".
        In ``deep`` mode: ALL Dart files across all categories.

        Files are grouped into batches of 25 and sent in a single API call
        per batch. Returns the number of files reclassified.
        """
        candidates: list[Path] = []

        if self.scan_mode == "deep":
            for cat in _DART_CATEGORIES | {"other"}:
                for fp in groups.get(cat, []):
                    if fp.suffix.lower() == ".dart" and fp not in candidates:
                        candidates.append(fp)
        else:
            # "smart" mode: reclassify "other" + root-level "utils" dart files
            for fp in groups.get("other", []):
                if fp.suffix.lower() == ".dart":
                    candidates.append(fp)
            for fp in groups.get("utils", []):
                if fp.suffix.lower() == ".dart" and not self._has_deep_util_path(fp):
                    candidates.append(fp)

        if not candidates:
            return 0

        # Build current-category lookup
        current_cats: dict[str, str] = {}
        for cat, file_list in groups.items():
            for fp in file_list:
                current_cats[str(fp)] = cat

        mover = 0
        batches = [candidates[i:i + _BATCH_SIZE] for i in range(0, len(candidates), _BATCH_SIZE)]

        for batch in batches:
            results = self._batch_classify(batch, current_cats)
            if not results:
                continue

            for fp in batch:
                new_cat = results.get(str(fp))
                if new_cat and new_cat != current_cats.get(str(fp)):
                    self._move_file(groups, fp, new_cat)
                    mover += 1

        return mover

    def _batch_classify(self, files: list[Path], current_cats: dict[str, str]) -> dict[str, str] | None:
        """Classify a batch of files in a single AI call.

        Args:
            files: File paths to classify.
            current_cats: Map of str(fp) → current category name.

        Returns a dict mapping full file path → category, or None on failure.
        """
        previews: list[tuple[str, str, str, str]] = []
        for fp in files:
            preview = self._read_preview(fp)
            cur = current_cats.get(str(fp), "other")
            previews.append((fp.name, str(fp), cur, preview))

        prompt = build_batch_prompt(previews)
        self._log_dim(f"  →  batch[{len(files)}]", f"{files[0].name} (+{len(files)-1} more)")

        try:
            response = self.llm.chat(
                system_prompt=BATCH_CLASSIFY_SYSTEM,
                user_message=prompt,
                temperature=0.0,
            )
            raw = response.strip()
        except Exception as exc:
            self._log_warn("  classify-err", str(exc)[:120])
            return None

        parsed = self._parse_json_response(raw)
        if parsed is None:
            self._log_warn("  classify-unk", f"unexpected response: {raw[:150]}...")
            return None

        # Build full-path keyed lookup with fallback matching
        validated: dict[str, str] = {}
        fp_map = {str(fp): fp for fp in files}  # full path → file
        for key, cat in parsed.items():
            cat_clean = cat.strip().lower()
            if cat_clean not in CATEGORIES:
                self._log_dim(f"  skip  {key}", f"unknown category: {cat_clean}")
                continue

            key_str = str(key).strip()

            # Try exact full-path match first
            if key_str in fp_map:
                validated[key_str] = cat_clean
                continue

            # Fallback: match by filename (key is just "filename.dart")
            for full_path, fp in fp_map.items():
                if key_str == fp.name or full_path.endswith(key_str):
                    validated[full_path] = cat_clean
                    break
            else:
                self._log_dim(f"  skip  {key}", "no matching file in this batch")

        return validated

    # ---- internal: content extraction ---------------------------------------

    @staticmethod
    def _read_preview(fp: Path, max_lines: int = _MAX_PREVIEW_LINES) -> str:
        """Read first N lines of a Dart file for classification."""
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            return "\n".join(lines[:max_lines])
        except Exception:
            return ""

    # ---- internal: helpers --------------------------------------------------

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, str] | None:
        """Extract a JSON object from the AI response, handling ``` fences."""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            # Find the first { and last }
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end + 1]
            else:
                return None

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return None

        if not isinstance(result, dict):
            return None
        return result

    @staticmethod
    def _has_deep_util_path(fp: Path) -> bool:
        """True if the file sits in a named 'utils' or 'helpers' directory.

        Files deep inside an actual utils/ directory are likely true utils.
        Root-level ambiguous dart files get checked by AI.
        """
        parts = [p.lower() for p in fp.parts]
        return any(p in {"utils", "helpers", "tools"} for p in parts[:-1])

    @staticmethod
    def _move_file(groups: dict[str, list[Path]], fp: Path, target_cat: str):
        """Move a file from its current category to target_cat."""
        for cat in list(groups.keys()):
            if fp in groups[cat]:
                groups[cat].remove(fp)
                break
        if target_cat in groups:
            groups[target_cat].append(fp)

    # ---- static helpers (unchanged) -----------------------------------------

    @staticmethod
    def get_file_count(groups: dict[str, list[Path]]) -> int:
        return sum(len(files) for files in groups.values())

    @staticmethod
    def get_dart_files(groups: dict[str, list[Path]]) -> list[Path]:
        files = []
        for category in ["screens", "widgets", "services", "models", "providers", "utils"]:
            for f in groups.get(category, []):
                if f.suffix.lower() in {".dart"}:
                    files.append(f)
        for f in groups.get("other", []):
            if f.suffix.lower() in {".dart"}:
                files.append(f)
        return files

    def print_scan_summary(self, groups: dict[str, list[Path]]):
        self._print_summary(groups)

    # ---- internal helpers ---------------------------------------------------

    def _print_summary(self, groups: dict[str, list[Path]]):
        for category, files in groups.items():
            if files:
                self._log_info("ScanAgent", f"  [{category}] {len(files)} file(s)")
        total = self.get_file_count(groups)
        self._log_info("ScanAgent", f"  Total: {total} file(s) found")

    def _log_info(self, tag: str, message: str):
        self.console.print(f"[cyan][{tag}][/cyan] {message}")

    def _log_dim(self, tag: str, message: str):
        self.console.print(f"[dim][{tag}][/dim] {message}")

    def _log_warn(self, tag: str, message: str):
        self.console.print(f"[yellow][{tag}][/yellow] {message}")

    def _log_error(self, tag: str, message: str):
        self.console.print(f"[red][{tag}][/red] {message}")
