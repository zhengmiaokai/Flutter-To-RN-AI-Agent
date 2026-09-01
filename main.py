"""main — CLI entry point for the Flutter-to-RN converter.

Powered by LangChain + LangGraph:
- OpenAI integration:   ChatOpenAI (supports any OpenAI-compatible API)
- Utility tools:        @tool-decorated functions in tools/__init__.py
- State persistence:    JSON-file-backed checkpoint/resume
- Workflow state:       StateGraph with typed state + conditional edges
- Multi-agent:          4 agents as graph nodes sharing a PipelineState

Usage:
    python3 main.py                          # uses ./sample → ./output
    python3 main.py --source ./my_app --target ./out
"""

import os
import sys

# ── Auto-activate venv if running outside it ──────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_DIR = os.path.join(_SCRIPT_DIR, "venv")
_VENV_MARKER = os.path.join(_VENV_DIR, "bin", "activate")

if (
    sys.prefix != _VENV_DIR                            # not already inside this venv
    and os.path.isfile(_VENV_MARKER)                   # venv exists
):
    _venv_python = os.path.join(_VENV_DIR, "bin", "python")
    os.execv(_venv_python, [_venv_python] + sys.argv)


def main():
    """Entry point called from CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Flutter-to-RN: Convert Flutter projects to React Native"
    )
    parser.add_argument("--source", default=os.path.join(_SCRIPT_DIR, "sample"),
                        help="Source Flutter project directory (default: ./sample)")
    parser.add_argument("--target", default=os.path.join(_SCRIPT_DIR, "output"),
                        help="Output directory for React Native project (default: ./output)")
    parser.add_argument("--model", default="deepseek-v4-pro", help="LLM model (default: deepseek-v4-pro)")
    parser.add_argument("--api-key", default=None, help="OpenAI API key")
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible API base URL")
    parser.add_argument("--timeout", type=float, default=120.0, help="LLM request timeout in seconds (default: 120)")
    parser.add_argument("--max-retries", type=int, default=3, help="Max auto-fix retries (default: 3)")
    parser.add_argument("--scan-mode", default="fast", choices=["fast", "smart", "deep"],
                        help="Scan mode: fast (no LLM, default), smart (LLM for uncertain), deep (LLM for all dart files)")
    parser.add_argument("--skip-setup", action="store_true", help="Skip project setup phase")
    parser.add_argument("--skip-conversion", action="store_true", help="Skip code conversion phase")
    parser.add_argument("--skip-verification", action="store_true", help="Skip build verification phase")

    # ── Harness: caching, memory, budget, verify mode ──
    parser.add_argument("--no-memory", action="store_true", help="Disable cross-run memory (few-shots/fix-memos/digest)")
    parser.add_argument("--cache-ttl", type=int, default=None, help="Response cache TTL in hours")
    parser.add_argument("--budget", type=int, default=None, help="Hard token budget (0 = unlimited)")
    parser.add_argument("--route", action="append", default=None, metavar="TASK=MODEL",
                        help="Route a task to a model (repeatable, e.g. --route convert=claude-sonnet-5). "
                             "Overrides the primary model only; base_url/api_key inherit the task's "
                             "MODEL_ROUTES entry or the global config.")

    args = parser.parse_args()

    from framework.config import init_config
    from orchestration.pipeline import Pipeline

    config_kwargs = dict(
        source_dir=args.source,
        target_dir=args.target,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=args.max_retries,
        scan_mode=args.scan_mode,
        skip_setup=args.skip_setup,
        skip_conversion=args.skip_conversion,
        skip_verification=args.skip_verification,
        memory_enabled=not args.no_memory,
    )
    if args.route:
        routes = {}
        for spec in args.route:
            if "=" in spec:
                task, model = spec.split("=", 1)
                routes[task.strip()] = {"model": model.strip()}
        if routes:
            config_kwargs["model_routes"] = routes
    # Optional ints: only pass when set so dataclass defaults survive.
    if args.cache_ttl is not None:
        config_kwargs["cache_ttl_hours"] = args.cache_ttl
    if args.budget is not None:
        config_kwargs["token_budget"] = args.budget

    config = init_config(**config_kwargs)

    pipeline = Pipeline(config)
    success = pipeline.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
