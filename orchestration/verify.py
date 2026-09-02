"""orchestration/verify — deterministic Verify-phase orchestration.

Runs tsc --noEmit, parses the output into structured errors, and drives the
fix sub-flow: it computes per-file context (RAG) + fix-memo (memory) exactly
once and delegates the actual fixing to ``agents.fix_agent.FixAgent`` (the
pipeline's only true agent) via setter injection.

This is a plain orchestration class — NOT an agent and NOT a skill. The fix
decision loop lives entirely inside FixAgent; VerifyPhase only routes inputs
to it (import errors first, then declaration/type/syntax/unused/other).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console

from framework.config import Config
from framework.harness import BudgetExceededError

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
# VerifyPhase
# =============================================================================


class VerifyPhase:
    """Deterministic Verify-phase orchestration (tsc → parse → route to fix).

    Fixes are performed by ``agents.fix_agent.FixAgent`` (injected via
    ``set_fix_agent``). VerifyPhase computes cross-file context and fix-memos
    once per file and hands them to the agent — it never fixes files itself.
    """

    def __init__(self, config: Config, harness=None):
        self.config = config
        self.harness = harness
        self.console = Console()
        self._target = Path(config.target_dir)
        # Populated after each _auto_fix cycle: {filename: {fixed, error_categories, ...}}
        self.last_fix_results: dict[str, dict] = {}
        self._rag_engine = None
        self._memory = None
        self._fix_agent = None  # injected via set_fix_agent

    # ---- injection ---------------------------------------------------------

    def set_rag_engine(self, engine):
        """Attach a RAG engine for semantic type definition retrieval."""
        self._rag_engine = engine

    def set_memory_store(self, store):
        """Attach the memory store for fix-memo injection (advisory only)."""
        self._memory = store

    def set_fix_agent(self, agent):
        """Inject the FixAgent that performs the actual fix loop."""
        self._fix_agent = agent

    # ---- logging -----------------------------------------------------------

    def log_info(self, tag: str, message: str):
        self.console.print(f"[cyan][{tag}][/cyan] {message}")

    def log_success(self, tag: str, message: str):
        self.console.print(f"[green][{tag}][/green] {message}")

    def log_warn(self, tag: str, message: str):
        self.console.print(f"[yellow][{tag}][/yellow] {message}")

    def log_error(self, tag: str, message: str):
        self.console.print(f"[red][{tag}][/red] {message}")

    # ---- Structured error fix -------------------------------------------------

    def _auto_fix(self, errors: str) -> int:
        """Auto-fix build errors with a structured per-file pass.

        Parses tsc errors into structured groups, orders files by fix
        priority (import errors first), and delegates each file's fix to
        the injected FixAgent.
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

            fixed = self._fix_file(
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

    # ---- Thin dispatcher to the injected FixAgent -----------------------------

    def _fix_file(
        self,
        file_path: Path,
        errors: str,
        filename: str,
        file_error_group: Optional[list[TscError]] = None,
        cross_file_context: str = "",
    ) -> bool:
        """Route one file's fix to the injected FixAgent.

        Computes the fix-memo once per file and hands context + memo to
        ``FixAgent.fix`` (which runs the ReAct loop or its single-shot
        degraded mode internally). BudgetExceededError propagates — the
        pipeline stops the verify phase (gave_up) instead of looping without
        tokens.
        """
        if self._fix_agent is None:
            return False

        memo = ""
        if self._memory is not None and file_error_group:
            codes = sorted({e.code for e in file_error_group})
            memo = self._memory.query_fix_memos(codes)

        return self._fix_agent.fix(
            file_path=file_path,
            errors=errors,
            filename=filename,
            target_dir=self._target,
            cross_file_context=cross_file_context,
            memo=memo,
        )

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
