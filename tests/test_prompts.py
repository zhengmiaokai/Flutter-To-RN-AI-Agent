"""tests/test_prompts — Tests for prompt templates."""

from prompts.convert import (
    get_conversion_prompt,
    FLUTTER_TO_RN_SYSTEM,
)
from prompts.verify import (
    get_fix_prompt,
    BUILD_FIX_SYSTEM,
)


class TestConversionPrompts:
    """Tests for Flutter-to-RN conversion prompts."""

    def test_system_prompt_exists(self):
        assert FLUTTER_TO_RN_SYSTEM is not None
        assert "react-native" in FLUTTER_TO_RN_SYSTEM.lower()
        assert "Flutter" in FLUTTER_TO_RN_SYSTEM

    def test_system_prompt_covers_widget_mapping(self):
        assert "Container" in FLUTTER_TO_RN_SYSTEM
        assert "Column" in FLUTTER_TO_RN_SYSTEM
        assert "Row" in FLUTTER_TO_RN_SYSTEM
        assert "ListView" in FLUTTER_TO_RN_SYSTEM

    def test_system_prompt_covers_state_management(self):
        assert "setState" in FLUTTER_TO_RN_SYSTEM
        assert "useState" in FLUTTER_TO_RN_SYSTEM
        assert "Provider" in FLUTTER_TO_RN_SYSTEM
        assert "ChangeNotifier" in FLUTTER_TO_RN_SYSTEM

    def test_system_prompt_covers_navigation(self):
        assert "Navigator.push" in FLUTTER_TO_RN_SYSTEM
        assert "navigation.navigate" in FLUTTER_TO_RN_SYSTEM
        assert "React Navigation" in FLUTTER_TO_RN_SYSTEM

    def test_system_prompt_covers_styling(self):
        assert "EdgeInsets" in FLUTTER_TO_RN_SYSTEM
        assert "BoxDecoration" in FLUTTER_TO_RN_SYSTEM
        assert "StyleSheet" in FLUTTER_TO_RN_SYSTEM

    def test_system_prompt_covers_dart_to_typescript(self):
        assert "Dart" in FLUTTER_TO_RN_SYSTEM
        assert "TypeScript" in FLUTTER_TO_RN_SYSTEM
        assert "final" in FLUTTER_TO_RN_SYSTEM
        assert "const" in FLUTTER_TO_RN_SYSTEM

    def test_build_fix_prompt_exists(self):
        assert BUILD_FIX_SYSTEM is not None

    def test_conversion_prompt_includes_source(self):
        prompt = get_conversion_prompt("class HomePage extends StatelessWidget {}", "HomePage.dart")
        assert "HomePage.dart" in prompt
        assert "HomePage" in prompt
        assert "React Native" in prompt

    def test_fix_prompt_includes_error(self):
        prompt = get_fix_prompt("const x = 1;", "TypeError: x", "test.tsx")
        assert "TypeError: x" in prompt
        assert "test.tsx" in prompt