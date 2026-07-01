"""prompts/verify — TypeScript build verification and fix prompts.

Used by VerifyAgent to auto-fix TypeScript build errors in the
converted React Native project.
"""

import re

# =============================================================================
# Build fix system prompt
# =============================================================================

BUILD_FIX_SYSTEM = """You are an expert React Native TypeScript developer debugging a TypeScript build failure.

Below is the TypeScript/TSX code and the build error. Analyze the error and produce a CORRECTED version.

## Tool Usage — fix → verify → iterate

You have access to:
1. `read_source_file` — read file contents
2. `write_output_file` — write the corrected file
3. `run_tsc_check` — run TypeScript type-checking (fast, no npm install)
4. `run_build_check` — full build check (npm install + tsc, use only if node_modules needs updating)

**Workflow: read → write → verify → iterate:**
1. Read the error file first to understand current code
2. Write the corrected version using write_output_file
3. Run run_tsc_check to verify your fix
4. If BUILD_ERRORS remain, read the file again and fix remaining issues
5. Repeat until BUILD_OK or you cannot resolve further errors

## Error Categories — identify what you're fixing

Errors fall into these categories — fix in this priority order:

### 1. IMPORT ERRORS (TS2307, TS2792)
"Cannot find module '...'" — the most common conversion issue.
- Remove any remaining Flutter/Dart imports (package:, dart:)
- Fix relative paths — Flutter's folder structure differs from RN
- Ensure required packages are installed (react-native, @react-navigation/*, etc.)

### 2. DECLARATION ERRORS (TS2304, TS2339, TS2552)
"Cannot find name 'X'" / "Property 'X' does not exist on type 'Y'"
- The type/interface/component was not imported or doesn't exist
- Either add the import, or define the missing type locally
- For missing properties: check if the property name was adapted correctly from Flutter

### 3. TYPE MISMATCH (TS2322, TS2345, TS2769)
"Type 'X' is not assignable to type 'Y'"
- Wrong type annotation or incompatible value
- Replace `any` with proper types or fix value to match expected type
- Method signatures: Flutter methods often have different parameter shapes

### 4. SYNTAX ERRORS
Missing brackets, semicolons, or closing JSX tags

## Rules

1. Fix ALL errors in the build output — not just the first one
2. Do NOT change business logic — only fix compilation errors
3. Do NOT add `// @ts-ignore` or `// @ts-nocheck` — fix the actual error
4. Do NOT remove code that compiles correctly — only modify lines with errors
5. If a package import is missing, ADD the import rather than removing usage
6. Output the COMPLETE corrected file via write_output_file tool
7. After writing, ALWAYS run run_tsc_check to verify

## Common Auto-Conversion Patterns

- `any` used as prop type → replace with proper interface reference
- Missing `key` prop in list renders → add `key={item.id}`
- Wrong import path for companion files → fix relative path
- Non-exported type used → ensure the type is exported or defined locally
- `null` used where TS expects `undefined` → use `undefined` instead
- Method signature mismatch (Flutter methods have different parameter shapes) → adapt to RN conventions
- Flutter `?.` null-safe access → convert to `?.` optional chaining (same syntax) or `&&` short-circuit
- Flutter `!` null assertion → check if the value can actually be null, handle appropriately
"""


# =============================================================================
# Error categorization helpers
# =============================================================================

# Maps tsc error codes to fix categories
ERROR_CATEGORIES: dict[str, str] = {
    "TS2307": "import",
    "TS2792": "import",
    "TS2304": "declaration",
    "TS2339": "declaration",
    "TS2552": "declaration",
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
    "TS2322": "type",
    "TS2722": "type",
    "TS6133": "unused",
    "TS6196": "unused",
    "TS6192": "unused",
    "TS2694": "declaration",
    "TS2445": "declaration",
    "TS2375": "syntax",
    "TS1005": "syntax",
    "TS1109": "syntax",
    "TS1128": "syntax",
    "TS17012": "syntax",
}


def categorize_errors(tsc_output: str) -> dict[str, list[str]]:
    """Parse tsc output into categorized error messages."""
    categories: dict[str, list[str]] = {
        "import": [],
        "declaration": [],
        "type": [],
        "syntax": [],
        "unused": [],
        "other": [],
    }

    for line in tsc_output.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Match tsc error format: file(line,col): error TSXXXX: msg
        # or: file:line:col - error TSXXXX: msg
        match = re.search(r"error\s+(TS\d+):", line_stripped)
        if match:
            code = match.group(1)
            cat = ERROR_CATEGORIES.get(code, "other")
            categories[cat].append(line_stripped)
        elif "error" in line_stripped.lower():
            categories["other"].append(line_stripped)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


# =============================================================================
# Prompt builder
# =============================================================================


def get_fix_prompt(source_code: str, errors: str, filename: str) -> str:
    """Build a categorized fix prompt for a single TypeScript file."""
    categorized = categorize_errors(errors)

    # Add priority annotation so the LLM knows what to fix first
    priority_order = ["import", "declaration", "type", "syntax", "unused", "other"]
    error_sections = []
    for cat in priority_order:
        if cat in categorized:
            label = {
                "import": "IMPORT ERRORS (fix these first)",
                "declaration": "DECLARATION ERRORS (missing types/names)",
                "type": "TYPE MISMATCH ERRORS",
                "syntax": "SYNTAX ERRORS",
                "unused": "UNUSED (can be removed, lowest priority)",
                "other": "OTHER ERRORS",
            }.get(cat, cat.upper())

            for err in categorized[cat]:
                error_sections.append(f"  [{label}] {err}")

    categorized_block = "\n".join(error_sections) if error_sections else errors

    return f"""Fix the following React Native TypeScript file that has build errors.

File: {filename}

## Categorized Errors
```
{categorized_block}
```

## Current Code
```typescript
{source_code}
```

Work through this fix loop:
1. Read the file using read_source_file
2. Write the CORRECTED version using write_output_file
3. Verify with run_tsc_check
4. If errors remain, iterate: read → fix → verify again
5. Stop when run_tsc_check returns BUILD_OK

Output the corrected file ONLY through write_output_file."""
