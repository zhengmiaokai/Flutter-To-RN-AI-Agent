"""agents/verify_agent — Build verification with LangGraph ReAct agents.

Verifies the generated React Native project builds correctly using a
LangGraph ReAct agent bound to build-check and auto-fix tools.

Key LangChain/LangGraph features:
- create_react_agent with run_build_check tool
- ReAct tool calling loop for build → parse errors → fix → recheck
- @tool-decorated utility functions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage

from framework.config import Config
from framework.llm import LLMClient
from agents.base import BaseAgent
from tools import (
    read_source_file,
    write_output_file,
    run_build_check,
    run_tsc_check,
)
from prompts.verify import BUILD_FIX_SYSTEM, get_fix_prompt


# =============================================================================
# Structured tsc error types
# =============================================================================


@dataclass
class TscError:
    """A single parsed tsc error."""

    file: str
    line: int
    col: int
    code: str  # e.g., TS2307
    message: str
    category: str = "other"  # import, declaration, type, syntax, unused, other


@dataclass
class TscErrorGroup:
    """All tsc errors grouped by file and category."""

    by_file: dict[str, list[TscError]] = field(default_factory=dict)
    by_category: dict[str, list[TscError]] = field(default_factory=dict)
    file_fix_order: list[str] = field(default_factory=list)


# =============================================================================
# tsc output parser
# =============================================================================

_TSC_LINE_RE = re.compile(
    r"^(?:> )?(.+?)\((\d+),(\d+)\):?\s+error\s+(TS\d+):\s*(.+)$"
)
_TSC_LINE_RE_ALT = re.compile(
    r"^(?:> )?(.+?):(\d+):(\d+)\s+[-–—]+\s+error\s+(TS\d+):\s*(.+)$"
)

# Category mapping from error code
_ERROR_CATEGORY: dict[str, str] = {
    "TS2307": "import",
    "TS2792": "import",
    "TS2304": "declaration",
    "TS2339": "declaration",
    "TS2552": "declaration",
    "TS2694": "declaration",
    "TS2445": "declaration",
    "TS2322": "type",
    "TS2345": "type",
    "TS2769": "type",
    "TS2554": "type",
    "TS2571": "type",
    "TS18046": "type",
    "TS7053": "type",
    "TS2365": "type",
    "TS2353": "type",
    "TS2416": "type",
    "TS2540": "type",
    "TS2722": "type",
    "TS6133": "unused",
    "TS6196": "unused",
    "TS6192": "unused",
    "TS2375": "syntax",
    "TS1005": "syntax",
    "TS1109": "syntax",
    "TS1128": "syntax",
    "TS17012": "syntax",
}

_PRIORITY_ORDER = ["import", "declaration", "type", "syntax", "unused", "other"]


def parse_tsc_errors(output: str, target_dir: str = "") -> TscErrorGroup:
    """Parse tsc --noEmit output into structured error groups.

    Groups errors by file (for per-file fixing) and by category
    (for fix priority). Also computes a fix order: files with
    import errors are fixed first.
    """
    group = TscErrorGroup()
    target_path = Path(target_dir).resolve() if target_dir else None

    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        m = _TSC_LINE_RE.match(line) or _TSC_LINE_RE_ALT.match(line)
        if not m:
            continue

        file_path = m.group(1)
        # Normalize paths — strip leading ./ or relative prefix
        if file_path.startswith("./"):
            file_path = file_path[2:]

        # If tsc emitted an absolute path, make it relative to target
        if target_path and file_path.startswith(str(target_path)):
            try:
                rel = Path(file_path).relative_to(target_path)
                file_path = str(rel)
            except ValueError:
                pass

        err = TscError(
            file=file_path,
            line=int(m.group(2)),
            col=int(m.group(3)),
            code=m.group(4),
            message=m.group(5).strip(),
            category=_ERROR_CATEGORY.get(m.group(4), "other"),
        )

        if err.file not in group.by_file:
            group.by_file[err.file] = []
        group.by_file[err.file].append(err)

        if err.category not in group.by_category:
            group.by_category[err.category] = []
        group.by_category[err.category].append(err)

    # Compute fix order: files with import errors first, then declaration,
    # then type, then syntax, then the rest.
    scored: list[tuple[int, str]] = []
    for fname, errors in group.by_file.items():
        priority = 5  # default (highest number = lowest priority)
        for err in errors:
            cat_priority = _PRIORITY_ORDER.index(err.category) if err.category in _PRIORITY_ORDER else 99
            priority = min(priority, cat_priority)
        scored.append((priority, fname))

    scored.sort()
    group.file_fix_order = [fname for _, fname in scored]

    return group


# =============================================================================
# VerifyAgent
# =============================================================================


class VerifyAgent(BaseAgent):
    """Agent that verifies the generated React Native project builds correctly.

    Uses a LangGraph ReAct agent for the build-verify-fix loop. The agent
    calls run_build_check → reads error files → transforms code → writes fix.

    Enhanced with:
    - Structured tsc error parsing and categorization
    - Cross-file context for import resolution
    - Self-verifying fix loop (read → fix → run_tsc_check → iterate)
    - Priority-ordered multi-file fixing (import errors first)
    """

    def __init__(self, config: Config, llm: LLMClient):
        super().__init__(config, llm)
        self._target = Path(config.target_dir)
        # Populated after each _auto_fix cycle: {filename: {fixed, error_categories, ...}}
        self.last_fix_results: dict[str, dict] = {}
        self._rag_engine = None

    def set_rag_engine(self, engine):
        """Attach a RAG engine for semantic type definition retrieval."""
        self._rag_engine = engine

    # ---- Structured error fix -------------------------------------------------

    def _auto_fix_with_agent(self, errors: str) -> int:
        """Use the ReAct agent to auto-fix build errors.

        Parses tsc errors into structured groups, orders files by fix
        priority, and fixes each file with a self-verifying agent loop.
        """
        # Parse errors into structured groups
        error_group = parse_tsc_errors(errors, str(self._target))

        if not error_group.by_file:
            self.log_warn("Verify", "Could not identify fixable error files from tsc output.")
            self.console.print(f"[dim]{errors[:500]}[/dim]")
            return 0

        # Log what we found
        cat_counts = {cat: len(errs) for cat, errs in error_group.by_category.items()}
        self.log_info("Verify", f"Parsed {sum(cat_counts.values())} errors: {cat_counts}")
        self.log_info(
            "Verify",
            f"Fix order ({len(error_group.file_fix_order)} files): "
            f"{', '.join(error_group.file_fix_order[:6])}{'...' if len(error_group.file_fix_order) > 6 else ''}",
        )

        # Build cross-file context from ALL files in the project
        cross_file_context = self._build_cross_file_context(error_group)

        # Capture per-file error data before fixing
        error_categories_by_file: dict[str, set[str]] = {}
        for filename, file_errors in error_group.by_file.items():
            error_categories_by_file[filename] = set()
            error_codes_by_file: set[str] = set()
            for e in file_errors:
                error_categories_by_file[filename].add(e.category)
                error_codes_by_file.add(e.code)
            # Pre-populate fix results (will be updated after fixing)
            self.last_fix_results[filename] = {
                "error_count": len(file_errors),
                "error_categories": sorted(error_categories_by_file[filename]),
                "error_codes": sorted(error_codes_by_file),
                "lines": sorted(set((e.line, e.col) for e in file_errors)),
                "fixed": False,
            }

        success_count = 0
        for filename in error_group.file_fix_order:
            # Only fix files that exist in our target
            file_path = self._resolve_file(filename)
            if not file_path:
                self.log_warn("Verify", f"File not found: {filename}")
                continue

            # Get errors specific to this file
            file_errors = error_group.by_file[filename]
            file_error_text = "\n".join(
                f"  {e.line}:{e.col} [{e.code}] {e.message}" for e in file_errors
            )

            fixed = self._fix_with_agent(
                file_path=file_path,
                errors=file_error_text,
                filename=filename,
                file_error_group=error_group.by_file[filename],
                cross_file_context=cross_file_context,
            )
            if fixed:
                self.log_success("Verify", f"Auto-fixed {filename}")
                if filename in self.last_fix_results:
                    self.last_fix_results[filename]["fixed"] = True
                    self.last_fix_results[filename]["file_path"] = str(file_path)
                success_count += 1
            else:
                if filename in self.last_fix_results:
                    self.last_fix_results[filename]["file_path"] = str(file_path)

        self.log_info("Verify", f"Auto-fixed {success_count}/{len(error_group.file_fix_order)} file(s).")
        return success_count

    def _build_cross_file_context(self, error_group: TscErrorGroup) -> str:
        """Collect type definition context for fixing errors.

        Two strategies, tried in order:
          1. RAG: query the vector store with error messages to find type
             definitions semantically (covers indirect types like Context generics,
             inherited interfaces, etc.).
          2. Fallback: scan imports for direct companion file exports
             (original approach).

        The RAG approach is strictly better — it retrieves type definitions
        even when the erroring file doesn't directly import the type file
        (e.g. types from Context providers, navigator params, etc.).
        """
        # ── Strategy 1: RAG-based type definition retrieval ──────────────
        if self._rag_engine is not None:
            context_parts = []
            seen_content: set[str] = set()

            for filename in error_group.file_fix_order[:5]:
                file_path = self._resolve_file(filename)
                if not file_path or not file_path.exists():
                    continue
                try:
                    source = file_path.read_text(encoding="utf-8")
                except Exception:
                    continue

                # Build query from: error file content + error messages
                file_errors = error_group.by_file.get(filename, [])
                error_text = " ".join(f"{e.code}: {e.message}" for e in file_errors[:3])

                # Query with the file's source code + error messages
                query = f"{error_text}\n{source[:1500]}"
                results = self._rag_engine.retrieve_context(
                    query_code=query,
                    filename=filename,
                    k=4,
                    score_threshold=0.25,
                )

                # Filter to only TS output types (not issue patterns)
                type_results = [r for r in results if r.get("type") == "ts_output"]
                if type_results:
                    formatted = self._rag_engine.format_type_context(type_results)
                    if formatted not in seen_content:
                        seen_content.add(formatted)
                        context_parts.append(formatted)

            if context_parts:
                return "\n\n".join(context_parts)

            # If RAG returned nothing useful, fall through to Strategy 2

        # ── Strategy 2: Import-scan fallback (original) ──────────────────
        context_parts = []
        seen: set[str] = set()

        for filename in error_group.file_fix_order[:5]:
            file_path = self._resolve_file(filename)
            if not file_path or not file_path.exists():
                continue
            try:
                source = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            imports = re.findall(r"from\s+['\"](\.\.?/[^'\"]+)['\"]", source)
            for imp in imports[:5]:
                resolved = self._resolve_import_from_string(filename, imp)
                if resolved and resolved.exists() and str(resolved) not in seen:
                    seen.add(str(resolved))
                    sigs = self._extract_exports(resolved)
                    if sigs:
                        context_parts.append(
                            f"# {resolved.name} (imported via '{imp}' from {filename})\n"
                            + "\n".join(sigs)
                        )

        return "\n\n".join(context_parts[:10]) if context_parts else ""

    def _extract_exports(self, file_path: Path) -> list[str]:
        """Extract export/interface/type/import lines from a file (compact)."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return []

        lines = []
        for line in content.split("\n"):
            stripped = line.strip()
            if any(
                stripped.startswith(kw)
                for kw in [
                    "export ", "export type", "export interface",
                    "export enum", "export class", "export const",
                    "export function", "export default",
                    "interface ", "type ", "import type",
                    "export {", "export *",
                ]
            ):
                lines.append(stripped)
            # Also capture comment-documented exports
            elif stripped.startswith("// @") or stripped.startswith("/**"):
                lines.append(stripped)

        # Limit to keep context reasonable
        return lines[:30]

    def _resolve_import_from_string(self, current_file: str, import_path: str) -> Optional[Path]:
        """Resolve a relative import path to a file on disk.

        Tries common extensions (.ts, .tsx, /index.ts, /index.tsx).
        """
        # Find the directory of the current file
        current_file_path = self._resolve_file(current_file)
        if not current_file_path:
            return None

        base = current_file_path.parent / import_path
        for ext in ["", ".ts", ".tsx", ".js", ".jsx"]:
            candidate = base.parent / f"{base.name}{ext}" if ext else base
            if candidate.exists():
                return candidate
            # Try index files
            idx = base / f"index{ext}"
            if idx.exists():
                return idx
        return None

    # ---- Enhanced per-file fix ------------------------------------------------

    def _fix_with_agent(
        self,
        file_path: Path,
        errors: str,
        filename: str,
        file_error_group: Optional[list[TscError]] = None,
        cross_file_context: str = "",
    ) -> bool:
        """Fix a single file using the LangGraph ReAct agent with self-verification.

        The agent is given `read_source_file`, `write_output_file`, and
        `run_tsc_check` tools so it can:
        1. Read the current file
        2. Write the corrected code
        3. Run tsc to verify
        4. Iterate if errors remain

        Only returns True if write_output_file was actually called or a
        valid code block was extracted.
        """
        try:
            source = file_path.read_text(encoding="utf-8")

            # Build enhanced prompt with categorized errors + cross-file context
            category_labels = []
            if file_error_group:
                seen_cats = set()
                for e in file_error_group:
                    if e.category not in seen_cats:
                        seen_cats.add(e.category)
                        category_labels.append(e.category)
            category_hint = ", ".join(category_labels) if category_labels else "mixed"

            prompt = get_fix_prompt(source, errors, filename)

            # Append cross-file context if available
            if cross_file_context:
                prompt += f"\n\n## Companion File Context (exports from imported files)\n{cross_file_context}"

            # Collect additional error context — show top errors from OTHER files too
            # so the agent understands inter-file dependencies
            prompt += f"\n\nFile categories being fixed: {category_hint}"

            if self.llm:
                agent = self.create_agent(
                    tools=[
                        read_source_file,
                        write_output_file,
                        run_tsc_check,
                        run_build_check,
                    ],
                    system_prompt=BUILD_FIX_SYSTEM,
                    name="fix_agent",
                )

                result = agent.invoke({
                    "messages": [
                        HumanMessage(
                            content=(
                                f"Fix the build errors in {filename}.\n\n"
                                f"{prompt}\n\n"
                                f"## Instructions\n"
                                f"1. Read the file: use read_source_file('{file_path}')\n"
                                f"2. Write the corrected code: use write_output_file\n"
                                f"3. Verify:\n"
                                f"   - First use run_build_check(target_dir='{self._target}')\n"
                                f"     to run a full build (npm install + tsc).\n"
                                f"   - If node_modules already exist, use\n"
                                f"     run_tsc_check(target_dir='{self._target}') for faster\n"
                                f"     iteration.\n"
                                f"4. If BUILD_ERRORS appear, read the file and fix again\n"
                                f"5. Stop when run_tsc_check or run_build_check returns BUILD_OK\n\n"
                                f"Target directory: {self._target}"
                            )
                        ),
                    ]
                })

                # ---- Check if write_output_file was called in ANY turn ----
                tool_wrote = False
                for msg in result["messages"]:
                    if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
                        for tc in msg.additional_kwargs.get("tool_calls", []):
                            func_name = ""
                            if isinstance(tc, dict):
                                func_name = tc.get("function", {}).get("name", "")
                                func_args_str = tc.get("function", {}).get("arguments", "{}")
                            else:
                                func_name = getattr(tc, "function", None) or ""
                                func_args_str = "{}"

                            if "write_output_file" in func_name:
                                tool_wrote = True
                                # Try to extract the code from the tool call args to check validity
                                try:
                                    import json
                                    func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else {}
                                    written_code = func_args.get("code", "")
                                    if len(written_code) > 50:  # valid code block
                                        break
                                except (json.JSONDecodeError, TypeError):
                                    pass

                if tool_wrote:
                    return True

                # ---- Fallback: extract code block from final response ----
                response = result["messages"][-1].content
                match = re.search(
                    r"```(?:tsx|typescript|ts|jsx|javascript|js|json)\n(.*?)```",
                    response,
                    re.DOTALL,
                )
                if match:
                    code = match.group(1).strip()
                    if len(code) > 50:  # sanity: actual code, not just "fixed!"
                        file_path.write_text(code, encoding="utf-8")
                        self.log_info("Verify", f"Applied code-block fix to {filename}")
                        return True

                result_text = result["messages"][-1].content[:300] if result["messages"] else ""
                self.log_warn(
                    "Verify",
                    f"Agent did not produce a valid fix for {filename} — "
                    f"no write_output_file call, no valid code block. Response: {result_text}...",
                )
                return False
            else:
                return False

        except Exception as e:
            self.log_warn("Verify", f"Failed to fix {filename}: {e}")
            return False

    # ---- Legacy auto-fix (kept for StateMachine compatibility) ---------------

    def _auto_fix(self, errors: str) -> int:
        """Legacy auto-fix (returns count of files fixed).

        Delegates to the enhanced ReAct agent fix system.
        """
        return self._auto_fix_with_agent(errors)

    # ---- Standard build steps (used by StateMachine) ------------------------

    def _run_npm_install(self) -> bool:
        """Run npm install. Returns True on success."""
        import subprocess
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(self._target),
                capture_output=True, text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            self.log_warn("Verify", "npm install timed out (120s)")
            return False
        if result.returncode != 0:
            self.log_warn("Verify", f"npm install failed: {result.stderr[:500]}")
            return False
        return True

    def _run_tsc(self) -> tuple[bool, str]:
        import subprocess
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(self._target),
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stdout + result.stderr

    # ---- Helper -------------------------------------------------------------

    def _resolve_file(self, filename: str) -> Optional[Path]:
        """Resolve a filename (from tsc output) to an actual Path.

        Handles: src/Foo.tsx, /absolute/path/Foo.tsx, Foo.tsx
        """
        # If it's already a valid path, try direct lookup
        direct = Path(filename)
        if direct.is_absolute():
            return direct if direct.exists() else None
        if direct.exists():
            return direct.resolve()

        # Try under target/src
        candidate = self._target / filename
        if candidate.exists():
            return candidate

        # Try just the filename (rglob)
        candidates = list(self._target.rglob(Path(filename).name))
        if candidates:
            return candidates[0]

        # Try by stem (tsc may report .tsx as .ts or vice versa)
        stem = Path(filename).stem
        for ext in [".tsx", ".ts", ".jsx", ".js"]:
            candidates = list(self._target.rglob(f"{stem}{ext}"))
            if candidates:
                return candidates[0]

        return None

    # ---- Advanced: grouped fix pass (fixes related files together) ----------

    def _fix_file_group(
        self,
        files: list[str],
        all_errors: str,
        cross_file_context: str = "",
    ) -> int:
        """Fix a group of related files (e.g., all files with import errors)."""
        success_count = 0
        for filename in files:
            file_path = self._resolve_file(filename)
            if not file_path:
                continue
            fixed = self._fix_with_agent(
                file_path=file_path,
                errors=all_errors,
                filename=filename,
                cross_file_context=cross_file_context,
            )
            if fixed:
                success_count += 1
        return success_count
