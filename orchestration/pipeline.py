"""orchestration/pipeline — 5-phase LangGraph StateGraph multi-agent pipeline.

Builds a compiled LangGraph StateGraph where:
- Each pipeline phase is a graph node (setup → scan → convert/reflect → verify)
- Nodes communicate through typed shared state
- Conditional edges handle the verify→fix retry loop
- JSON-file-backed state persistence for checkpoint/resume

Key LangGraph concepts:
- StateGraph with TypedDict state schema
- add_node / add_edge / add_conditional_edges for graph topology
- Compile + invoke for execution
- Multi-agent collaboration through shared state
- Conditional routing for retry loops
"""

from __future__ import annotations

import concurrent.futures
import shutil
from pathlib import Path
from typing import Any, TypedDict

from rich.console import Console

from framework.config import Config
from framework.llm import LLMClient
from framework.state import StateManager
from framework.state_machine import StateMachine, StepResult, StepStatus
from agents.scan_agent import ScanAgent
from agents.convert_agent import ConvertAgent
from agents.verify_agent import VerifyAgent
from agents.reflect_agent import ReflectAgent
from orchestration.setup import ProjectSetup

from langgraph.graph import END, StateGraph

console = Console()

_MAX_PARALLEL_WORKERS = 6


# =============================================================================
# LangGraph state schema for the pipeline
# =============================================================================


class PipelineState(TypedDict):
    """Shared state flowing through the LangGraph conversion pipeline."""
    source_dir: str
    target_dir: str
    model: str
    base_url: str | None
    api_key: str | None
    max_retries: int
    scan_mode: str
    skip_setup: bool
    skip_conversion: bool
    skip_verification: bool
    # Phase tracking
    scan_done: bool
    convert_done: bool
    verify_done: bool
    build_ok: bool
    gave_up: bool
    verify_attempts: int
    # Data
    file_groups: dict[str, list[Any]]
    converted_count: int
    failed_count: int
    errors: list[str]


# =============================================================================
# Pipeline — compiles a multi-agent LangGraph StateGraph
# =============================================================================


class Pipeline:
    """Main pipeline orchestrator — multi-agent Flutter-to-RN conversion.

    Builds a LangGraph StateGraph with 4 nodes:
      setup → scan → convert & reflect → verify (with fix loop)

    The graph is compiled once and invoked for each run. State is
    persisted via SQLite for checkpoint/resume capability.
    """

    def __init__(self, config: Config):
        self._config = config
        self._llm = LLMClient(config)
        self._state = StateManager(config.state_path)
        self._graph = self._build_graph()

    # =========================================================================
    # Graph construction
    # =========================================================================

    def _build_graph(self) -> StateGraph:
        """Build the multi-agent LangGraph StateGraph.

        Graph topology:
          setup → scan → convert → verify_dispatch
                                      ├──→ verify (retry) → back to verify_dispatch
                                      └──→ END

        Each node reads from / writes to PipelineState.
        """
        graph = StateGraph(PipelineState)

        # ── Nodes ───────────────────────────────────────────────────────────

        graph.add_node("setup", self._phase_setup)
        graph.add_node("scan", self._phase_scan)
        graph.add_node("copy_assets", self._phase_copy_assets)
        graph.add_node("convert", self._phase_convert)
        graph.add_node("verify", self._phase_verify)

        # ── Edges ───────────────────────────────────────────────────────────

        graph.add_edge("setup", "scan")
        graph.add_edge("scan", "copy_assets")
        graph.add_edge("copy_assets", "convert")
        graph.add_edge("convert", "verify")

        # ── Conditional edge for verify→fix loop ──────────────────────────

        graph.add_conditional_edges(
            "verify",
            self._route_after_verify,
            {
                "verify": "verify",   # retry
                END: END,
            },
        )

        graph.set_entry_point("setup")

        return graph

    # =========================================================================
    # Phase nodes (LangGraph node functions)
    # =========================================================================

    def _phase_setup(self, state: PipelineState) -> dict:
        """Phase 1: Project Setup."""
        console.print("[bold]Phase 1: Project Setup[/bold]")
        if self._config.skip_setup:
            console.print("  [yellow]Skipping setup (--skip-setup)[/yellow]")
            return {}

        setup = ProjectSetup(self._config)
        setup.run()
        console.print("[green][Setup][/green] React Native environment ready.")
        return {}

    def _phase_scan(self, state: PipelineState) -> dict:
        """Phase 2: Scan & Classify (hybrid rule-based + LLM)."""
        # ── Skip if already scanned with matching mode ─────────────────────
        if self._state.is_phase_completed("scan"):
            scan_data = self._state.get_phase_data("scan")
            if scan_data.get("scan_mode") == self._config.scan_mode:
                console.print("[bold]Phase 2: Scan & Classify[/bold]")
                console.print("  [dim]Scan already completed in previous run, skipping.[/dim]")
                return {}
            console.print(f"  [yellow]Scan mode changed, re-scanning.[/yellow]")

        console.print("[bold]Phase 2: Scan & Classify[/bold]")

        scanner = ScanAgent(self._config, llm=self._llm, scan_mode=self._config.scan_mode)
        groups = scanner.scan()

        # Convert Paths to strings for JSON-safe state
        serializable: dict[str, list[str]] = {}
        for cat, files in groups.items():
            serializable[cat] = [str(f) for f in files]

        total = sum(len(v) for v in serializable.values())
        console.print(f"  [cyan]Scanned {total} file(s)[/cyan]")

        # ── Persist phase data ─────────────────────────────────────────────
        self._state.set_phase_data("scan", {
            "scan_mode": self._config.scan_mode,
            "file_groups": serializable,
        })
        self._state.mark_phase_completed("scan")

        return {
            "scan_done": True,
            "file_groups": serializable,
            "errors": [],
            "scan_mode": self._config.scan_mode,
        }

    def _phase_copy_assets(self, state: PipelineState) -> dict:
        """Phase 2.5: Copy asset files to target project."""
        groups_raw = state.get("file_groups", {})
        asset_paths = [Path(fp) for fp in groups_raw.get("assets", [])]
        if not asset_paths:
            return {}

        target = Path(self._config.target_dir)
        source = Path(self._config.source_dir)
        for src_file in asset_paths:
            try:
                rel = src_file.relative_to(source.resolve() if source.exists() else source)
            except ValueError:
                rel = Path(src_file.name)
            dst = target / "src" / "assets" / rel.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_file, dst)
            except OSError:
                pass
        return {}

    def _phase_convert(self, state: PipelineState) -> dict:
        """Phase 3: Single-shot LLM conversion + quality reflection."""
        console.print("[bold]Phase 3: Conversion + Reflection[/bold]")

        if self._config.skip_conversion:
            console.print("  [yellow]Skipping conversion (--skip-conversion)[/yellow]")
            return {"convert_done": True, "converted_count": 0, "failed_count": 0}

        # ── Skip if already converted in a previous run ────────────────────
        if self._state.is_phase_completed("convert"):
            console.print("  [dim]Conversion already completed in previous run, skipping.[/dim]")
            conv_data = self._state.get_phase_data("convert")
            return {
                "convert_done": True,
                "converted_count": conv_data.get("converted_count", 0),
                "failed_count": conv_data.get("failed_count", 0),
            }

        groups_raw = state.get("file_groups", {})
        # Convert string paths back to Path objects with categories
        work_items: list[tuple[str, Path]] = []
        for category in ["screens", "widgets", "services", "models", "providers", "utils"]:
            for fp_str in groups_raw.get(category, []):
                fp = Path(fp_str)
                if fp.suffix.lower() != ".dart":
                    continue
                work_items.append((category, fp))

        if not work_items:
            console.print("  [yellow]No convertible source files found.[/yellow]")
            return {"convert_done": True, "converted_count": 0, "failed_count": 0}

        converter = ConvertAgent(self._config, self._llm, self._state)
        reflector = ReflectAgent(self._config, self._llm)

        # Build project-wide file registry for context-aware conversion
        from agents.convert_agent import build_file_registry, CATEGORY_MAP
        file_groups_paths: dict[str, list[Path]] = {}
        for cat in ["screens", "widgets", "services", "models", "providers", "utils"]:
            file_groups_paths[cat] = [Path(p) for p in groups_raw.get(cat, [])]
        registry = build_file_registry(file_groups_paths, self._config.target_dir, CATEGORY_MAP)
        converter.set_file_registry(registry)

        # Parallel conversion with ThreadPoolExecutor
        stats = {"success": 0, "failed": 0}

        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_PARALLEL_WORKERS) as executor:
            futures = {
                executor.submit(_convert_one_file, converter, category, src_path, self._state):
                    (category, src_path)
                for category, src_path in work_items
            }

            for future in concurrent.futures.as_completed(futures):
                category, src_path = futures[future]
                try:
                    ok = future.result()
                    if ok:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                except Exception:
                    stats["failed"] += 1

        console.print(f"  [dim]Converted: {stats['success']} success, {stats['failed']} failed[/dim]")

        # Reflection: quality check on all screens and widgets
        sample_items = [
            (cat, f) for cat, f in work_items
            if cat in ("screens", "widgets")
        ]
        for category, src_path in sample_items:
            _reflect_one_file(self._config, converter, reflector, category, src_path, self._state)

        # ── Persist phase data ─────────────────────────────────────────────
        self._state.set_phase_data("convert", {
            "converted_count": stats["success"],
            "failed_count": stats["failed"],
        })
        self._state.mark_phase_completed("convert")

        console.print(self._state.summary())
        return {"convert_done": True, "converted_count": stats["success"], "failed_count": stats["failed"]}

    def _phase_verify(self, state: PipelineState) -> dict:
        """Phase 4: Build verification with LangGraph StateMachine retry loop."""
        console.print("[bold]Phase 4: Verification[/bold]")

        if self._config.skip_verification:
            console.print("  [yellow]Skipping verification (--skip-verification)[/yellow]")
            return {"build_ok": True, "verify_done": True, "verify_attempts": 0}

        # Clear stale per-file error state from previous runs so a fresh
        # verification doesn't produce contradictory state (e.g. "build_ok:
        # true" alongside "fixed: false" files from a prior failed attempt).
        self._state.clear_phase_files("verify")

        verifier = VerifyAgent(self._config, self._llm)

        attempt = state.get("verify_attempts", 0)

        if attempt >= self._config.max_retries:
            console.print(f"  [yellow]Max retries ({self._config.max_retries}) reached, build has errors.[/yellow]")
            self._state.set_phase_data("verify", {
                "build_ok": False,
                "done": True,
                "gave_up": True,
                "attempts": attempt,
            })
            self._state.mark_phase_completed("verify")
            return {"build_ok": False, "gave_up": True, "verify_done": True, "verify_attempts": attempt}

        # Build the LangGraph StateMachine for the fix loop
        sm = StateMachine("verify-loop")
        sm.add_step("install", lambda _: _npm_install(verifier))
        sm.add_step("build", lambda data: _tsc_build(verifier, data))
        sm.add_conditional(
            "check",
            lambda data: data.get("build_ok", False) if data else False,
            on_success="done",
            on_failure="fix",
        )
        sm.add_step("fix", lambda data: _auto_fix(verifier, data), next_step="build", retry_count=3)

        sm.hook("before_step", lambda name, data: console.print(f"  [dim]StateGraph → {name}[/dim]"))
        sm.hook("on_error", lambda name, err: console.print(f"  [yellow]Step '{name}' error: {err}[/yellow]"))

        results = sm.run({"build_ok": False, "errors": "", "_fix_cycle": attempt})

        # ── Persist per-file verify state ─────────────────────────────────
        for step_name, step_result in results.items():
            if not step_result or not hasattr(step_result, 'data') or not step_result.data:
                continue
            fix_results = step_result.data.get("fix_results", {}) if isinstance(step_result.data, dict) else {}
            if fix_results:
                for filename, file_data in fix_results.items():
                    self._state.set_file_state("verify", filename, {
                        **file_data,
                        "status": "fixed" if file_data.get("fixed") else "unfixed",
                    })
                break  # only the last fix cycle matters

        # Check if ANY step gave up — if so, stop retrying immediately
        # (prevents infinite loop when auto-fix can't resolve errors)
        gave_up = any(
            isinstance(r.data, dict) and r.data.get("gave_up", False)
            for r in results.values()
            if hasattr(r, 'data') and r.data
        )
        if gave_up:
            console.print(f"  [yellow]Auto-fix gave up, stopping retries.[/yellow]")
            self._state.set_phase_data("verify", {
                "build_ok": False,
                "done": True,
                "gave_up": True,
                "attempts": attempt + 1,
            })
            self._state.mark_phase_completed("verify")
            return {"build_ok": False, "gave_up": True, "verify_done": True, "verify_attempts": attempt + 1}

        # Check the build step result (not check — that only returns True/False for routing)
        build_result = results.get("build")
        if build_result and build_result.status == StepStatus.SUCCESS:
            data = build_result.data if isinstance(build_result.data, dict) else {}
            if data.get("build_ok", False):
                console.print("[green][Verify][/green] Build succeeded!")
                self._state.set_phase_data("verify", {
                    "build_ok": True,
                    "done": True,
                    "gave_up": False,
                    "attempts": attempt + 1,
                    "files": {},  # Clear error data — build passed, so no errors
                })
                self._state.mark_phase_completed("verify")
                return {"build_ok": True, "verify_done": True, "verify_attempts": attempt + 1}

        # Not done — retry
        return {"build_ok": False, "verify_done": False, "verify_attempts": attempt + 1}

    def _route_after_verify(self, state: PipelineState) -> str:
        """Route after verification: retry or end."""
        attempt = state.get("verify_attempts", 0)
        if state.get("build_ok", False) or state.get("gave_up", False) or attempt >= self._config.max_retries:
            return END
        return "verify"

    # =========================================================================
    # Pipeline execution
    # =========================================================================

    def run(self) -> bool:
        """Compile and invoke the LangGraph StateGraph."""
        errors = self._config.validate()
        if errors:
            for e in errors:
                console.print(f"[red][Error][/red] {e}")
            return False

        console.print(f"[bold cyan]Flutter-to-RN Converter[/bold cyan]")
        console.print(f"  Source: {self._config.source_dir}")
        console.print(f"  Target: {self._config.target_dir}")
        console.print(f"  Model:  {self._config.model}")

        compiled = self._graph.compile()

        # ── Reset phase completion flags so all phases always run fresh ──
        # Per-file checkpoint data (phase_data.*.files) is preserved so
        # individual files that were already converted are still skipped.
        self._state.mark_phase_incomplete("scan")
        self._state.mark_phase_incomplete("convert")
        self._state.mark_phase_incomplete("verify")

        # ── Load persisted phase status to skip completed phases ───────────
        scan_phase_data = self._state.get_phase_data("scan")
        scan_done = self._state.is_phase_completed("scan")
        # Re-scan if scan_mode changed
        if scan_done and scan_phase_data.get("scan_mode") != self._config.scan_mode:
            scan_done = False
        file_groups = scan_phase_data.get("file_groups", {}) if scan_done else {}

        convert_done = self._state.is_phase_completed("convert")
        convert_phase_data = self._state.get_phase_data("convert") if convert_done else {}

        verify_phase_data = self._state.get_phase_data("verify")

        # Invoke
        initial_state: PipelineState = {
            "source_dir": self._config.source_dir,
            "target_dir": self._config.target_dir,
            "model": self._config.model,
            "base_url": self._config.base_url,
            "api_key": self._config.api_key,
            "max_retries": self._config.max_retries,
            "scan_mode": self._config.scan_mode,
            "skip_setup": self._config.skip_setup,
            "skip_conversion": self._config.skip_conversion,
            "skip_verification": self._config.skip_verification,
            # Restored phase flags
            "scan_done": scan_done,
            "convert_done": convert_done,
            "verify_done": False,
            "build_ok": False,
            "gave_up": False,
            "verify_attempts": 0,
            # Restored file groups
            "file_groups": file_groups,
            "converted_count": convert_phase_data.get("converted_count", 0) if convert_done else 0,
            "failed_count": convert_phase_data.get("failed_count", 0) if convert_done else 0,
            "errors": [],
        }

        final_state = compiled.invoke(initial_state)

        success = final_state.get("build_ok", False)
        if success:
            console.print("\n[bold green]Conversion complete![/bold green]")
        else:
            console.print("\n[bold yellow]Conversion complete with issues. Review output manually.[/bold yellow]")

        return True

# =============================================================================
# Standalone node helpers (used inside graph phases)
# =============================================================================


def _convert_one_file(
    converter: ConvertAgent,
    category: str,
    src_path: Path,
    state_mgr: StateManager,
) -> bool:
    """Convert a single file with checkpoint support. Thread-safe."""
    key = f"{category}:{src_path.name}"
    if state_mgr.is_completed(key):
        return True

    # Determine output path from category mapping
    from agents.convert_agent import CATEGORY_MAP
    mapping = CATEGORY_MAP.get(category)
    output_rel = None
    if mapping:
        subdir, ext = mapping
        output_rel = f"{subdir}/{src_path.stem}{ext}"

    extra = {
        "category": category,
        "source": str(src_path),
        "output": str(Path(converter.config.target_dir) / output_rel) if output_rel and hasattr(converter, 'config') else str(src_path),
        "output_rel": output_rel or "",
    }

    try:
        converter.convert_file(category, src_path)
        state_mgr.mark_completed(key, extra=extra)
        return True
    except Exception as exc:
        state_mgr.mark_failed(key, f"Conversion failed for {src_path.name}: {exc}", extra=extra)
        return False


def _build_reflection_feedback(result) -> str:
    """Build a targeted feedback block from reflection issues.

    Converts structured ReflectResult issues into a formatted prompt section
    that tells the LLM exactly what to fix in the re-conversion.
    """
    lines = [
        "## PREVIOUS CONVERSION ISSUES — Fix ALL of the following:",
        f"Quality score was {result.score}/100 with {len(result.issues)} issue(s) "
        f"({result.critical_count} critical).",
        "",
    ]
    for i, issue in enumerate(result.issues, 1):
        severity = issue.get("severity", "?") or "info"
        description = (issue.get("description") or "").strip()
        suggestion = (issue.get("suggestion") or "").strip()
        lines.append(f"{i}. [{severity.upper()}] {description}")
        if suggestion:
            lines.append(f"   → {suggestion}")
    if not result.issues:
        lines.append("(No specific issues captured — improve overall quality.)")

    return "\n".join(lines)


def _reflect_one_file(
    cfg: Config,
    converter: ConvertAgent,
    reflector: ReflectAgent,
    category: str,
    src_path: Path,
    state_mgr: StateManager | None = None,
):
    """Run quality reflection on a single converted file.

    If quality is below threshold, triggers re-conversion and re-verifies
    the result. Tracks re-conversion attempts and persistence quality
    scores per-file via state manager.
    """
    if category == "screens":
        output_path = Path(cfg.target_dir) / "src" / "screens" / f"{src_path.stem}.tsx"
    elif category == "widgets":
        output_path = Path(cfg.target_dir) / "src" / "components" / f"{src_path.stem}.tsx"
    else:
        return

    if not output_path.exists():
        return

    file_key = f"{category}:{src_path.name}"

    # Skip reflection if already done (checkpoint via structured state)
    if state_mgr:
        existing = state_mgr.get_file_state("reflect", file_key)
        if existing.get("status") in ("reviewed", "reconverted"):
            return

    try:
        original = src_path.read_text(encoding="utf-8")
        converted = output_path.read_text(encoding="utf-8")
    except Exception:
        return

    result = reflector.reflect(
        rn_code=converted,
        flutter_source=original,
        filename=src_path.name,
    )

    # Common reflect state
    reflect_state = {
        "score": result.score,
        "pass": result.pass_,
        "issues": result.issues,
        "critical_count": result.critical_count,
        "summary": result.summary,
        "needs_rework": result.needs_rework(),
    }

    if result.needs_rework():
        # Log top issues for debugging
        issue_summary = "; ".join(
            f"[{i.get('severity','?')}] {i.get('description','')[:80]}"
            for i in result.issues[:3]
        )
        console.print(f"  [yellow][Reflect][/yellow] {src_path.name} score={result.score} — re-converting")
        if issue_summary:
            console.print(f"         Issues: {issue_summary}")

        # Build targeted feedback from reflection issues so the LLM knows
        # exactly what to fix instead of re-generating the same flawed output
        reflection_feedback = _build_reflection_feedback(result)

        # Backup original converted output before re-conversion, so we can
        # roll back if the new version scores worse than the original.
        backup_content = converted

        reflect_state["status"] = "reconverted"
        reflect_state["reconverted"] = True
        try:
            converter.convert_file(category, src_path, reflection_feedback=reflection_feedback)

            # Re-reflect to verify the fix
            try:
                new_converted = output_path.read_text(encoding="utf-8")
                new_result = reflector.reflect(
                    rn_code=new_converted,
                    flutter_source=original,
                    filename=src_path.name,
                )

                # Score guard: revert if re-conversion produced worse output
                if new_result.score < result.score:
                    console.print(f"  [yellow][Reflect][/yellow] {src_path.name} re-conversion score ({new_result.score}) dropped from original ({result.score}), reverting.")
                    output_path.write_text(backup_content, encoding="utf-8")
                    # Use the original reflect state — the revert is labelled
                    # "reconverted" so it won't be re-processed next run, but
                    # the actual converted content is the original.
                    reflect_state["reverted"] = True
                else:
                    if new_result.needs_rework():
                        console.print(f"  [yellow][Reflect][/yellow] {src_path.name} still below threshold (score={new_result.score}), accepting.")
                    else:
                        console.print(f"  [dim][Reflect][/dim] {src_path.name} score={new_result.score} OK after re-conversion")
                    # Update state with post-reconversion values
                    reflect_state["post_reconversion_score"] = new_result.score
                    reflect_state["post_reconversion_pass"] = new_result.pass_
                    reflect_state["post_reconversion_issues"] = new_result.issues
            except Exception as exc:
                console.print(f"  [yellow][Reflect][/yellow] Re-reflection failed for {src_path.name}: {exc}")
        except Exception as exc:
            console.print(f"  [yellow][Reflect][/yellow] Re-conversion failed for {src_path.name}: {exc}")

        if state_mgr:
            state_mgr.set_file_state("reflect", file_key, reflect_state)
    else:
        console.print(f"  [dim][Reflect][/dim] {src_path.name} score={result.score} OK")
        reflect_state["status"] = "reviewed"
        reflect_state["reconverted"] = False
        if state_mgr:
            state_mgr.set_file_state("reflect", file_key, reflect_state)


def _npm_install(verifier: VerifyAgent) -> StepResult:
    # Skip if node_modules already exists (saves ~30s per retry)
    target = Path(verifier.config.target_dir)
    if (target / "node_modules").exists():
        return StepResult(status=StepStatus.SUCCESS, data={"npm_ok": True, "skipped": True})
    try:
        ok = verifier._run_npm_install()
        if ok:
            return StepResult(status=StepStatus.SUCCESS, data={"npm_ok": True})
        return StepResult(status=StepStatus.FAILED, error="npm install failed")
    except Exception as e:
        return StepResult(status=StepStatus.FAILED, error=str(e))


def _tsc_build(verifier: VerifyAgent, data: dict | None = None) -> StepResult:
    """Run tsc build check. Always runs tsc — no shortcuts via gave_up."""
    base = dict(data or {}).copy()
    try:
        success, errors = verifier._run_tsc()
    except Exception as e:
        return StepResult(status=StepStatus.FAILED, data={**base, "build_ok": False, "errors": str(e)}, error=str(e))

    if success:
        return StepResult(status=StepStatus.SUCCESS, data={**base, "build_ok": True})
    return StepResult(
        status=StepStatus.FAILED,
        data={**base, "build_ok": False, "errors": errors[:2000]},
        error=errors[:200],
    )


def _auto_fix(verifier: VerifyAgent, data: dict | None) -> StepResult:
    if data is None:
        data = {"build_ok": False, "errors": ""}
    errors = data.get("errors", "")
    if not errors:
        return StepResult(status=StepStatus.SUCCESS, data=data)

    attempt = data.get("_fix_cycle", 0) + 1
    data = {**data, "_fix_cycle": attempt}

    if attempt > (getattr(verifier.config, 'max_retries', 3)):
        console.print(f"[yellow]Auto-fix: reached max cycles, build still has errors.[/yellow]")
        return StepResult(status=StepStatus.FAILED, data={**data, "build_ok": False, "gave_up": True}, error="Max auto-fix retries reached")

    try:
        # Reset and run fix — last_fix_results will be populated by the agent
        verifier.last_fix_results = {}
        fixed_count = verifier._auto_fix(errors)
        # Attach per-file fix results to returned data
        data["fix_results"] = dict(verifier.last_fix_results) if verifier.last_fix_results else {}
        if fixed_count > 0:
            return StepResult(status=StepStatus.SUCCESS, data=data)
        console.print("[yellow]Auto-fix unable to resolve remaining errors.[/yellow]")
        return StepResult(status=StepStatus.FAILED, data={**data, "build_ok": False, "gave_up": True}, error="No files could be fixed")
    except Exception as e:
        return StepResult(status=StepStatus.FAILED, error=str(e), data=data)
