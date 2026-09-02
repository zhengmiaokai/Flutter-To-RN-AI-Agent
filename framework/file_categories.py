"""framework/file_categories — shared file-category inference.

Single source of truth for categorizing a target-relative filename (e.g.
``src/screens/LoginPage.tsx`` → ``screens``). Shared by the fix sub-flow so
the usage ledger, fix-memo routing, and ``last_fix_results`` all agree:
- ``agents/fix_agent.py`` uses it for ledger + single-shot fix routing
- ``orchestration/verify.py`` (via pipeline) uses it for fix-memos
"""


def infer_file_category(filename: str) -> str:
    """Infer the category from a target-relative path (for routing/memos)."""
    norm = "/" + str(filename).replace("\\", "/") + "/"
    for cat in ("screens", "widgets", "providers", "services", "models", "utils"):
        if f"/{cat}/" in norm:
            return cat
    return "other"
