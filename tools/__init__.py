"""tools — LangChain @tool-decorated tool functions invoked by agents.

Each tool is a stateless, self-documenting function decorated with
langchain_core.tools.tool. The tool's docstring + parameter annotations
serve as the LLM-facing schema — no separate JSON definition needed.

All tools are registered in TOOLS and can be bound directly to
ChatOpenAI instances or LangGraph ReAct agents.

Key LangChain features used:
- @tool decorator (auto-generates tool schema from type hints + docstring)
- ToolRegistry (structured list for agent binding)
- Backward compatibility: FileWriter class kept for existing tests
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


# =============================================================================
# Tool 1: Read source file
# =============================================================================


@tool
def read_source_file(file_path: str) -> str:
    """Read a source file from disk and return its contents.

    Args:
        file_path: Absolute or relative path to the source file.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: file not found: {file_path}"
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


# =============================================================================
# Tool 2: Write output file
# =============================================================================


@tool
def write_output_file(code: str, output_path: str) -> str:
    """Write generated TypeScript/TSX code to a target file.

    Creates parent directories if they don't exist.

    Args:
        code: The TypeScript/TSX code to write.
        output_path: Target path (relative or absolute).
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(code, encoding="utf-8")
        return f"Written: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


# =============================================================================
# Tool 3: Scan and classify Flutter files
# =============================================================================

# Classification constants (reused from original scan_agent)
SCREEN_DIRS = {"pages", "screens", "views"}
WIDGET_DIRS = {"components", "widgets", "shared", "common"}
SERVICE_DIRS = {"services", "api", "network", "channels"}
MODEL_DIRS = {"models", "entities", "types"}
PROVIDER_DIRS = {"providers", "blocs", "view_models", "viewmodels", "store", "redux"}
UTIL_DIRS = {"utils", "helpers", "tools"}
ASSET_DIRS = {"assets", "images", "fonts", "icons", "res"}
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
DART_EXTENSIONS = {".dart"}
SKIP_DIRS = {
    ".git", ".dart_tool", "build", ".idea", ".vscode",
    "node_modules", "__tests__", "coverage",
    "ios", "android", "macos", "linux", "windows", "web",
    "test", "tests",
}
SKIP_FILES = {
    "pubspec.lock", ".flutter-plugins", ".flutter-plugins-dependencies",
    ".gitignore", "readme.md",
}
SKIP_FILE_PATTERNS = ["*.g.dart", "*.freezed.dart", "*.gr.dart"]
CONFIG_FILES = {"pubspec.yaml", "analysis_options.yaml", ".metadata"}
SCAN_CATEGORIES = [
    "screens", "widgets", "services", "models",
    "providers", "utils", "assets", "config", "other",
]


@tool
def classify_file(file_path: str, source_dir: str = "") -> str:
    """Classify a Flutter file into a category based on its path and extension.

    Categories: screens, widgets, services, models, providers, utils, assets, config, other.

    Args:
        file_path: Path to the Flutter file.
        source_dir: Project root (for relative path heuristics).
    """
    path = Path(file_path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts = [p.lower() for p in path.parts]

    if name in SKIP_FILES or any(p in SKIP_DIRS for p in parts):
        return "skip"
    if name in CONFIG_FILES:
        return "config"
    if suffix in ASSET_EXTENSIONS:
        return "assets"

    for part in parts:
        if part in SCREEN_DIRS:
            return "screens"
        if part in WIDGET_DIRS:
            return "widgets"
        if part in SERVICE_DIRS:
            return "services"
        if part in MODEL_DIRS:
            return "models"
        if part in PROVIDER_DIRS:
            return "providers"
        if part in UTIL_DIRS:
            return "utils"
        if part in ASSET_DIRS:
            return "assets"

    # Detect files inside Flutter package directories (packges/, packages/, modules/, plugins/)
    # Map the package name to the appropriate category for better conversion prompts.
    PACKAGE_DIRS = {"packges", "packages", "modules", "plugins"}
    PACKAGE_CATEGORY_KEYWORDS: dict[str, set[str]] = {
        "services": {"service", "network", "api", "channel", "router", "database", "preference"},
        "models": {"model", "entity"},
        "providers": {"bloc", "provider", "viewmodel", "view_model", "store"},
    }
    for idx, part in enumerate(parts):
        if part in PACKAGE_DIRS and idx + 1 < len(parts):
            pkg_name = parts[idx + 1]
            for cat, keywords in PACKAGE_CATEGORY_KEYWORDS.items():
                if any(kw in pkg_name for kw in keywords):
                    return cat
            break

    if suffix in DART_EXTENSIONS:
        if source_dir:
            try:
                rel = path.resolve().relative_to(Path(source_dir).resolve())
                if len(rel.parents) <= 1 or (rel.parts[0] == "lib" and len(rel.parents) <= 2):
                    return "config"
            except ValueError:
                pass
        return "utils"

    if suffix in {".json"} and name not in SKIP_FILES:
        return "config"
    return "other"


@tool
def scan_source_directory(source_dir: str) -> str:
    """Recursively scan a Flutter source directory for convertible files.

    Returns a JSON map of category → file list.

    Args:
        source_dir: Path to the Flutter project root.
    """
    root = Path(source_dir)
    if not root.exists():
        return json.dumps({"error": f"Directory not found: {source_dir}"})

    groups: dict[str, list[str]] = {c: [] for c in SCAN_CATEGORIES}

    for file_path in root.rglob("*"):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        if any(file_path.match(p) for p in SKIP_FILE_PATTERNS):
            continue

        cat = classify_file.invoke({"file_path": str(file_path), "source_dir": source_dir})
        if cat in groups:
            groups[cat].append(str(file_path))

    total = sum(len(v) for v in groups.values())
    result = {k: v for k, v in groups.items() if v}
    result["total"] = total
    return json.dumps(result, indent=2)


# =============================================================================
# Tool 4: LLM-driven code extraction
# =============================================================================


@tool
def extract_code_from_response(response: str) -> str:
    """Extract code block from an LLM response string.

    Supports tsx, typescript, ts, jsx, javascript, js, and json blocks.
    Returns an empty string if no code block is found (never returns
    the raw response, which would corrupt files when written to disk).

    Args:
        response: The raw LLM response text.
    """
    match = re.search(
        r"```(?:tsx|typescript|ts|jsx|javascript|js|json)\n(.*?)```",
        response,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return ""


# =============================================================================
# Tool 5: Build verification
# =============================================================================


@tool
def run_build_check(target_dir: str) -> str:
    """Run npm install and TypeScript type-checking in the target directory.

    Returns BUILD_OK on success, or the full error output on failure.
    Use this for the initial build check — for quick iteration after fixes,
    prefer run_tsc_check which skips npm install.

    Args:
        target_dir: React Native project directory.
    """
    target = Path(target_dir)
    if not target.exists():
        return f"Error: target directory not found: {target_dir}"

    try:
        install = subprocess.run(
            ["npm", "install"],
            cwd=str(target),
            capture_output=True, text=True, timeout=120,
        )
        if install.returncode != 0:
            return f"npm install failed:\n{install.stderr[:1000]}"

        tsc = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(target),
            capture_output=True, text=True, timeout=120,
        )
        if tsc.returncode == 0:
            return "BUILD_OK"
        return f"BUILD_ERRORS:\n{(tsc.stdout + tsc.stderr)[:3000]}"
    except subprocess.TimeoutExpired:
        return "Error: build timed out (120s)"
    except FileNotFoundError:
        return "Error: npm/npx not found in PATH"
    except Exception as e:
        return f"Error running build: {e}"


@tool
def run_tsc_check(target_dir: str) -> str:
    """Run TypeScript type-checking only — skips npm install for speed.

    Use this to verify individual code fixes during the fix loop.
    Only use run_build_check when you need to reinstall dependencies.

    Returns BUILD_OK on success, or BUILD_ERRORS with the error output.

    Args:
        target_dir: React Native project directory.
    """
    target = Path(target_dir)
    if not target.exists():
        return f"Error: target directory not found: {target_dir}"
    if not (target / "node_modules").exists():
        return "Error: node_modules missing — run run_build_check first"

    try:
        tsc = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(target),
            capture_output=True, text=True, timeout=120,
        )
        if tsc.returncode == 0:
            return "BUILD_OK"
        return f"BUILD_ERRORS:\n{(tsc.stdout + tsc.stderr)[:3000]}"
    except subprocess.TimeoutExpired:
        return "Error: build timed out (120s)"
    except Exception as e:
        return f"Error running tsc: {e}"


# =============================================================================
# Tool 6: Reflection tool
# =============================================================================


@tool
def reflect_on_conversion(
    original_dart: str,
    converted_typescript: str,
    filename: str,
) -> str:
    """Reflect on the quality of a Flutter-to-RN conversion.

    Returns a structured prompt for the review agent to evaluate.

    Args:
        original_dart: The original Flutter source code.
        converted_typescript: The converted React Native code.
        filename: Source file name for context.
    """
    return json.dumps({
        "filename": filename,
        "original_length": len(original_dart),
        "converted_length": len(converted_typescript),
        "review_instructions": (
            "Check: widget mapping, state management (Provider→Context, setState→useState), "
            "layout (Column/Row→flexbox), styling (BoxDecoration→StyleSheet), "
            "imports (no dart imports, valid RN imports), "
            "navigation (Navigator→React Navigation), lifecycle (initState→useEffect)."
        ),
    })


# =============================================================================
# Tool registry — bind these to any ChatOpenAI / LangGraph agent
# =============================================================================

TOOLS = [
    read_source_file,
    write_output_file,
    classify_file,
    scan_source_directory,
    extract_code_from_response,
    run_build_check,
    run_tsc_check,
    reflect_on_conversion,
]


# =============================================================================
# Backward-compatible FileWriter (preserves existing test API)
# =============================================================================


class FileWriter:
    """Write converted React Native files (kept for test compatibility).

    Underlying file I/O delegates to write_output_file tool.
    """

    def __init__(self, target_dir: str):
        self._target = Path(target_dir)

    def write_screen(self, code: str, screen_name: str) -> Path:
        out = self._target / "src" / "screens" / f"{screen_name}.tsx"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        return out

    def write_widget(self, code: str, widget_name: str) -> Path:
        out = self._target / "src" / "components" / f"{widget_name}.tsx"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        return out

    def write_service(self, code: str, filename: str) -> Path:
        name = Path(filename).stem + ".ts"
        out = self._target / "src" / "services" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        return out

    def write_model(self, code: str, filename: str) -> Path:
        name = Path(filename).stem + ".ts"
        out = self._target / "src" / "models" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        return out

    def write_provider(self, code: str, filename: str) -> Path:
        name = Path(filename).stem + ".tsx"
        out = self._target / "src" / "providers" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        return out

    def write_util_file(self, code: str, filename: str) -> Path:
        name = Path(filename).stem + ".ts"
        out = self._target / "src" / "utils" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        return out

    @staticmethod
    def extract_code(response: str) -> str:
        """Extract code block from LLM response. Delegates to the @tool."""
        return extract_code_from_response.invoke({"response": response})

    @staticmethod
    def extract_tsx(response: str) -> str | None:
        match = re.search(r"```(?:tsx|typescript|ts)\n(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
