"""tests/test_classifier — Tests for the @tool-decorated classify_file function.

Replaces the old FileClassifier class tests with tests against the
LangChain @tool-decorated classify_file function from tools/__init__.py.
"""

from pathlib import Path

from tools import classify_file, SKIP_DIRS, SKIP_FILES


class TestClassifyFileTool:
    """Tests for classify_file @tool."""

    def test_classify_screen_by_dir(self):
        assert classify_file.invoke({"file_path": "lib/pages/HomePage.dart"}) == "screens"
        assert classify_file.invoke({"file_path": "lib/screens/Profile.dart"}) == "screens"
        assert classify_file.invoke({"file_path": "lib/views/Dashboard.dart"}) == "screens"

    def test_classify_widget_by_dir(self):
        assert classify_file.invoke({"file_path": "lib/components/Button.dart"}) == "widgets"
        assert classify_file.invoke({"file_path": "lib/shared/Header.dart"}) == "widgets"
        assert classify_file.invoke({"file_path": "lib/widgets/Card.dart"}) == "widgets"

    def test_classify_service_by_dir(self):
        assert classify_file.invoke({"file_path": "lib/services/ApiService.dart"}) == "services"
        assert classify_file.invoke({"file_path": "lib/network/HttpClient.dart"}) == "services"
        assert classify_file.invoke({"file_path": "lib/channels/GlobalChannel.dart"}) == "services"

    def test_classify_model_by_dir(self):
        assert classify_file.invoke({"file_path": "lib/models/User.dart"}) == "models"
        assert classify_file.invoke({"file_path": "lib/entities/Product.dart"}) == "models"

    def test_classify_provider_by_dir(self):
        assert classify_file.invoke({"file_path": "lib/providers/AuthProvider.dart"}) == "providers"
        assert classify_file.invoke({"file_path": "lib/view_models/LoginViewModel.dart"}) == "providers"
        assert classify_file.invoke({"file_path": "lib/blocs/CounterBloc.dart"}) == "providers"

    def test_classify_util_by_dir(self):
        assert classify_file.invoke({"file_path": "lib/utils/helpers.dart"}) == "utils"
        assert classify_file.invoke({"file_path": "lib/helpers/format.dart"}) == "utils"

    def test_classify_asset_by_ext(self):
        assert classify_file.invoke({"file_path": "images/logo.png"}) == "assets"
        assert classify_file.invoke({"file_path": "assets/bg.jpg"}) == "assets"

    def test_classify_config(self):
        assert classify_file.invoke({"file_path": "pubspec.yaml"}) == "config"
        assert classify_file.invoke({"file_path": "analysis_options.yaml"}) == "config"

    def test_classify_skip_readme(self):
        assert classify_file.invoke({"file_path": "README.md"}) == "skip"

    def test_skip_files_contains_expected(self):
        assert "pubspec.lock" in SKIP_FILES
        assert ".flutter-plugins" in SKIP_FILES
        assert ".flutter-plugins-dependencies" in SKIP_FILES

    def test_skip_dirs_contains_expected(self):
        assert ".git" in SKIP_DIRS
        assert ".dart_tool" in SKIP_DIRS
        assert "build" in SKIP_DIRS
        assert "ios" in SKIP_DIRS
        assert "android" in SKIP_DIRS

    def test_classify_root_dart_as_config(self, tmp_path):
        src = tmp_path / "main.dart"
        src.write_text("// test")
        result = classify_file.invoke({"file_path": str(src), "source_dir": str(tmp_path)})
        assert result == "config"

    def test_classify_lib_root_dart_as_config(self, tmp_path):
        lib = tmp_path / "lib"
        lib.mkdir()
        src = lib / "Application.dart"
        src.write_text("// test")
        result = classify_file.invoke({"file_path": str(src), "source_dir": str(tmp_path)})
        assert result == "config"

    def test_classify_deep_dart_as_util(self, tmp_path):
        src = tmp_path / "deep" / "nested" / "helper.dart"
        src.parent.mkdir(parents=True)
        src.write_text("// test")
        result = classify_file.invoke({"file_path": str(src), "source_dir": str(tmp_path)})
        assert result == "utils"
