"""tests/test_tools — Tests for @tool functions and the FileWriter class."""
from pathlib import Path

import pytest
from tools import (
    FileWriter,
    VERIFY_FIX_TOOLS,
    classify_file,
    extract_code_from_response,
    read_source_file,
    run_build_check,
    run_tsc_check,
    scan_source_directory,
    write_output_file,
)


class TestClassifyFileTool:
    """Tests for the classify_file @tool."""

    def test_screen_dirs(self):
        assert classify_file.invoke({"file_path": "lib/pages/Home.dart"}) == "screens"
        assert classify_file.invoke({"file_path": "lib/screens/Profile.dart"}) == "screens"
        assert classify_file.invoke({"file_path": "lib/views/Dashboard.dart"}) == "screens"

    def test_widget_dirs(self):
        assert classify_file.invoke({"file_path": "lib/components/Button.dart"}) == "widgets"
        assert classify_file.invoke({"file_path": "lib/widgets/Card.dart"}) == "widgets"

    def test_service_dirs(self):
        assert classify_file.invoke({"file_path": "lib/services/api.dart"}) == "services"
        assert classify_file.invoke({"file_path": "lib/network/client.dart"}) == "services"

    def test_model_dirs(self):
        assert classify_file.invoke({"file_path": "lib/models/User.dart"}) == "models"

    def test_provider_dirs(self):
        assert classify_file.invoke({"file_path": "lib/providers/Auth.dart"}) == "providers"

    def test_util_dirs(self):
        assert classify_file.invoke({"file_path": "lib/utils/helpers.dart"}) == "utils"

    def test_asset_extensions(self):
        assert classify_file.invoke({"file_path": "images/logo.png"}) == "assets"
        assert classify_file.invoke({"file_path": "assets/bg.jpg"}) == "assets"

    def test_config(self):
        assert classify_file.invoke({"file_path": "pubspec.yaml"}) == "config"

    def test_skip_readme(self):
        assert classify_file.invoke({"file_path": "README.md"}) == "skip"


class TestScanSourceDirectoryTool:
    """Tests for scan_source_directory @tool."""

    def test_scan_empty_dir(self, tmp_path):
        result = scan_source_directory.invoke({"source_dir": str(tmp_path)})
        # Should return JSON with total=0 and no category lists (empty ones are excluded)
        import json
        data = json.loads(result)
        assert "total" in data

    def test_scan_dart_file(self, tmp_path):
        file = tmp_path / "lib" / "screens" / "Home.dart"
        file.parent.mkdir(parents=True)
        file.write_text("class Home {}")

        result = scan_source_directory.invoke({"source_dir": str(tmp_path)})
        import json
        data = json.loads(result)
        assert data["total"] >= 1


class TestExtractCodeFromResponse:
    """Tests for the extract_code_from_response @tool."""

    def test_tsx_block(self):
        result = extract_code_from_response.invoke({"response": "```tsx\nconst x = <View />;\n```"})
        assert result == "const x = <View />;"

    def test_typescript_block(self):
        result = extract_code_from_response.invoke({"response": "```typescript\nconst x: number = 1;\n```"})
        assert result == "const x: number = 1;"

    def test_json_block(self):
        result = extract_code_from_response.invoke({"response": '```json\n{"key": "value"}\n```'})
        assert result == '{"key": "value"}'

    def test_no_block(self):
        result = extract_code_from_response.invoke({"response": "const x = 1;"})
        assert result == ""


class TestVerifyFixTools:
    """Tests for the ReAct verify-fix tools."""

    def test_verify_fix_tools_registry(self):
        assert {t.name for t in VERIFY_FIX_TOOLS} == {
            "read_source_file",
            "write_output_file",
            "run_tsc_check",
            "run_build_check",
        }

    def test_read_source_file(self, tmp_path):
        f = tmp_path / "a.ts"
        f.write_text("export const x = 1;")
        assert read_source_file.invoke({"file_path": str(f)}) == "export const x = 1;"

    def test_read_source_file_missing(self, tmp_path):
        result = read_source_file.invoke({"file_path": str(tmp_path / "nope.ts")})
        assert result.startswith("Error: file not found")

    def test_write_output_file_creates_parents(self, tmp_path):
        out = tmp_path / "src" / "screens" / "Home.tsx"
        result = write_output_file.invoke({"code": "const Home = () => <View />;", "output_path": str(out)})
        assert "Written" in result
        assert out.exists()
        assert out.read_text() == "const Home = () => <View />;"

    def test_run_tsc_check_requires_node_modules(self, tmp_path):
        # Guard triggers before any subprocess call — no node_modules present.
        result = run_tsc_check.invoke({"target_dir": str(tmp_path)})
        assert "node_modules missing" in result

    def test_run_tsc_check_missing_dir(self, tmp_path):
        result = run_tsc_check.invoke({"target_dir": str(tmp_path / "missing")})
        assert "target directory not found" in result

    def test_run_build_check_missing_dir(self, tmp_path):
        result = run_build_check.invoke({"target_dir": str(tmp_path / "missing")})
        assert "target directory not found" in result


class TestFileWriter:
    """Tests for FileWriter (backward-compatible class in tools/__init__)."""

    def test_extract_code_tsx(self):
        response = "```tsx\nconst x = <View />;\n```"
        assert FileWriter.extract_code(response) == "const x = <View />;"

    def test_extract_code_typescript(self):
        response = "```typescript\nconst x: number = 1;\n```"
        assert FileWriter.extract_code(response) == "const x: number = 1;"

    def test_extract_code_json(self):
        response = '```json\n{"key": "value"}\n```'
        assert FileWriter.extract_code(response) == '{"key": "value"}'

    def test_extract_code_no_block(self):
        response = "const x = 1;"
        assert FileWriter.extract_code(response) == ""

    def test_extract_tsx(self):
        response = "```tsx\nconst x = <View />;\n```"
        assert FileWriter.extract_tsx(response) == "const x = <View />;"

    def test_extract_tsx_none(self):
        response = "```json\n{}\n```"
        assert FileWriter.extract_tsx(response) is None

    def test_write_screen(self, tmp_path):
        writer = FileWriter(str(tmp_path))
        out = writer.write_screen("const Home = () => <View />;", "Home")
        assert out.exists()
        assert out == tmp_path / "src" / "screens" / "Home.tsx"

    def test_write_widget(self, tmp_path):
        writer = FileWriter(str(tmp_path))
        out = writer.write_widget("const Button = () => <Pressable />;", "Button")
        assert out.exists()
        assert out == tmp_path / "src" / "components" / "Button.tsx"

    def test_write_service(self, tmp_path):
        writer = FileWriter(str(tmp_path))
        out = writer.write_service("export const api = { get: () => fetch('/api') };", "api.ts")
        assert out.exists()
        assert out == tmp_path / "src" / "services" / "api.ts"

    def test_write_model(self, tmp_path):
        writer = FileWriter(str(tmp_path))
        out = writer.write_model("export interface User { name: string; }", "User.ts")
        assert out.exists()
        assert out == tmp_path / "src" / "models" / "User.ts"

    def test_write_provider(self, tmp_path):
        writer = FileWriter(str(tmp_path))
        out = writer.write_provider("export const AuthContext = createContext();", "AuthContext.tsx")
        assert out.exists()
        assert out == tmp_path / "src" / "providers" / "AuthContext.tsx"

    def test_write_util_file(self, tmp_path):
        writer = FileWriter(str(tmp_path))
        out = writer.write_util_file("export const formatDate = (d: Date) => d.toISOString();", "format.ts")
        assert out.exists()
        assert out == tmp_path / "src" / "utils" / "format.ts"
