"""tests/test_convert_agent — Tests for the ConvertAgent category dispatch.

Tests that the agent correctly dispatches files by category to the
correct output directories using the single-shot harness path.
"""

from pathlib import Path

import pytest

from framework.config import Config
from agents.convert_agent import ConvertAgent


class FakeHarness:
    """Minimal harness stand-in: call() returns a fixed code block."""

    def __init__(self, content: str):
        self._content = content
        self.llm = None

    def call(self, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(content=self._content)


class TestConvertAgentDispatch:
    """Tests for convert_file category dispatch."""

    @pytest.fixture
    def mock_agent(self, tmp_path):
        """Create a ConvertAgent with a fake harness returning a code block."""
        config = Config(
            source_dir=".",
            target_dir=str(tmp_path),
            api_key="test-key",
        )
        harness = FakeHarness("```tsx\nconst App = () => <View />;\n```")
        mock_state = MagicMockLike()
        return ConvertAgent(config, harness, mock_state)


class MagicMockLike:
    def is_completed(self, key):
        return False

    def test_convert_file_screens(self, mock_agent, tmp_path):
        src = tmp_path / "HomePage.dart"
        src.write_text("import 'package:flutter/material.dart';\nclass HomePage extends StatelessWidget {}")
        mock_agent.convert_file("screens", src)
        output = tmp_path / "src" / "screens" / "HomePage.tsx"
        assert output.exists()

    def test_convert_file_widgets(self, mock_agent, tmp_path):
        src = tmp_path / "CustomButton.dart"
        src.write_text("import 'package:flutter/material.dart';\nclass CustomButton extends StatelessWidget {}")
        mock_agent.convert_file("widgets", src)
        output = tmp_path / "src" / "components" / "CustomButton.tsx"
        assert output.exists()

    def test_convert_file_services(self, mock_agent, tmp_path):
        src = tmp_path / "ApiService.dart"
        src.write_text("class ApiService { Future get() async {} }")
        mock_agent.convert_file("services", src)
        output = tmp_path / "src" / "services" / "ApiService.ts"
        assert output.exists()

    def test_convert_file_models(self, mock_agent, tmp_path):
        src = tmp_path / "User.dart"
        src.write_text("class User { final String name; User(this.name); }")
        mock_agent.convert_file("models", src)
        output = tmp_path / "src" / "models" / "User.ts"
        assert output.exists()

    def test_convert_file_utils(self, mock_agent, tmp_path):
        src = tmp_path / "helpers.dart"
        src.write_text("String formatDate(DateTime d) => d.toString();")
        mock_agent.convert_file("utils", src)
        output = tmp_path / "src" / "utils" / "helpers.ts"
        assert output.exists()

    def test_convert_file_unknown_category(self, mock_agent, tmp_path):
        src = tmp_path / "test.dart"
        src.write_text("// test")
        with pytest.raises(ValueError, match="Unknown category"):
            mock_agent.convert_file("unknown", src)
