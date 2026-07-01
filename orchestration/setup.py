"""orchestration/setup — Initialize the target React Native output environment.

Uses templates from the templates/ package to write all static output files
(package.json, tsconfig.json, babel.config.js, metro.config.js, App.tsx, navigation, home screen).
"""

import json
from pathlib import Path

from framework.config import Config
from templates.package_json import PACKAGE_JSON
from templates.rn_app import RN_APP_TSX
from templates.rn_navigation import RN_APP_NAVIGATOR_TSX
from templates.rn_screens import RN_HOME_SCREEN_TSX


class ProjectSetup:
    """Initialize the target React Native project environment using template assets."""

    def __init__(self, config: Config):
        self._config = config

    def run(self):
        if self._config.skip_setup:
            return

        target = Path(self._config.target_dir)
        self._write_config_files(target)
        self._write_app_files(target)
        self._write_navigation(target)
        self._write_home_screen(target)
        self._write_empty_dirs(target)

    # ---- config files --------------------------------------------------------

    def _write_config_files(self, target: Path):
        target.mkdir(parents=True, exist_ok=True)

        # package.json
        pkg = target / "package.json"
        pkg.write_text(json.dumps(PACKAGE_JSON, indent=2) + "\n", encoding="utf-8")

        # tsconfig.json
        tsconfig = target / "tsconfig.json"
        tsconfig.write_text(
            json.dumps(
                {
                    "compilerOptions": {
                        "target": "ESNext",
                        "module": "commonjs",
                        "lib": ["ESNext"],
                        "allowJs": True,
                        "jsx": "react-jsx",
                        "strict": True,
                        "moduleResolution": "node",
                        "allowSyntheticDefaultImports": True,
                        "esModuleInterop": True,
                        "skipLibCheck": True,
                        "forceConsistentCasingInFileNames": True,
                        "resolveJsonModule": True,
                        "isolatedModules": True,
                        "noEmit": True,
                        "baseUrl": ".",
                        "paths": {
                            "@/*": ["src/*"],
                        },
                    },
                    "include": ["src/**/*", "App.tsx", "index.js"],
                    "exclude": ["node_modules", "babel.config.js", "metro.config.js", "jest.config.js"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        # babel.config.js
        babel = target / "babel.config.js"
        babel.write_text(
            "module.exports = {\n"
            "  presets: ['module:@react-native/babel-preset'],\n"
            "};\n",
            encoding="utf-8",
        )

        # metro.config.js
        metro = target / "metro.config.js"
        metro.write_text(
            "const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');\n\n"
            "/** @type {import('metro-config').MetroConfig} */\n"
            "const config = {};\n\n"
            "module.exports = mergeConfig(getDefaultConfig(__dirname), config);\n",
            encoding="utf-8",
        )

    # ---- app files -----------------------------------------------------------

    def _write_app_files(self, target: Path):
        (target / "App.tsx").write_text(RN_APP_TSX, encoding="utf-8")

    # ---- navigation ----------------------------------------------------------

    def _write_navigation(self, target: Path):
        nav_dir = target / "src" / "navigation"
        nav_dir.mkdir(parents=True, exist_ok=True)
        (nav_dir / "AppNavigator.tsx").write_text(RN_APP_NAVIGATOR_TSX, encoding="utf-8")

    # ---- home screen ---------------------------------------------------------

    def _write_home_screen(self, target: Path):
        home_dir = target / "src" / "screens"
        home_dir.mkdir(parents=True, exist_ok=True)
        (home_dir / "Home.tsx").write_text(RN_HOME_SCREEN_TSX, encoding="utf-8")

    # ---- empty directories ---------------------------------------------------

    def _write_empty_dirs(self, target: Path):
        src = target / "src"
        (src / "components").mkdir(parents=True, exist_ok=True)
        (src / "services").mkdir(parents=True, exist_ok=True)
        (src / "models").mkdir(parents=True, exist_ok=True)
        (src / "utils").mkdir(parents=True, exist_ok=True)
        (src / "assets").mkdir(parents=True, exist_ok=True)
