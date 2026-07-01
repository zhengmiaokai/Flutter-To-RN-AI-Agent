"""prompts — Prompt templates for the Flutter-to-RN converter.

Modules:
- convert.py → Flutter → React Native conversion prompts
- verify.py  → TypeScript build verification & fix prompts
- scanner.py → AI-powered file classification prompts
- generic.py → Shared prompt utilities
"""

from prompts.convert import (
    FLUTTER_TO_RN_SYSTEM,
    FLUTTER_TO_RN_CORE,
    build_category_system_prompt,
    get_conversion_prompt,
)
from prompts.verify import (
    BUILD_FIX_SYSTEM,
    get_fix_prompt,
)
from prompts.scanner import (
    BATCH_CLASSIFY_SYSTEM,
    build_batch_prompt,
)

__all__ = [
    "FLUTTER_TO_RN_SYSTEM",
    "FLUTTER_TO_RN_CORE",
    "build_category_system_prompt",
    "BUILD_FIX_SYSTEM",
    "BATCH_CLASSIFY_SYSTEM",
    "get_conversion_prompt",
    "get_fix_prompt",
    "build_batch_prompt",
]
