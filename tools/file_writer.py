"""tools/file_writer — Backward-compatible re-export for FileWriter.

FileWriter is now defined in tools/__init__.py alongside the @tool functions.
This file exists only to not break existing imports.
"""

from tools import FileWriter

__all__ = ["FileWriter"]
