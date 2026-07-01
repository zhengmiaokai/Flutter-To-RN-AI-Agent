"""framework/config — Global configuration for the Flutter-to-RN converter."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os

from dotenv import load_dotenv


@dataclass
class Config:
    """Global configuration for the Flutter-to-RN converter."""

    source_dir: str = "sample"
    target_dir: str = "output"
    template_dir: Optional[str] = None

    model: str = "deepseek-v4-pro"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    max_retries: int = 3
    timeout: float = 120.0
    llm_max_retries: int = 2
    scan_mode: str = "fast"
    skip_setup: bool = False
    skip_conversion: bool = False
    skip_verification: bool = False

    state_file: str = ".flutter_to_rn_state.json"

    _loaded: bool = field(default=False, repr=False)

    def __post_init__(self):
        if not self._loaded:
            load_dotenv()
            self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            self.base_url = self.base_url or os.getenv("OPENAI_BASE_URL")
            self._loaded = True

    @property
    def state_path(self) -> Path:
        return Path(self.target_dir) / self.state_file

    def validate(self) -> list[str]:
        errors = []
        if not self.api_key:
            errors.append("OPENAI_API_KEY is not set (env var, .env, or --api-key)")
        src = Path(self.source_dir) if self.source_dir else None
        if src and not src.exists():
            errors.append(f"Source directory not found: {self.source_dir}")
        return errors


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(**kwargs) -> Config:
    global _config
    _config = Config(**kwargs)
    _config._loaded = True
    return _config
