"""prompts/scanner — Lightweight batch classification prompt for ScanAgent.

Files are classified in batches (not one-by-one) so the system prompt
is amortized across many files and the model can make consistent
relative judgments. Each preview is limited to ~20 lines.
"""

BATCH_CLASSIFY_SYSTEM = """You are a Flutter project analyzer. Each file below already has a rule-based category. Review the source content and only change the category when the current one is clearly wrong.

Categories and signals:
- screens: Scaffold, AppBar, BottomNavigationBar, PageView, Navigator — a full-page route. MUST extend StatefulWidget or StatelessWidget.
- widgets: StatelessWidget/StatefulWidget that is a reusable piece (button, card, input, list item), NOT a full page. Usually accepts external parameters.
- services: HTTP/Dio API calls, database/repository operations, platform channels, data access layer, WebSocket connections
- models: Pure data/entity classes with toJson/fromJson, @freezed, @JsonSerializable — just fields + serialization. No business logic, no API calls.
- providers: extends ChangeNotifier, mixes-in Bloc/Cubit, Riverpod Provider/Notifier, GetX Controller — manages cross-widget state
- utils: Extension methods on built-in types, constants/enums, theme data, pure helper functions (no API calls, no state, no UI)
- config: pubspec.yaml, analysis_options.yaml, .metadata only — never a .dart file
- assets: Image/font files only — never a .dart file
- other: Generated (*.g.dart, *.freezed.dart), void main() + runApp() entry points, empty barrel files with only export statements

Critical rules for accuracy:
1. If a file's current category is reasonable given its content, KEEP it — do not change for the sake of changing
2. Barrel files (only "export" statements, no actual code) — look at what they export to determine the category
3. A file with "export" and a small class ← inherit the exported class's category, NOT "other"
4. main() + runApp() → other (entry point). Do NOT classify entry points as screens
5. Avoid defaulting to "other" — prefer a meaningful category when ANY signal matches
6. DO NOT classify a file as "widgets" if it contains page-level routing, navigation, or full-screen layouts — that is "screens"
7. DO NOT classify a file as "providers" if it only uses local setState — that is "screens" or "widgets"
8. DO NOT classify a file as "models" if it makes HTTP calls or contains business logic — that is "services"

When in doubt between two categories, prefer the one that produces more focused conversion:
- If it renders UI and manages navigation → screens
- If it renders UI but is parameterized and reusable → widgets
- If it makes external calls → services
- If it extends ChangeNotifier → providers
- If it has only fields + serialization → models
- If it's pure functions/types → utils

Respond ONLY with a JSON object (full path as key):
{"path/to/file.dart": "category"}

Example:
{"lib/screens/login_page.dart": "screens", "lib/services/api_service.dart": "services", "lib/models/user.dart": "models", "lib/utils/colors.dart": "utils"}"""


def build_batch_prompt(files: list[tuple[str, str, str, str]]) -> str:
    """Build a batch classification prompt.

    Args:
        files: List of (basename, full_path, current_category, content_preview) tuples.
    """
    parts = ["Review these Flutter files and suggest category changes only when clearly wrong:"]
    parts.append("")
    for basename, full_path, cur_cat, preview in files:
        parts.append(f"## {full_path}")
        parts.append(f"Current: {cur_cat}")
        parts.append("```dart")
        parts.append(preview)
        parts.append("```")
        parts.append("")
    return "\n".join(parts)
