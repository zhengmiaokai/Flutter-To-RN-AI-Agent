"""agents/convert_agent — Convert Flutter source files to React Native (optimized).

Uses single-shot LLM calls instead of ReAct agents — the source code is already
read before the call, so the tool-calling loop adds only token cost and latency
without benefit. Per-category system prompts avoid sending irrelevant mapping
tables (e.g. models don't need widget or navigation mappings).

Estimated token reduction: ~50-60% vs the previous ReAct agent approach.
"""

from __future__ import annotations

import re
from pathlib import Path

from framework.config import Config
from framework.llm import LLMClient
from framework.state import StateManager
from agents.base import BaseAgent
from prompts import build_category_system_prompt, get_conversion_prompt

# Registry: dart filename → output info
FileRegistry = dict[str, dict[str, str]]


def _contains_jsx(code: str) -> bool:
    """Check if code contains JSX (self-closing or paired opening tags).

    Heuristic: a '<' followed by an ASCII identifier or known JSX built-in,
    then either '/>' or '>'.  Avoids false positives on generics (e.g. Array<Foo>)
    by requiring whitespace after the tag name before '>', and excludes
    known-non-JSX patterns like React.createElement.
    """
    # Fast path — React.createElement means no JSX
    if "React.createElement" in code:
        return False

    return bool(
        re.search(
            r"<([A-Z][a-zA-Z0-9_.]*(?:\.[A-Z][a-zA-Z0-9_.]*)?)\b(?:\s[^>]*)?/>",  # <Foo /> or <Foo.Bar />
            code,
        )
        or re.search(
            r"<([A-Z][a-zA-Z0-9_.]*(?:\.[A-Z][a-zA-Z0-9_.]*)?)\b(?:\s[^>]*)?>",  # <Foo> or <Foo.Bar>
            code,
        )
        or re.search(
            r"<([a-z][a-zA-Z0-9._]*-[a-zA-Z0-9._-]+)\b(?:\s[^>]*)?[/>]",  # <custom-element>
            code,
        )
    )


def build_file_registry(
    file_groups: dict[str, list[Path]],
    target_dir: str,
    category_map: dict[str, tuple[str, str]],
) -> FileRegistry:
    """Build a registry of all Dart files and their target output paths."""
    registry: FileRegistry = {}
    for cat, files in file_groups.items():
        subdir, ext = category_map.get(cat, ("src/other", ".ts"))
        for fp in files:
            if fp.suffix.lower() != ".dart":
                continue
            output_name = fp.stem + ext
            output_path = Path(target_dir) / subdir / output_name
            registry[fp.name] = {
                "category": cat,
                "output": str(output_path),
            }
    return registry


def find_companion_context(
    src_name: str,
    registry: FileRegistry,
    max_entries: int = 10,
    source_code: str | None = None,
) -> list[dict[str, str]]:
    """Find companion files relevant to a given source file.

    Two matching strategies:
    1. Same-name-prefix matching (e.g. LoginMainView → LoginMainModel)
    2. Import-based matching: if source_code is provided, parse its Dart
       import statements and look up each referenced module in the registry.

    Returns a list of {name, category, output} dicts, capped at max_entries.
    """
    stem = Path(src_name).stem.lower()

    # Strip trailing "View", "Page", "Screen" to find base prefix
    for suffix in ("view", "page", "screen"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    companions: list[dict[str, str]] = []
    seen: set[str] = set()

    for fname, info in registry.items():
        if fname == src_name:
            continue
        fstem = Path(fname).stem.lower()

        # Same prefix → strong match (e.g. LoginMainView ↔ LoginMainModel)
        if fstem.startswith(stem) or stem.startswith(fstem):
            if fname not in seen:
                companions.append({"name": fname, **info})
                seen.add(fname)

    # Strategy 2: match by Dart imports
    if source_code and len(companions) < max_entries:
        imported_names = _parse_dart_imports(source_code)
        for fname, info in registry.items():
            if fname in seen:
                continue
            fstem = Path(fname).stem.lower()
            # Match imported module name (without .dart extension) against registry filename
            for imp_name in imported_names:
                imp_stem = Path(imp_name).stem.lower()
                if imp_stem == fstem or imp_stem == fname.lower():
                    companions.append({"name": fname, **info})
                    seen.add(fname)
                    break
            if len(companions) >= max_entries:
                break

    return companions[:max_entries]


def _parse_dart_imports(source_code: str) -> list[str]:
    """Parse Dart import/export statements and return referenced module names.

    Handles:
      import 'package:foo/bar.dart';
      import './relative/path.dart';
      export 'package:foo/bar.dart';
    """
    imports: list[str] = []
    for m in re.finditer(
        r"(?:import|export)\s+['\"](?:package:[\w_.]+/)?([\w_./]+\.dart)['\"]",
        source_code,
    ):
        imports.append(m.group(1))
    return imports


def build_context_prompt(companions: list[dict[str, str]]) -> str:
    """Build a compact context snippet for the conversion prompt."""
    if not companions:
        return ""
    lines = [
        "## Companion files already in the project (import these, do NOT redefine their types):",
    ]
    for c in companions:
        lines.append(f"- {c['name']} → {c['output']}  (category: {c['category']})")
    return "\n".join(lines)


# ── Category mapping ─────────────────────────────────────────────────────

CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "screens": ("src/screens", ".tsx"),
    "widgets": ("src/components", ".tsx"),
    "services": ("src/services", ".ts"),
    "models": ("src/models", ".ts"),
    "providers": ("src/providers", ".tsx"),
    "utils": ("src/utils", ".ts"),
}


class ConvertAgent(BaseAgent):
    """Agent that converts Flutter files into React Native modules.

    Optimized for token efficiency — uses a single LLM call per file with
    a category-specific system prompt (no ReAct tool-calling overhead).
    The source code is embedded directly in the prompt; the LLM returns
    converted code in a ```tsx/ts code block which we extract and write.
    """

    def __init__(self, config: Config, llm: LLMClient, state: StateManager):
        super().__init__(config, llm)
        self._state = state
        self._file_registry: FileRegistry = {}

    def set_file_registry(self, registry: FileRegistry):
        """Set the project-wide file registry for context-aware conversion."""
        self._file_registry = registry

    # ---- Quick single-file conversion (used by pipeline) -------------------

    def convert_file(self, category: str, src_path: Path, reflection_feedback: str | None = None):
        """Convert a single file using a single LLM call (no ReAct loop).

        Args:
            category: File category (screens, widgets, etc.)
            src_path: Path to the source Dart file.
            reflection_feedback: Optional feedback from reflection step —
                specific issues to fix in a re-conversion pass.
        """
        mapping = CATEGORY_MAP.get(category)
        if mapping is None:
            raise ValueError(f"Unknown category: {category}")
        subdir, ext = mapping
        self._convert_single_shot(src_path, category, subdir, ext, reflection_feedback)

    # ---- Single-shot conversion (replaces ReAct agent) --------------------

    def _convert_single_shot(self, src_path: Path, category: str, subdir: str, ext: str,
                              reflection_feedback: str | None = None):
        """Convert a file in a single LLM call (replaces ReAct agent loop).

        Why single-shot instead of ReAct agent:
        - We already read the source code before the call — the read_source_file
          tool is redundant and adds an extra LLM turn.
        - Writing output is a local file operation — it doesn't need a tool call.
        - A single call eliminates the ~2x system prompt overhead and cuts
          latency by ~40-60%.

        The per-category system prompt (~1K-3.5K tokens depending on category)
        replaces the full 4K-token prompt used previously.

        Args:
            src_path: Path to source .dart file.
            category: File category (screens, widgets, etc.).
            subdir: Target subdirectory under target_dir.
            ext: Target file extension (.ts or .tsx).
            reflection_feedback: Optional specific issues to fix from
                the reflection step. When provided, the LLM is instructed
                to address each issue in the re-conversion.
        """
        source_code = src_path.read_text(encoding="utf-8")
        prompt = get_conversion_prompt(source_code, src_path.name)

        # Build compact companion context
        companion_context = ""
        if self._file_registry:
            companions = find_companion_context(src_path.name, self._file_registry, source_code=source_code)
            if companions:
                companion_context = build_context_prompt(companions)

        # Category-specific system prompt (core + relevant sections only)
        system_prompt = build_category_system_prompt(category)

        output_name = src_path.stem + ext
        output_path = Path(self.config.target_dir) / subdir / output_name

        # Build user message
        user_content = (
            f"Convert this {category} file: {src_path.name}\n\n"
            f"{prompt}\n\n"
        )
        if companion_context:
            user_content += (
                f"{companion_context}\n\n"
                f"IMPORTANT: Use imports from the companion files above instead of "
                f"redefining types, models, view models, or state classes inline. "
                f"Their output paths show where they will be located — use relative "
                f"imports from your location ({subdir}/{output_name}).\n\n"
            )

        # Inject reflection feedback when re-converting (guides the LLM to fix
        # specific issues found during quality review, rather than re-generating
        # the same flawed output)
        if reflection_feedback:
            user_content += (
                f"{reflection_feedback}\n\n"
                f"IMPORTANT: The issues listed above are from a quality review of your "
                f"previous attempt. Address EVERY issue. Do NOT repeat the same mistakes.\n\n"
            )

        user_content += (
            "Output the converted code in a single ```tsx or ```typescript code block.\n"
            "No explanations, no markdown outside the code block."
        )

        # Single LLM call — no ReAct agent overhead
        response = self.llm.chat(
            system_prompt=system_prompt,
            user_message=user_content,
        )

        # Extract code block and write directly
        match = re.search(
            r"```(?:tsx|typescript|ts|jsx|javascript|js)\n(.*?)```",
            response,
            re.DOTALL,
        )
        if match:
            code = match.group(1).strip()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Auto-upgrade .ts → .tsx if the output contains JSX but has the wrong extension.
            # TypeScript can't parse <Foo /> inside a .ts file (it sees comparison operators).
            if ext == ".ts" and _contains_jsx(code):
                tsx_path = output_path.with_suffix(".tsx")
                tsx_path.write_text(code, encoding="utf-8")
                self.log_info("Convert", f"{output_path.name} contains JSX, saved as {tsx_path.name}")
            else:
                output_path.write_text(code, encoding="utf-8")
        else:
            self.log_warn("Convert", f"LLM returned text instead of code for {src_path.name}")

