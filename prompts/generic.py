"""prompts/generic — Shared/generic prompt utilities.

Contains prompt helpers shared across multiple agents.
"""

# =============================================================================
# Generic prompt helpers
# =============================================================================


def truncate_content(content: str, max_chars: int = 6000) -> str:
    """Truncate content to max_chars, adding a note if truncated."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n[... truncated ...]"
